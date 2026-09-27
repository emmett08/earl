"""Fixed, agent-independent behavioural probes; run in a fresh subprocess."""

import html
import json
import os
import sys
import traceback


def check(fn):
    try:
        fn()
        return {"passed": True, "detail": "fixed behavioural assertions passed"}
    except Exception as exc:
        return {"passed": False, "detail": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()}


def main():
    from notification_service import Message, make_service
    from notification_service.channel import MemoryGateway

    def baseline():
        gateway = MemoryGateway()
        service = make_service(gateway)
        assert "console" in service.available_channels()
        receipt = service.send("console", Message("terminal", "Ready", "ok"))
        assert (receipt.medium, receipt.destination, receipt.content) == (
            "console", "terminal", b"Ready: ok"
        )
        assert len(gateway.sent) == 1
        try:
            service.send("missing", Message("x", "s", "b"))
        except ValueError:
            pass
        else:
            raise AssertionError("unknown channel accepted")
        assert len(gateway.sent) == 1

    def email():
        gateway = MemoryGateway()
        service = make_service(gateway)
        assert "email" in service.available_channels()
        subject = '<A&"'
        body = "B<'&\""
        receipt = service.send("email", Message("a@example.test", subject, body))
        expected = f"Subject: {html.escape(subject, quote=True)}\n\n{html.escape(body, quote=True)}".encode("utf-8")
        assert (receipt.medium, receipt.destination, receipt.content) == (
            "email", "a@example.test", expected
        )
        assert len(gateway.sent) == 1 and gateway.sent[0].content == expected

    def sms():
        gateway = MemoryGateway()
        service = make_service(gateway)
        assert "sms" in service.available_channels()
        receipt = service.send("sms", Message("+440000000000", "ignored", "hello"))
        assert (receipt.medium, receipt.destination, receipt.content) == (
            "sms", "+440000000000", b"hello"
        )
        assert len(gateway.sent) == 1

    def cap():
        gateway = MemoryGateway()
        service = make_service(gateway)
        at_limit = "é" * 80
        receipt = service.send("sms", Message("+440000000000", "ignored", at_limit))
        assert receipt.content == at_limit.encode("utf-8") and len(receipt.content) == 160
        assert len(gateway.sent) == 1
        for oversized in ("a" * 161, "é" * 81):
            try:
                service.send("sms", Message("+440000000000", "ignored", oversized))
            except ValueError:
                pass
            else:
                raise AssertionError(f"overlong SMS accepted ({len(oversized.encode('utf-8'))} bytes)")
            assert len(gateway.sent) == 1, "oversized SMS reached gateway"

    case = os.environ["ARCH_CASE"]
    checks = {"baseline_contract": check(baseline), "feature_behaviour": check(email if case == "a" else sms)}
    if case == "b":
        checks["email_regression"] = check(email)
        checks["payload_cap"] = check(cap)
    modules = sorted(name for name in sys.modules if name.startswith("notification_service."))
    channels = make_service(MemoryGateway()).available_channels()
    print(json.dumps({"checks": checks, "imported_modules": modules,
                      "registered_channels": channels}, sort_keys=True))


if __name__ == "__main__":
    main()
