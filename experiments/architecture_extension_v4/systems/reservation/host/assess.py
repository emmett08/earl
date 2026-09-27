"""Host-only cumulative reservation assessor; excluded from coding clones."""

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


def rig(m):
    calendar = m.InMemoryCalendar()
    svc = m.ReservationService(calendar)
    for room in ("amber", "blue", "green"):
        svc.add_room(room)
    return svc, calendar


def snapshot(calendar):
    return (repr(calendar.bookings), repr(calendar.commands), tuple(calendar.events))


def reject_without_change(action, calendar):
    before = snapshot(calendar)
    try:
        action()
    except (ValueError, KeyError, TypeError):
        pass
    else:
        raise AssertionError("invalid request accepted")
    assert snapshot(calendar) == before, "rejected request changed calendar state"


def baseline(m):
    svc, calendar = rig(m)
    first = svc.reserve("amber", 10, 20, "alice", "r")
    assert svc.reserve("amber", 10, 20, "alice", "r") == first
    svc.reserve("amber", 20, 30, "bob", "r")
    reject_without_change(lambda: svc.reserve("amber", 19, 25, "eve", "e"), calendar)
    reject_without_change(lambda: svc.cancel(first.booking_id, "eve", "c"), calendar)
    svc.cancel(first.booking_id, "alice", "c")
    svc.cancel(first.booking_id, "alice", "c")
    assert len(calendar.events) == 3


def bundle_atomic(m):
    svc, calendar = rig(m)
    blocker = svc.reserve("green", 10, 20, "other", "block")
    reject_without_change(lambda: svc.reserve_bundle(("amber", "green"), 15, 25, "alice", "bundle"), calendar)
    result = svc.reserve_bundle(("amber", "blue"), 10, 20, "alice", "bundle")
    assert result == m.BundleReceipt("alice", "bundle", result.booking_ids, ("amber", "blue"), 10, 20)
    assert len(result.booking_ids) == 2 and result.booking_ids[0] != result.booking_ids[1]
    assert [(calendar.bookings[i].room_id, calendar.bookings[i].start, calendar.bookings[i].end)
            for i in result.booking_ids] == [("amber", 10, 20), ("blue", 10, 20)]
    assert calendar.events[-1] == m.Event("BundleReserved", "alice", "bundle", result.booking_ids)
    assert blocker.active


def bundle_invalid(m):
    svc, calendar = rig(m)
    bad = [((), 10, 20, "a", "x"), (("amber", "amber"), 10, 20, "a", "y"),
           (("unknown",), 10, 20, "a", "z"), (("amber",), 20, 20, "a", "p"),
           (("amber",), True, 20, "a", "q"), (("amber",), 10, 20, "", "r"),
           (["amber"], 10, 20, "a", "list-is-not-a-tuple")]
    for args in bad:
        reject_without_change(lambda a=args: svc.reserve_bundle(*a), calendar)
    svc.reserve_bundle(("amber",), 10, 20, "a", "valid")
    reject_without_change(lambda: svc.reserve_bundle(("blue",), 10, 20, "a", "valid"), calendar)


def bundle_replay(m):
    svc, calendar = rig(m)
    result = svc.reserve_bundle(("blue", "amber"), 0, 10, "a", "same")
    before = snapshot(calendar)
    assert svc.reserve_bundle(("blue", "amber"), 0, 10, "a", "same") == result
    assert snapshot(calendar) == before
    other = svc.reserve_bundle(("green",), 0, 10, "b", "same")
    assert len(other.booking_ids) == 1
    reject_without_change(lambda: svc.reserve("green", 0, 10, "a", "same"), calendar)


def move_excludes_only_self(m):
    svc, calendar = rig(m)
    result = svc.reserve_bundle(("amber", "blue"), 10, 20, "alice", "bundle")
    svc.reserve("green", 10, 30, "other", "separate")
    moved = svc.move_bundle("alice", "bundle", 15, 25, "move")
    assert moved == m.BundleReceipt("alice", "move", result.booking_ids, result.room_ids, 15, 25)
    assert all((calendar.bookings[i].start, calendar.bookings[i].end) == (15, 25)
               for i in result.booking_ids)
    assert calendar.events[-1] == m.Event("BundleMoved", "alice", "move", result.booking_ids)
    assert (result.start, result.end) == (10, 20), "historical receipt overwritten"


