use std::io::{BufRead, BufReader, Write};
use std::process::{Command, Stdio};

#[test]
fn one_process_flushes_and_recovers_between_requests() {
    let mut child = Command::new(env!("CARGO_BIN_EXE_mas-protocol-codec"))
        .arg("serve").stdin(Stdio::piped()).stdout(Stdio::piped()).spawn().unwrap();
    let mut input = child.stdin.take().unwrap();
    let mut output = BufReader::new(child.stdout.take().unwrap());
    let source = "message \"m\" run \"r\" from \"a\" to \"b\" version \"1\" kind \"request\" payload {};";
    for operation in ["parse", "unknown", "parse"] {
        let request = serde_json::json!({"operation":operation,"source":source,"max_bytes":65536,"max_depth":32});
        writeln!(input, "{request}").unwrap();
        input.flush().unwrap();
        let mut line = String::new();
        assert!(output.read_line(&mut line).unwrap() > 0);
        let response: serde_json::Value = serde_json::from_str(&line).unwrap();
        assert_eq!(response["ok"], operation == "parse");
        assert!(child.try_wait().unwrap().is_none());
    }
    drop(input);
    assert!(child.wait().unwrap().success());
}
