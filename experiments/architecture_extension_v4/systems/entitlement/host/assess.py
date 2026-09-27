"""Host-only behavioural assessor. Never place this directory in a coding clone."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
import traceback
from pathlib import Path


def source_sha256(source: Path) -> str:
    digest = hashlib.sha256()
    paths = sorted((p for p in source.rglob("*.py") if "__pycache__" not in p.parts),
                   key=lambda p: p.relative_to(source).as_posix())
    if (source / "ARCHITECTURE.md").is_file():
        paths.append(source / "ARCHITECTURE.md")
    for path in sorted(paths, key=lambda p: p.relative_to(source).as_posix()):
        digest.update(path.relative_to(source).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
        digest.update(b"\n")
    return digest.hexdigest()


def rig(m, seats=2):
    store, issuer = m.InMemoryAccounts(), m.InMemoryIssuer()
    service = m.EntitlementService(store, issuer)
    service.open_account("a", seats)
    service.open_account("b", 1)
    return service, store, issuer


def reject_without_change(action, store, issuer):
    before = (repr(store.accounts), repr(store.commands), tuple(store.events), tuple(issuer.issued))
    try:
        action()
    except (ValueError, KeyError):
        pass
    else:
        raise AssertionError("invalid request accepted")
    after = (repr(store.accounts), repr(store.commands), tuple(store.events), tuple(issuer.issued))
    assert before == after, "rejected request changed state"


def baseline(m):
    svc, store, issuer = rig(m, 1)
    one = svc.assign("a", "alice", "x")
    assert svc.assign("a", "alice", "x") == one
    svc.assign("b", "bob", "x")
    reject_without_change(lambda: svc.assign("a", "eve", "x"), store, issuer)
    reject_without_change(lambda: svc.assign("a", "eve", "y"), store, issuer)
    svc.release("a", "alice", "z")
    svc.release("a", "alice", "z")
    assert len(store.events) == 3 and not store.accounts["a"].users


def exchange_full(m):
    svc, store, _ = rig(m, 1)
    svc.assign("a", "alice", "assign")
    result = svc.exchange("a", "alice", "bob", "swap")
    assert result == m.Assignment("a", "bob", "swap")
    assert set(store.accounts["a"].users) == {"bob"} and store.accounts["a"].seats == 1
    assert [e.name for e in store.events] == ["Assigned", "Exchanged"]


def exchange_reject(m):
    svc, store, issuer = rig(m)
    svc.assign("a", "alice", "assign")
    for args in [("a", "missing", "bob", "x"), ("a", "alice", "alice", "y"),
                 ("a", "alice", "", "z"), ("missing", "alice", "bob", "q")]:
        reject_without_change(lambda a=args: svc.exchange(*a), store, issuer)
    svc.assign("a", "bob", "second")
    reject_without_change(lambda: svc.exchange("a", "alice", "bob", "third"), store, issuer)


def exchange_replay(m):
    svc, store, issuer = rig(m, 1)
    svc.assign("a", "alice", "same")
    result = svc.exchange("a", "alice", "bob", "swap")
    count = len(store.events)
    assert svc.exchange("a", "alice", "bob", "swap") == result
    assert len(store.events) == count and set(store.accounts["a"].users) == {"bob"}
    for args in [("a", "bob", "alice", "swap"), ("a", "bob", "alice", "same")]:
        reject_without_change(lambda a=args: svc.exchange(*a), store, issuer)
    svc.assign("b", "other", "swap")  # request identity is account-scoped


def shrink_exact(m):
    svc, store, _ = rig(m, 3)
    for i in range(3):
        svc.assign("a", f"u{i}", f"assign-{i}")
    result = svc.shrink("a", 1, ("u2", "u0"), "shrink")
    assert result == ("u2", "u0")
    assert store.accounts["a"].seats == 1 and set(store.accounts["a"].users) == {"u1"}
    assert store.events[-1] == m.Event("Shrunk", "a", "shrink", "u2,u0")
    assert svc.shrink("a", 1, ("u2", "u0"), "shrink") == result
    assert [e.name for e in store.events].count("Shrunk") == 1


def shrink_reject(m):
    svc, store, issuer = rig(m, 3)
    for i in range(3):
        svc.assign("a", f"u{i}", f"assign-{i}")
    bad = [("a", 2, (), "x"), ("a", 2, ("u0", "u0"), "y"),
           ("a", 2, ("unknown",), "z"), ("a", 0, ("u0", "u1", "u2"), "q"),
           ("a", 4, (), "r"), ("a", True, (), "s"), ("missing", 1, (), "t"),
           ("a", 2, ["u0"], "list-is-not-a-tuple")]
    for args in bad:
        reject_without_change(lambda a=args: svc.shrink(*a), store, issuer)
    svc.shrink("a", 2, ("u0",), "valid")
    reject_without_change(lambda: svc.shrink("a", 1, ("u1",), "valid"), store, issuer)


def shrink_preserves_history(m):
    svc, store, issuer = rig(m, 2)
    svc.assign("a", "alice", "assign-a")
    svc.assign("a", "charlie", "assign-c")
    historical = svc.exchange("a", "alice", "bob", "exchange")
    svc.shrink("a", 1, ("bob",), "shrink")
    assert svc.exchange("a", "alice", "bob", "exchange") == historical
    assert set(store.accounts["a"].users) == {"charlie"}
    reject_without_change(lambda: svc.assign("a", "bob", "new"), store, issuer)


def issue_normal(m):
    svc, store, issuer = rig(m, 1)
    svc.assign("a", "alice", "assign")
    receipt = svc.issue_access("a", "alice", "issue")
    assert receipt == m.IssueReceipt("token-1", "a", "alice", "issue")
    assert issuer.lookup("a", "issue") == (receipt,)
    assert store.events[-1] == m.Event("AccessIssued", "a", "issue", "alice")
    svc.release("a", "alice", "release")
    assert svc.issue_access("a", "alice", "issue") == receipt
    assert len(issuer.issued) == 1 and [e.name for e in store.events].count("AccessIssued") == 1


def issue_lost_ack(m):
    svc, store, issuer = rig(m, 1)
    svc.assign("a", "alice", "assign")
    issuer.lose_next_ack = True
    try:
        receipt = svc.issue_access("a", "alice", "issue")
    except TimeoutError:
        receipt = svc.issue_access("a", "alice", "issue")
    assert receipt == issuer.issued[0]
    assert len(issuer.issued) == 1, "acknowledgement loss duplicated issuance"
    assert svc.issue_access("a", "alice", "issue") == receipt
    assert len(issuer.issued) == 1 and [e.name for e in store.events].count("AccessIssued") == 1


def issue_pre_effect_timeout(m):
    svc, store, issuer = rig(m, 1)
    svc.assign("a", "alice", "assign")
    issuer.fail_before_issue = True
    try:
        svc.issue_access("a", "alice", "issue")
    except TimeoutError:
        pass
    else:
        raise AssertionError("pre-effect timeout was treated as completed issuance")
    assert not issuer.issued and ("a", "issue") not in store.commands
    assert not any(event.name == "AccessIssued" for event in store.events)
    receipt = svc.issue_access("a", "alice", "issue")
    assert receipt == m.IssueReceipt("token-1", "a", "alice", "issue")
    assert len(issuer.issued) == 1 and [e.name for e in store.events].count("AccessIssued") == 1


def issue_conflicting_lookup(m):
    svc, store, issuer = rig(m, 1)
    svc.assign("a", "alice", "assign")
    issuer.issued.append(m.IssueReceipt("foreign", "a", "bob", "issue"))
    reject_without_change(lambda: svc.issue_access("a", "alice", "issue"), store, issuer)
    assert ("a", "issue") not in store.commands


def issue_multiple_lookup(m):
    svc, store, issuer = rig(m, 1)
    svc.assign("a", "alice", "assign")
    issuer.issued.extend([m.IssueReceipt("first", "a", "alice", "issue"),
                          m.IssueReceipt("second", "a", "alice", "issue")])
    reject_without_change(lambda: svc.issue_access("a", "alice", "issue"), store, issuer)
    assert ("a", "issue") not in store.commands


def issue_rejection(m):
    svc, store, issuer = rig(m, 1)
    reject_without_change(lambda: svc.issue_access("a", "alice", "never"), store, issuer)
    svc.assign("a", "alice", "assign")
    reject_without_change(lambda: svc.issue_access("a", "alice", "assign"), store, issuer)
    svc.issue_access("a", "alice", "issued")
    reject_without_change(lambda: svc.issue_access("a", "bob", "issued"), store, issuer)


CASES = {
    "B": [("baseline.identity-and-capacity", baseline),
          ("B.atomic-full-seat-exchange", exchange_full),
          ("B.invalid-exchange-no-effects", exchange_reject),
          ("B.account-scoped-replay", exchange_replay)],
    "C": [("C.exact-ordered-displacement", shrink_exact),
          ("C.invalid-shrink-no-effects", shrink_reject),
          ("C.prior-exchange-replay-after-shrink", shrink_preserves_history)],
    "D": [("D.issued-token-identity-and-replay", issue_normal),
          ("D.acknowledgement-loss-reconciliation", issue_lost_ack),
          ("D.pre-effect-timeout-remains-retryable", issue_pre_effect_timeout),
          ("D.conflicting-issuer-user-rejected", issue_conflicting_lookup),
          ("D.multiple-issuer-tokens-rejected", issue_multiple_lookup),
          ("D.rejected-issue-no-effects", issue_rejection)],
}


def assess(source: Path, stage: str) -> dict:
    if not (source / "service.py").is_file():
        raise ValueError("candidate source/service.py missing")
    sha = source_sha256(source)
    sys.path.insert(0, str(source.resolve()))
    sys.modules.pop("service", None)
    try:
        module = importlib.import_module("service")
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
        return {"system": "entitlement", "stage": stage, "source_sha256": sha,
                "valid": True, "passed": 0, "failed": 1, "total": 1,
                "findings": {"candidate.import": {"status": "fail", "detail": detail}},
                "checks": [{"id": "candidate.import", "status": "fail", "detail": detail}]}
    due = CASES["B"] + (CASES["C"] if stage in "CD" else []) + (CASES["D"] if stage == "D" else [])
    findings = []
    for name, case in due:
        try:
            case(module)
        except Exception as exc:
            findings.append({"id": name, "status": "fail", "detail": f"{type(exc).__name__}: {exc}"})
        else:
            findings.append({"id": name, "status": "pass", "detail": ""})
    return {"system": "entitlement", "stage": stage, "source_sha256": sha,
            "valid": True, "passed": sum(c["status"] == "pass" for c in findings),
            "failed": sum(c["status"] == "fail" for c in findings),
            "total": len(findings), "checks": findings,
            "findings": {c["id"]: {"status": c["status"], "detail": c["detail"]}
                         for c in findings}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--stage", choices=("B", "C", "D"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = assess(args.source, args.stage)
    except ValueError as exc:
        result = {"system": "entitlement", "stage": args.stage, "source_sha256": None,
                  "valid": False, "invalid_kind": "candidate_source", "passed": 0,
                  "failed": 0, "invalid": 1, "total": 1,
                  "findings": {"candidate.source": {"status": "invalid", "detail": str(exc)}},
                  "checks": [{"id": "candidate.source", "status": "invalid", "detail": str(exc)}]}
    except Exception as exc:
        result = {"system": "entitlement", "stage": args.stage, "source_sha256": None,
                  "valid": False, "invalid_kind": "assessor_error", "passed": 0,
                  "failed": 0, "invalid": 1, "total": 1,
                  "findings": {"host.assessor-error": {"status": "invalid", "detail": f"{type(exc).__name__}: {exc}"}},
                  "checks": [{"id": "host.assessor-error", "status": "invalid", "detail": f"{type(exc).__name__}: {exc}"}],
                  "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 2 if result.get("invalid_kind") == "assessor_error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
