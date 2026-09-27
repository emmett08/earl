"""Focused safety and end-to-end checks for host-bound current-source packets."""

from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import host
from snapshot_probe import _boundary_check, tree_manifest


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "experiments" / "architecture_extension_v2" / "results" / "snapshots" / "a"
BRIEF = Path(__file__).resolve().parent / "study" / "features" / "R-B.md"


class CurrentSnapshotHostTests(unittest.TestCase):
    def test_plain_and_mcp_share_observations_with_separate_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            common = {"baseline": BASE, "candidate": BASE, "family": "R", "feature": "B",
                      "disable_cache": False}
            plain = host.assess(Namespace(**common, arm="P1", state_dir=root / "plain"))
            argued = host.assess(Namespace(**common, arm="P2", state_dir=root / "argued"))
            eager = host.assess(Namespace(**common, arm="P2", eager_explain=True,
                                          state_dir=root / "eager"))
            p1 = json.loads((root / "plain" / "packet-P1.json").read_text())
            p2 = json.loads((root / "argued" / "packet-P2.json").read_text())
            self.assertEqual(plain["observation_digest"], argued["observation_digest"])
            self.assertEqual(p1["checks"], p2["checks"])
            self.assertEqual(p1["guidance"], p2["guidance"])
            self.assertEqual(p1["verification_choice"], p2["verification_choice"])
            self.assertEqual(p1["public_impact_absent"], p2["public_impact_absent"])
            self.assertEqual(p2["decisive_routes"],
                             json.loads((root / "eager" / "packet-P2.json").read_text())["decisive_routes"])
            self.assertFalse(argued["explanation_fetched"])
            self.assertTrue(eager["explanation_fetched"])
            self.assertNotIn("eal.sqlite3", [p.name for p in (root / "plain").iterdir()])
            self.assertTrue((root / "argued" / "mcp-wire.json").is_file())
            wire = json.loads((root / "argued" / "mcp-wire.json").read_text())
            methods = [json.loads(item["utf8_line"]).get("method") for item in wire["messages"]
                       if item["direction"] == "client_to_server"]
            self.assertIn("tools/list", methods)
            self.assertEqual(methods.count("tools/call"), 2)
            self.assertLessEqual(plain["packet_bytes"], 3072)
            self.assertLessEqual(argued["packet_bytes"], 3072)
            self.assertEqual(argued["claim_status"], "supported")
            self.assertFalse((root / "argued" / "workspace" / "study").exists())
            self.assertFalse((root / "argued" / "explanation.json").exists())
            self.assertEqual(host.explain(Namespace(state_dir=root / "argued",
                                                    assessment_id=argued["assessment_id"],
                                                    output=None))["packet"]["assessment_id"],
                             argued["assessment_id"])
            self.assertTrue((root / "argued" / "explanation.json").exists())
            self.assertTrue((root / "argued" / "mcp-explain-wire.json").exists())

    def test_changed_boundary_is_migration_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "candidate"
            shutil.copytree(BASE, candidate)
            (candidate / "fulfilment" / "ports.py").unlink()
            finding = _boundary_check(candidate, "R", "B")
            self.assertFalse(finding["passed"])
            self.assertIn("fulfilment/ports.py", finding["missing_boundary_files"])

    def test_migration_objection_fetches_scoped_explanation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "candidate"
            shutil.copytree(BASE, candidate)
            service = candidate / "fulfilment" / "service.py"
            source = service.read_text(encoding="utf-8")
            self.assertIn("pricing: PricingPort", source)
            service.write_text(source.replace("pricing: PricingPort", "pricing: object", 1),
                               encoding="utf-8")
            metrics = host.assess(Namespace(baseline=BASE, candidate=candidate, family="R",
                                            feature="B", arm="P2", disable_cache=False,
                                            state_dir=root / "host"))
            packet = json.loads((root / "host" / "packet-P2.json").read_text())
            self.assertTrue(metrics["explanation_fetched"])
            self.assertEqual(packet["claim_status"], "supported")
            self.assertIn("migration", packet["verification_choice"])
            self.assertTrue(any(item["id"] == "boundary_migration"
                                for item in packet["objections"]))

    def test_exposure_binds_visible_sidecars_and_omits_sealed_assessor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packet = root / "packet.json"
            source_sha = tree_manifest(BASE)["tree_sha256"]
            host.write_json(packet, {"schema": "architecture-v3-plain-packet/1",
                                     "family": "R", "feature": "B", "candidate_sha256": source_sha})
            options = Namespace(source=BASE, brief=BRIEF, family="R", feature="B",
                                arm="P1", packet=packet, destination=root / "trial",
                                record=root / "exposure.json")
            record = host.prepare(options)
            self.assertEqual(record["source_tree_sha256"], source_sha)
            self.assertEqual(set(p.name for p in (root / "trial").iterdir()),
                             {"fulfilment", "tests", "ARCHITECTURE.md", "AGENTS.md",
                              "FEATURE.md", "architecture-context.json"})
            self.assertTrue(host.verify_exposure(Namespace(trial=root / "trial",
                                                            record=root / "exposure.json"))["sidecars_intact"])
            clean = host.snapshot(Namespace(trial=root / "trial", record=root / "exposure.json",
                                            destination=root / "clean", manifest=root / "clean-manifest.json"))
            self.assertEqual(clean["source_tree_sha256"], source_sha)
            self.assertFalse(any((root / "clean" / name).exists()
                                 for name in ("AGENTS.md", "FEATURE.md", "architecture-context.json")))
            (root / "trial" / "FEATURE.md").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sidecar changed"):
                host.verify_exposure(Namespace(trial=root / "trial", record=root / "exposure.json"))


if __name__ == "__main__":
    unittest.main()
