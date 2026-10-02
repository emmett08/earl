#!/usr/bin/env python3
"""Reconstruct supplemental coding and verify the preserved baseline boundary."""
from collections import Counter
from pathlib import Path
import gzip
import hashlib
import importlib.util
import json
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    directory = ROOT / "followup/measurement"
    manifest = json.loads((directory / "manifest.json").read_text())
    baseline = json.loads((ROOT / "data/manifest.json").read_text())
    assert manifest["primary_archive_sha256"] == baseline["archive_sha256"]
    assert manifest["primary_annotated_rows_sha256"] == baseline["source_files"]["annotated-rows.json"]
    for name, record in manifest["files"].items():
        raw = (directory / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == record["sha256"], name
        unpacked = gzip.decompress(raw) if name.endswith(".gz") else raw
        assert hashlib.sha256(unpacked).hexdigest() == record["source_sha256"], name
    spec = importlib.util.spec_from_file_location("retained_supplemental_review", ROOT.parent / "scripts/review_pilot_measurement.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_raw = gzip.decompress((ROOT / "data/annotated-rows.json.gz").read_bytes())
    with tempfile.TemporaryDirectory(prefix="eal-jss-measurement-") as temporary:
        rows_path = Path(temporary) / "annotated-rows.json"
        rows_path.write_bytes(original_raw)
        reconstructed = module.review(directory, rows_path)
    saved = json.loads((directory / "supplemental-review.json").read_text())
    for key, value in reconstructed.items():
        assert saved[key] == value, f"Supplemental review mismatch: {key}"
    original = json.loads(original_raw)
    derived = json.loads(gzip.decompress((directory / "supplemental-annotated-rows.json.gz").read_bytes()))
    assert len(original) == len(derived) == 384
    for old_row, new_row in zip(original, derived):
        assert {k: v for k, v in old_row.items() if k != "sessions"} == {
            k: v for k, v in new_row.items() if k != "sessions"}, "Supplemental trajectory metadata changed"
    originals = {s["session_id"]: (row, s) for row in original for s in row["sessions"]}
    derived_sessions = {s["session_id"]: (row, s) for row in derived for s in row["sessions"]}
    assert len(originals) == len(derived_sessions) == 4224 and set(originals) == set(derived_sessions)
    amended = {r["session_id"]: r for r in reconstructed["flagged_records"]
               if r["supplemental_code"] != r["original_code"]}
    assert len(amended) == 6 and reconstructed["sample_n"] == 169
    totals = {arm: Counter() for arm in ["ordinary", "eal"]}
    ambiguities = 0
    for ident, (row, session) in derived_sessions.items():
        original_row, old = originals[ident]
        assert row["arm"] == original_row["arm"] and row["pair_id"] == original_row["pair_id"]
        if ident not in amended:
            assert session == old, f"Unreviewed session changed: {ident}"
        else:
            assert session["annotation"]["decision_code"] == amended[ident]["supplemental_code"]
            for key in set(session) | set(old):
                if key not in {"annotation", "annotation_history", "answer", "score"}:
                    assert session[key] == old[key], (ident, key)
            assert session["annotation_history"][-1] == old["annotation"]
            assert session["score"]["reference"] == old["score"]["reference"]
        code = session["annotation"]["decision_code"]
        ambiguities += code == "ambiguous"
        expected = session["score"]["reference"]["decision"]
        outcome = None if code == "ambiguous" else code == expected
        assert session["score"]["task_match"] is outcome
        if session["session"] > 0:
            totals[row["arm"]]["unknown" if outcome is None else "match" if outcome else "mismatch"] += 1
    assert ambiguities == 19
    primary_analysis = json.loads(gzip.decompress((ROOT / "data/analysis-annotated.json.gz").read_bytes()))
    supplemental_analysis = json.loads((directory / "supplemental-analysis.json").read_text())
    assert supplemental_analysis["pending_task_annotations"] == 19
    assert supplemental_analysis["status"] == "pending_annotation"
    assert supplemental_analysis["practical_decision"]["status"] == "pilot_only"
    remaining = json.loads((directory / "remaining-masked-packet.json").read_text())
    masked = json.loads((directory / "masked-items.json").read_text())
    texts = {item["id"]: item["text"] for item in masked["items"]}
    assert remaining["status"] == "prepared_unreviewed" and len(remaining["items"]) == 19
    assert remaining["source_sha256"] == hashlib.sha256((directory / "masked-items.json").read_bytes()).hexdigest()
    for item in remaining["items"]:
        assert item["text"] == texts[item["id"]]
        assert all(value is None for value in item["review"].values()), "Prepared packet contains an unreported review"
    for arm, stages in primary_analysis["resources"].items():
        for stage, values in stages.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    assert supplemental_analysis["resources"][arm][stage][key] == value, (arm, stage, key)
            else:
                assert supplemental_analysis["resources"][arm][stage] == values, (arm, stage)
    for arm, counts in totals.items():
        assert dict(counts) == {k: v for k, v in reconstructed["supplemental_recipient_reference_agreement"][arm].items()
                                if k in {"match", "mismatch", "unknown"}}
    print(f"169 supplemental reviews, six separate amendments and all 4,224 unchanged raw answers/accounting identities: passed. Conditional recipient totals: {dict((k, dict(v)) for k, v in totals.items())}")


if __name__ == "__main__":
    main()
