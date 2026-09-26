"""Compare authored EAL reasoning with opt-in ASPIC+ compilation on one collection.

All findings come from the pinned synthetic API load-test fixture. The compiler
derives its theory from checked EAL routes; the source contains no formal theory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from eal.runtime import ReasoningService
from eal.aspic_visualisation import render_aspic_html


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "aspic-compiled.eal").read_text(encoding="utf-8")
CONTEXT = {"service": "orders-api", "build_id": "demo-build-42", "dataset": "synthetic"}
NOW = "2026-09-25T10:00:30Z"
GOAL = "run_passes"
ROUTES = ("primary_run", "independent_probe")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visualise", type=Path,
                        help="Write a standalone ASPIC+ argument view to this HTML file")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="eal-compiled-aspic-demo-") as folder:
        service = ReasoningService(ROOT, HERE / "aspic-tools.toml",
                                   Path(folder) / "runs.sqlite3")
        validation = service.validate(SOURCE)
        assert validation["valid"], validation

        collection = service.collect(SOURCE, CONTEXT)
        record_status = {name: record["status"]
                         for name, record in collection["records"].items()}
        assert all(status == "ok" for status in record_status.values()), collection

        authored = service.reason(SOURCE, CONTEXT, collection["collection_id"], NOW)
        compiled = service.compile_aspic(SOURCE, CONTEXT, collection["collection_id"],
                                         GOAL, NOW)
        assert compiled["source_digest"] == authored["source_digest"]
        assert compiled["authored_claim_status"] == authored["claims"][GOAL]["status"]
        assert compiled["authored_claim_status"] == compiled["claim_status"] == "supported"
        assert compiled["formal"]["grounded_status"] == "accepted"
        assert authored["arguments"]["primary_run"]["status"] == "contested"
        assert authored["arguments"]["independent_probe"]["status"] == "supported"
        assert compiled["routes"]["primary_run"]["status"] == "rejected"
        assert compiled["routes"]["independent_probe"]["status"] == "accepted"
        assert compiled["source_map"]["arguments"]["report_arg"]["rule_kind"] == "strict"
        assert compiled["source_map"]["arguments"]["independent_probe"]["rank"] == 700
        assert compiled["source_map"]["evidence"]["probe_record"]["rank"] == 700

        argument_by_id = {item["id"]: item for item in compiled["formal"]["arguments"]}
        primary_rule = compiled["source_map"]["arguments"]["primary_run"]["rule_id"]
        gap_rule = compiled["source_map"]["objections"]["primary_trace_gap"]["rule_id"]
        assert any(
            defeat["kind"] == "undercut"
            and argument_by_id[defeat["attacker"]]["rule_id"] == gap_rule
            and argument_by_id[defeat["subargument"]]["rule_id"] == primary_rule
            for defeat in compiled["formal"]["defeats"]
        ), compiled["formal"]["defeats"]

        if args.visualise is not None:
            target = args.visualise.resolve()
            target.write_text(render_aspic_html(compiled), encoding="utf-8")

        print(json.dumps({
            "dataset": "synthetic",
            "collection_status": record_status,
            "authored_claim_status": authored["claims"][GOAL]["status"],
            "compiled_claim_status": compiled["claim_status"],
            "formal_status": compiled["formal"]["grounded_status"],
            "profile": compiled["profile"],
            "routes": {
                name: {"authored_status": authored["arguments"][name]["status"],
                       "compiled": compiled["routes"][name]}
                for name in ROUTES
            },
            "defeats": compiled["formal"]["defeats"],
            "source_map": compiled["source_map"],
            **({"visualisation": str(target)} if args.visualise is not None else {}),
        }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
