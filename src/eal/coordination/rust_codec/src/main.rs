use mas_protocol_codec::{
    admit_message, encode_message, parse_message, Diagnostic, ENCODE_ENVELOPE_ALLOWANCE, MAX_BYTES, MAX_DEPTH,
};
use serde::de::{self, Deserialize, Deserializer, MapAccess, Visitor};
use serde_json::Value;
use std::fmt;
use std::io::{self, BufRead, Read, Write};

// A source byte can become six ASCII bytes (\uXXXX) inside the control request.
// Bound framing independently of the unchanged source/wire limit.
const MAX_REQUEST_BYTES: usize = 6 * (MAX_BYTES + ENCODE_ENVELOPE_ALLOWANCE) + 1_024;

#[cfg(target_os = "linux")]
fn bind_parent_lifetime() -> io::Result<()> {
    use std::os::raw::{c_int, c_ulong};

    // Linux prctl(2): only this process's parent-death signal is changed. No
    // memory, file, network, executable, or caller-provided argument is used.
    unsafe extern "C" {
        fn getppid() -> c_int;
        fn prctl(option: c_int, arg2: c_ulong, arg3: c_ulong, arg4: c_ulong, arg5: c_ulong) -> c_int;
    }
    const PR_SET_PDEATHSIG: c_int = 1;
    const SIGKILL: c_ulong = 9;

    // SAFETY: these libc functions use the documented Linux ABI, accept no
    // pointers, and receive only fixed valid option/signal constants.
    let parent = unsafe { getppid() };
    if unsafe { prctl(PR_SET_PDEATHSIG, SIGKILL, 0, 0, 0) } != 0 {
        return Err(io::Error::last_os_error());
    }
    // Parent death before registration produces no signal. Detect that race
    // before accepting a request rather than leaving an orphan codec alive.
    if parent <= 1 || unsafe { getppid() } != parent {
        return Err(io::Error::new(io::ErrorKind::BrokenPipe, "Codec parent exited during startup"));
    }
    Ok(())
}

#[cfg(not(target_os = "linux"))]
fn bind_parent_lifetime() -> io::Result<()> {
    Ok(())
}

fn error(code: &'static str, message: impl Into<String>) -> Diagnostic {
    Diagnostic { code, message: message.into(), line: None, column: None }
}

fn operation(name: &str, source: &str, max_bytes: usize, max_depth: usize) -> Result<Value, Diagnostic> {
    match name {
        "parse" => parse_message(source, max_bytes, max_depth)
            .map(|message| serde_json::json!({"ok":true,"message":message.to_value()})),
        "encode" => encode_message(source, max_bytes, max_depth)
            .map(|text| serde_json::json!({"ok":true,"text":text})),
        "admit" => admit_message(source, max_bytes, max_depth)
            .map(|message| serde_json::json!({"ok":true,"message":message.to_value()})),
        _ => Err(error("COMMAND", "Operation must be parse, encode or admit")),
    }
}

fn response(result: Result<Value, Diagnostic>) -> Value {
    match result {
        Ok(value) => value,
        Err(diagnostic) => serde_json::json!({"ok":false,"error":diagnostic.to_value()}),
    }
}

struct Request {
    operation: String,
    source: String,
    max_bytes: usize,
    max_depth: usize,
}

// The transport control object is separate from the nom-recognised message.
// Deserialise fields directly so duplicate names cannot be silently overwritten.
impl<'de> Deserialize<'de> for Request {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        struct RequestVisitor;
        impl<'de> Visitor<'de> for RequestVisitor {
            type Value = Request;
            fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
                formatter.write_str("a codec request object with exactly four fields")
            }
            fn visit_map<M: MapAccess<'de>>(self, mut map: M) -> Result<Request, M::Error> {
                let (mut operation, mut source, mut max_bytes, mut max_depth) = (None, None, None, None);
                while let Some(key) = map.next_key::<String>()? {
                    match key.as_str() {
                        "operation" => {
                            if operation.is_some() { return Err(de::Error::duplicate_field("operation")); }
                            operation = Some(map.next_value()?);
                        }
                        "source" => {
                            if source.is_some() { return Err(de::Error::duplicate_field("source")); }
                            source = Some(map.next_value()?);
                        }
                        "max_bytes" => {
                            if max_bytes.is_some() { return Err(de::Error::duplicate_field("max_bytes")); }
                            max_bytes = Some(map.next_value()?);
                        }
                        "max_depth" => {
                            if max_depth.is_some() { return Err(de::Error::duplicate_field("max_depth")); }
                            max_depth = Some(map.next_value()?);
                        }
                        _ => return Err(de::Error::unknown_field(
                            &key, &["operation", "source", "max_bytes", "max_depth"],
                        )),
                    }
                }
                Ok(Request {
                    operation: operation.ok_or_else(|| de::Error::missing_field("operation"))?,
                    source: source.ok_or_else(|| de::Error::missing_field("source"))?,
                    max_bytes: max_bytes.ok_or_else(|| de::Error::missing_field("max_bytes"))?,
                    max_depth: max_depth.ok_or_else(|| de::Error::missing_field("max_depth"))?,
                })
            }
        }
        deserializer.deserialize_map(RequestVisitor)
    }
}