def move_conflict_rollback(m):
    svc, calendar = rig(m)
    result = svc.reserve_bundle(("amber", "blue"), 10, 20, "alice", "bundle")
    svc.reserve("blue", 20, 40, "other", "block")
    for args in [("alice", "bundle", 15, 25, "fail"),
                 ("alice", "bundle", 10, 20, "same-interval"),
                 ("alice", "missing", 30, 40, "missing")]:
        reject_without_change(lambda a=args: svc.move_bundle(*a), calendar)
    moved = svc.move_bundle("alice", "bundle", 0, 10, "move")
    assert moved.booking_ids == result.booking_ids
    reject_without_change(lambda: svc.move_bundle("alice", "bundle", 30, 40, "move"), calendar)


def move_replay(m):
    svc, calendar = rig(m)
    receipt = svc.reserve_bundle(("amber", "blue"), 5, 15, "a", "b")
    first_move = svc.move_bundle("a", "b", 15, 25, "m1")
    svc.move_bundle("a", "b", 25, 35, "m2")
    before = snapshot(calendar)
    assert svc.move_bundle("a", "b", 15, 25, "m1") == first_move
    assert snapshot(calendar) == before
    assert svc.reserve_bundle(("amber", "blue"), 5, 15, "a", "b") == receipt


def cancel_current_bundle(m):
    svc, calendar = rig(m)
    original = svc.reserve_bundle(("amber", "blue"), 10, 20, "a", "b")
    moved = svc.move_bundle("a", "b", 30, 40, "m")
    result = svc.cancel_bundle("a", "b", "c")
    assert result == m.CancelReceipt("a", "c", original.booking_ids)
    assert not any(calendar.bookings[i].active for i in original.booking_ids)
    assert calendar.events[-1] == m.Event("BundleCancelled", "a", "c", original.booking_ids)
    svc.reserve_bundle(("amber", "blue"), 30, 40, "other", "reuse")
    assert svc.cancel_bundle("a", "b", "c") == result
    assert svc.move_bundle("a", "b", 30, 40, "m") == moved
    assert svc.reserve_bundle(("amber", "blue"), 10, 20, "a", "b") == original
    assert [e.name for e in calendar.events].count("BundleCancelled") == 1


def cancel_partial_reject(m):
    svc, calendar = rig(m)
    result = svc.reserve_bundle(("amber", "blue"), 10, 20, "a", "b")
    reject_without_change(lambda: svc.cancel_bundle("b", "b", "wrong"), calendar)
    reject_without_change(lambda: svc.cancel_bundle("a", "missing", "wrong"), calendar)
    svc.cancel(result.booking_ids[0], "a", "individual")
    reject_without_change(lambda: svc.cancel_bundle("a", "b", "partial"), calendar)
    assert calendar.bookings[result.booking_ids[1]].active
    reject_without_change(lambda: svc.cancel_bundle("a", "b", "individual"), calendar)


CASES = {
    "B": [("baseline.half-open-availability-and-identity", baseline),
          ("B.all-or-none-cross-room-conflict", bundle_atomic),
          ("B.invalid-bundle-no-effects", bundle_invalid),
          ("B.historical-replay-and-customer-scope", bundle_replay)],
    "C": [("C.self-exclusion-and-stable-booking-ids", move_excludes_only_self),
          ("C.other-conflict-rejection-and-rollback", move_conflict_rollback),
          ("C.move-replay-after-later-move", move_replay)],
    "D": [("D.cancel-moved-bundle-and-historical-replay", cancel_current_bundle),
          ("D.partial-bundle-and-identity-rejections", cancel_partial_reject)],
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
        return {"system": "reservation", "stage": stage, "source_sha256": sha,
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
    return {"system": "reservation", "stage": stage, "source_sha256": sha,
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
        result = {"system": "reservation", "stage": args.stage, "source_sha256": None,
                  "valid": False, "invalid_kind": "candidate_source", "passed": 0,
                  "failed": 0, "invalid": 1, "total": 1,
                  "findings": {"candidate.source": {"status": "invalid", "detail": str(exc)}},
                  "checks": [{"id": "candidate.source", "status": "invalid", "detail": str(exc)}]}
    except Exception as exc:
        result = {"system": "reservation", "stage": args.stage, "source_sha256": None,
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
