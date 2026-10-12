"""Store a Rust-admitted envelope using the supplied Lab's transaction rules.

Only lab_server's Rust admission tool calls this function. It is not an MCP
operation accepting a caller assertion that an envelope has been validated.

The transaction below is adapted from MAS Protocol Lab Store.send, copyright
2026 Emmett Miller, MIT (see rust_codec/LICENSE and rust_codec/UPSTREAM.json). The only
changed boundary is canonical admission: Rust returns the checked envelope in
one operation instead of Python repeating an encode/parse round trip.
"""
from mas_protocol.store import digest, dump


def send_admitted(store, canonical, authenticated_sender):
    text = dump(canonical)
    fingerprint = digest(canonical)
    size = len(text.encode())
    run_id = canonical["run_id"]
    message_id = canonical["message_id"]
    sender = canonical["sender"]
    recipient = canonical["recipient"]
    with store.transaction() as db:
        run, config = store._run(db, run_id, authenticated_sender)
        if sender != authenticated_sender:
            raise ValueError("sender differs from host worker identity")
        if recipient not in config["agents"]:
            raise ValueError("unregistered recipient")
        old = db.execute("SELECT hash,seq FROM messages WHERE run=? AND id=?",
                         (run_id, message_id)).fetchone()
        if old:
            if old["hash"] != fingerprint:
                raise ValueError("message identity reused with different content")
            return dict(accepted=True, duplicate=True, sequence=old["seq"])
        store._run(db, run_id, authenticated_sender, True)
        if canonical["version"] != run["active"]:
            raise ValueError("inactive or incompatible protocol version")
        if run["message_count"] + 1 > config["max_messages"] or run["byte_count"] + size > config["max_bytes"]:
            raise ValueError("communication budget exhausted")
        cur = db.execute("INSERT INTO messages(run,id,sender,recipient,content,hash) VALUES(?,?,?,?,?,?)",
                         (run_id, message_id, sender, recipient, text, fingerprint))
        db.execute("UPDATE runs SET message_count=message_count+1,byte_count=byte_count+? WHERE id=?",
                   (size, run_id))
        return dict(accepted=True, duplicate=False, sequence=cur.lastrowid)