fn request(frame: &[u8]) -> Result<Value, Diagnostic> {
    let source = std::str::from_utf8(frame)
        .map_err(|_| error("UNICODE", "Control request must be valid UTF-8"))?;
    let request: Request = serde_json::from_str(source)
        .map_err(|reason| error("REQUEST", format!("Invalid codec control request: {reason}")))?;
    operation(&request.operation, &request.source, request.max_bytes, request.max_depth)
}

fn write_response<W: Write>(writer: &mut W, value: &Value) -> io::Result<()> {
    serde_json::to_writer(&mut *writer, value)?;
    writer.write_all(b"\n")?;
    writer.flush()
}

fn serve<R: BufRead, W: Write>(mut reader: R, mut writer: W) -> io::Result<bool> {
    loop {
        let mut frame = Vec::new();
        // take() prevents read_until() allocating an unbounded line.
        let length = (&mut reader).take((MAX_REQUEST_BYTES + 1) as u64)
            .read_until(b'\n', &mut frame)?;
        if length == 0 { return Ok(true); }
        if length > MAX_REQUEST_BYTES {
            write_response(&mut writer, &response(Err(error(
                "SIZE", format!("Control request exceeds {MAX_REQUEST_BYTES} UTF-8 bytes"),
            ))))?;
            return Ok(false);
        }
        write_response(&mut writer, &response(request(&frame)))?;
    }
}

