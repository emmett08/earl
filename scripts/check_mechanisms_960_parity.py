#!/usr/bin/env python3
"""Execute 24 roots × four input/gate variants × two bounded checker paths.

The standalone brief-rule calculation is separately coded in the fixture
validator, but both paths and cases originated with one author. Digest
matching here demonstrates a synthetic gate; it does not authenticate an
external acquisition, an author or a physical measurement.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from eal.runtime import load_method_registry  # noqa: E402
import run_mechanisms_960 as study  # noqa: E402

VARIANTS = ("intact", "wrong_scope", "stale_replayed", "hash_tampered")


def _variants(root: dict) -> dict[str, dict]:
    base = root["valid_records"]
    wrong = deepcopy(base)
    first = (root.get("reference_rule", {}).get("primary")
             if root["family"] == "objection_defence" else next(iter(wrong)))
    wrong[first]["context"] = {**wrong[first]["context"], "unrelated_scope": "other-task"}
    stale = deepcopy(base)
    instant = datetime.fromisoformat(root["now"].replace("Z", "+00:00"))
    stale[first]["observed_at"] = (instant - timedelta(seconds=3601)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {"intact": base, "wrong_scope": wrong, "stale_replayed": stale,
            "hash_tampered": base}


def _packet(root: dict, records: dict) -> dict:
    return {"source_sha256": study.digest(root["representations"]["eal"].encode("utf-8")),
            "semantic_sha256": study.digest(root["representations"]["json"]),
            "records_sha256": study.digest(records), "context": root["context"],
            "claim": root["claim"], "assessed_at": root["now"],
            "method_registry_fingerprint": load_method_registry(root.get("method_factory")).fingerprint}


def gate(root: dict, records: dict, packet: dict) -> bool:
    return packet == _packet(root, records)


def run_parity(roots: list[dict], fixtures: Path) -> dict:
    validator = runpy.run_path(str(study.local_file(fixtures, "validate_fixtures.py")))
    eal_status = validator["eal_status"]
    reference_status = validator["reference_status"]
    result = []
    for root in roots:
        for variant, records in _variants(root).items():
            packet = _packet(root, records)
            if variant == "hash_tampered":
                packet = {**packet, "records_sha256": "0" * 64}
            for system in ("eal", "standalone_brief_rule"):
                started = time.monotonic()
                if not gate(root, records, packet):
                    outcome = "refused"
                elif system == "eal":
                    outcome, _collection = eal_status(
                        root, records, source_text=root["representations"]["eal"])
                else:
                    outcome = reference_status(root, records)
                result.append({"root_id": root["id"], "family": root["family"], "variant": variant,
                               "system": system, "status": outcome, "gate_accepted": outcome != "refused",
                               "seconds": time.monotonic() - started,
                               "records_sha256": study.digest(records),
                               "packet_sha256": study.digest(packet)})
    if len(result) != 192:
        raise ValueError("Expected exactly 192 deterministic executions")
    pair = {}
    for row in result:
        key = (row["root_id"], row["variant"])
        pair.setdefault(key, {})[row["system"]] = row["status"]
    if (len(pair) != 96 or any(set(systems) != {"eal", "standalone_brief_rule"}
                               or len(set(systems.values())) != 1 for systems in pair.values())):
        raise ValueError("EAL and separate brief-rule checker disagree")
    for (root_id, variant), systems in pair.items():
        status = systems["eal"]
        if variant == "intact" and status != next(root["valid_status"] for root in roots if root["id"] == root_id):
            raise ValueError("Intact checker reference failed")
        if variant in {"wrong_scope", "stale_replayed"} and status != "unsupported":
            raise ValueError(f"Wrong-scope/stale record was admitted: {root_id}/{variant} -> {status}")
        if variant == "hash_tampered" and status != "refused":
            raise ValueError("Tampered packet passed the common gate")
    return {"schema": "eal2-mechanisms-960-parity/2", "roots": 24, "variants": list(VARIANTS),
            "executions": 192, "paired_variants": 96, "discordance": 0,
            "tampered_accepted": 0, "gate_kind": "same synthetic digest/identity gate for both paths",
            "comparator_kind": "separately coded, same-author brief-rule checker",
            "records": result}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    frozen = study.freeze(args.plan)
    report = run_parity(frozen["roots"], study.local_file(args.plan.resolve().parent, frozen["plan"]["fixtures"]).parent)
    report["freeze_sha256"] = frozen["freeze_sha256"]
    study.write(args.output, report)
    print(json.dumps({k: report[k] for k in ("executions", "discordance", "tampered_accepted")}, sort_keys=True))


if __name__ == "__main__":
    main()