fn main() {
    let mut args = std::env::args().skip(1);
    let name = args.next().unwrap_or_default();
    if name == "serve" {
        if args.next().is_some() {
            println!("{}", response(Err(error("COMMAND", "Use serve without arguments"))));
            std::process::exit(2);
        }
        if let Err(reason) = bind_parent_lifetime() {
            println!("{}", response(Err(error("PROCESS", format!("Cannot bind codec parent lifetime: {reason}")))));
            std::process::exit(2);
        }
        let input = io::stdin();
        let output = io::stdout();
        if !matches!(serve(input.lock(), output.lock()), Ok(true)) {
            std::process::exit(2);
        }
        return;
    }

    // Preserve the supplied one-shot command and its response/exit contract.
    let mut max_bytes = MAX_BYTES;
    let mut max_depth = MAX_DEPTH;
    let mut valid = true;
    while let Some(flag) = args.next() {
        let value = args.next().and_then(|text| text.parse::<usize>().ok());
        match (flag.as_str(), value) {
            ("--max-bytes", Some(n)) => max_bytes = n,
            ("--max-depth", Some(n)) => max_depth = n,
            _ => valid = false,
        }
    }
    let result = if !valid || !matches!(name.as_str(), "parse" | "encode" | "admit") {
        Err(error("COMMAND", "Use parse|encode|admit [--max-bytes N] [--max-depth N] with UTF-8 stdin, or serve"))
    } else {
        let mut source = String::new();
        let transport_limit = MAX_BYTES + if matches!(name.as_str(), "encode" | "admit") { ENCODE_ENVELOPE_ALLOWANCE } else { 0 };
        match io::stdin().take((transport_limit + 1) as u64).read_to_string(&mut source) {
            Err(_) => Err(error("UNICODE", "stdin must be valid UTF-8")),
            Ok(_) => operation(&name, &source, max_bytes, max_depth),
        }
    };
    let success = result.is_ok();
    println!("{}", response(result));
    if !success { std::process::exit(2); }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    fn wire(payload: &str) -> String {
        format!("message \"m\" run \"r\" from \"a\" to \"b\" version \"1\" kind \"request\" payload {payload};")
    }
    fn frame(name: &str, source: &str, max_bytes: usize, max_depth: usize) -> String {
        serde_json::json!({"operation":name,"source":source,"max_bytes":max_bytes,"max_depth":max_depth}).to_string() + "\n"
    }
    fn run(input: &[u8]) -> (bool, Vec<Value>) {
        let mut output = Vec::new();
        let complete = serve(Cursor::new(input), &mut output).unwrap();
        let responses = String::from_utf8(output).unwrap().lines()
            .map(|line| serde_json::from_str(line).unwrap()).collect();
        (complete, responses)
    }

    #[test]
    fn repeated_operations_match_one_shot_results() {
        let source = wire(r#"{"text":"∀x:🧠","n":340282366920938463463374607431768211456,"flag":true}"#);
        let typed = parse_message(&source, MAX_BYTES, MAX_DEPTH).unwrap().to_value().to_string();
        let input = (frame("encode", &typed, MAX_BYTES, MAX_DEPTH)
            + &frame("parse", &source, MAX_BYTES, MAX_DEPTH)).repeat(20);
        let (complete, replies) = run(input.as_bytes());
        assert!(complete);
        assert_eq!(replies.len(), 40);
        for pair in replies.chunks(2) {
            assert_eq!(pair[0], operation("encode", &typed, MAX_BYTES, MAX_DEPTH).unwrap());
            assert_eq!(pair[1], operation("parse", &source, MAX_BYTES, MAX_DEPTH).unwrap());
        }
    }

    #[test]
    fn malformed_requests_are_isolated_and_strict() {
        let mut input = String::new();
        for invalid in ["{", "{}", "[]", r#"{"operation":"parse","operation":"encode","source":"","max_bytes":1,"max_depth":1}"#,
            r#"{"operation":"parse","source":"","max_bytes":true,"max_depth":1}"#,
            r#"{"operation":"parse","source":"","max_bytes":1,"max_depth":1,"extra":0}"#,
            r#"{"operation":"parse","source":"","max_bytes":1,"max_depth":1} trailing"#] {
            input.push_str(invalid);
            input.push('\n');
        }
        input += &frame("parse", &wire("{}"), MAX_BYTES, MAX_DEPTH);
        let (complete, replies) = run(input.as_bytes());
        assert!(complete);
        assert_eq!(replies.len(), 8);
        assert!(replies[..7].iter().all(|reply| reply["error"]["code"] == "REQUEST"));
        assert_eq!(replies[7]["ok"], true);
    }

    #[test]
    fn complete_source_recognition_and_limits_remain_enforced() {
        let valid = wire("{}");
        let nested = wire(&format!("{{\"x\":{}0{}}}", "[".repeat(32), "]".repeat(32)));
        let input = frame("parse", &(valid.clone() + " garbage"), MAX_BYTES, MAX_DEPTH)
            + &frame("parse", &valid, 16, MAX_DEPTH)
            + &frame("parse", &nested, MAX_BYTES, MAX_DEPTH)
            + &frame("parse", &valid, MAX_BYTES + 1, MAX_DEPTH)
            + &frame("parse", &valid, MAX_BYTES, 0)
            + &frame("parse", &wire(r#"{"x":1,"x":2}"#), MAX_BYTES, MAX_DEPTH);
        let (complete, replies) = run(input.as_bytes());
        assert!(complete);
        let codes: Vec<&str> = replies.iter().map(|reply| reply["error"]["code"].as_str().unwrap()).collect();
        assert_eq!(codes, ["SYNTAX", "SIZE", "DEPTH", "LIMIT", "LIMIT", "DUPLICATE"]);
    }

    #[test]
    fn oversized_control_frame_fails_closed_with_bounded_read() {
        let input = vec![b'x'; MAX_REQUEST_BYTES + 10];
        let (complete, replies) = run(&input);
        assert!(!complete);
        assert_eq!(replies.len(), 1);
        assert_eq!(replies[0]["error"]["code"], "SIZE");
    }

    #[test]
    fn invalid_utf8_does_not_poison_next_request() {
        let mut input = vec![0xff, b'\n'];
        input.extend(frame("parse", &wire("{}"), MAX_BYTES, MAX_DEPTH).as_bytes());
        let (complete, replies) = run(&input);
        assert!(complete);
        assert_eq!(replies[0]["error"]["code"], "UNICODE");
        assert_eq!(replies[1]["ok"], true);
    }

    #[test]
    fn admission_control_operation_reuses_canonical_result() {
        let source = wire(r#"{"n":-0,"text":"∀x:🧠","arr":[]}"#);
        let typed = parse_message(&source, MAX_BYTES, MAX_DEPTH).unwrap().to_value().to_string();
        let input = frame("admit", &typed, MAX_BYTES, MAX_DEPTH)
            + &frame("parse", &source, MAX_BYTES, MAX_DEPTH)
            + &frame("admit", &(typed+" trailing"), MAX_BYTES, MAX_DEPTH);
        let (complete, replies) = run(input.as_bytes());
        assert!(complete);
        assert_eq!(replies[0], replies[1]);
        assert_eq!(replies[2]["ok"], false);
    }
}
