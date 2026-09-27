"""Deterministic local checks for allocation, lineage, and failure capture."""

from __future__ import annotations

import json
import random
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import runner
import runner_capture
from runner_capture import tree_digest, tree_entries, usage_from_jsonl


ASSESSOR = '''import argparse, json
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--source',type=Path,required=True)
p.add_argument('--stage',required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
due='BCD'[:'BCD'.index(a.stage)+1]
ok=all((a.source/('stage-'+s+'.txt')).is_file() for s in due)
data={'findings': {'lineage': {'status': 'pass' if ok else 'fail', 'detail': due}},
      'passed': int(ok), 'failed': int(not ok), 'invalid':0}
a.output.write_text(json.dumps(data))
'''
STUB = '''import json,os
from pathlib import Path
if os.environ.get('EARL_TASK')=='decision':
    assert 'ACTION' in Path('FEATURE.md').read_text()
    print(json.dumps({'action':'inspect_existing'}))
    raise SystemExit(0)
s=os.environ['EARL_STAGE']
prompt=Path('FEATURE.md').read_text()
assert 'current='+s in prompt
assert all('future='+other not in prompt for other in 'BCD' if other!=s)
assert not Path('assess.py').exists()
assert not Path('manifest.json').exists()
for old in 'BCD'[:'BCD'.index(s)]: assert Path('stage-'+old+'.txt').is_file()
Path('stage-'+s+'.txt').write_text(s)
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':4,'output_tokens':2}}))
'''


class RunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixtures = self.root / "systems"
        self.decision_cases = self.root / "decision_cases"
        self.systems = ("fulfilment", "entitlement", "reservation")
        for system in self.systems:
            folder = self.fixtures / system
            (folder / "source").mkdir(parents=True)
            (folder / "source" / "baseline.py").write_text("VALUE = 1\n")
            (folder / "host").mkdir()
            (folder / "host/assess.py").write_text(ASSESSOR)
            (folder / "features").mkdir()
            for stage in "BCD":
                (folder / "features" / f"{stage}.md").write_text(f"current={stage}\n")
            for case in ("clean", "defeated"):
                case_source = self.decision_cases / system / case / "source"
                case_source.mkdir(parents=True)
                (case_source / "baseline.py").write_text("VALUE = 1\n")
        (self.decision_cases / "cases.json").write_text(json.dumps({
            "systems": {system: {case: {"evidence_schema": {"mode": "smoke"}}
                                for case in ("clean", "defeated")} for system in self.systems}}))
        permutation = random.Random(int("a" * 64, 16))
        blocks = []
        for system in self.systems:
            for rep in (1, 2):
                block_id = f"{system}-{rep:02}"
                arms = ["P0", "P1", "P2"]
                permutation.shuffle(arms)
                blocks.append({"id": block_id, "system": system,
                               "assignments": [{"clone": f"{block_id}-K{i+1}", "arm": arm}
                                               for i, arm in enumerate(arms)]})
        self.manifest = {"schema": runner.SCHEMA, "seed_hex": "a" * 64,
                         "allocation_algorithm": "frozen test permutation",
                         "systems": list(self.systems), "replicate_blocks_per_system": 2,
                         "blocks": blocks, "wall_cap_seconds": 5,
                         "agent": {"model": "synthetic", "effort": "none", "cli_version": "0.154.0"},
                         "evidence_schema": {system: {stage: {"mode": "smoke"}
                                                       for stage in "BCD"} for system in self.systems},
                         "critical_check_ids": {system: {stage: ["lineage"]
                                                         for stage in "BCD"} for system in self.systems},
                         "max_block_high_scenario_usd": "15.00",
                         "decision_probes": {"case_ids": ["clean", "defeated"],
                                             "wall_cap_seconds": 120}}
        self.manifest_path = self.root / "manifest.json"
        self.manifest_path.write_text(json.dumps(self.manifest))
        self.previous_packets = sys.modules.get("packets")

        def generate(source, system, stage, arm, evidence_schema):
            source_hash = tree_digest(tree_entries(source))
            return {"facts": {"source": source_hash, "current": stage}, "guidance": "same guidance",
                    "status": "supported", "selected_action": "proceed",
                    "shared_material_digest": source_hash,
                    "source_tree_sha256": source_hash,
                    **({"formal": {"route": "supported"}} if arm == "P2" else {}),
                    "packet_text": f"{arm} argument presentation"}
        sys.modules["packets"] = types.SimpleNamespace(generate=generate)
        self.previous_decision = sys.modules.get("decision_probe")

        def decision_generate(source, system, case_id, arm, evidence_schema):
            source_hash = tree_digest(tree_entries(source))
            expected = "inspect_existing" if case_id == "clean" else "implement_missing"
            return {"facts": {"case": case_id}, "guidance": "same advice",
                    "status": "supported", "selected_action": expected,
                    "shared_material_digest": source_hash,
                    "source_tree_sha256": source_hash, "expected_action": expected,
                    "allowed_actions": ["inspect_existing", "implement_missing"],
                    "prompt_text": f"ACTION current={case_id} {arm}",
                    **({"formal": {"route": "supported"}} if arm == "P2" else {})}

        def decision_score(response, expected, allowed_actions):
            action = json.loads(response)["action"]
            return {"correct": action == expected, "observed_action": action}
        sys.modules["decision_probe"] = types.SimpleNamespace(
            generate=decision_generate, score=decision_score)

    def tearDown(self) -> None:
        if self.previous_packets is None:
            sys.modules.pop("packets", None)
        else:
            sys.modules["packets"] = self.previous_packets
        if self.previous_decision is None:
            sys.modules.pop("decision_probe", None)
        else:
            sys.modules["decision_probe"] = self.previous_decision
        self.temp.cleanup()

    def test_block_has_three_independent_complete_lineages_with_only_current_brief(self):
        output = self.root / "output"
        result = runner.run(self.manifest_path, self.fixtures, output, "stub", "fulfilment-01",
                            [sys.executable, "-c", STUB], self.decision_cases)
        self.assertEqual(result["status"], "completed_smoke_only")
        self.assertEqual(len(result["episodes"]), 9)
        self.assertEqual(len(result["decision_probes"]), 6)
        self.assertEqual({row["case_id"] for row in result["decision_probes"]},
                         {"clean", "defeated"})
        self.assertTrue(all(row["source_tree_sha256"] for row in result["decision_probes"]))
        self.assertEqual({row["arm"] for row in result["episodes"]}, {"P0", "P1", "P2"})
        for clone in ("fulfilment-01-K1", "fulfilment-01-K2", "fulfilment-01-K3"):
            rows = [row for row in result["episodes"] if row["clone"] == clone]
            self.assertEqual([row["stage"] for row in rows], list("BCD"))
            self.assertTrue(all(row["complete"] for row in rows))
            self.assertEqual(rows[0]["output_source_tree_sha256"], rows[1]["input_source_tree_sha256"])
            self.assertEqual(rows[1]["output_source_tree_sha256"], rows[2]["input_source_tree_sha256"])
            for row in rows:
                self.assertTrue(row["smoke_only"])
                self.assertIsNone(row["resource_use"]["totals"])
                self.assertGreaterEqual(row["failure_penalised_seconds"], row["actual_agent_wall_seconds"])
        self.assertNotEqual(result["episodes"][0]["output_source_tree_sha256"],
                            result["episodes"][1]["output_source_tree_sha256"])
        with self.assertRaises(FileExistsError):
            runner.run(self.manifest_path, self.fixtures, output, "stub", "fulfilment-01", None)

    def test_packet_parity_deviation_stops_and_retains_attempt(self):
        def mismatch(source, system, stage, arm, evidence_schema):
            return {"facts": {"arm": arm}, "guidance": "same", "status": "supported",
                    "selected_action": "proceed", "shared_material_digest": "x",
                    "source_tree_sha256": "x",
                    **({"formal": {"route": "supported"}} if arm == "P2" else {}),
                    "packet_text": arm}
        sys.modules["packets"] = types.SimpleNamespace(generate=mismatch)
        output = self.root / "stopped"
        with self.assertRaises(runner.InfrastructureDeviation):
            runner.run(self.manifest_path, self.fixtures, output, "stub", "fulfilment-01",
                       None, self.decision_cases)
        retained = json.loads((output / "summary.json").read_text())
        self.assertEqual(retained["status"], "stopped_infrastructure_deviation")
        self.assertEqual(retained["episodes"], [])

    def test_absent_token_counters_are_unknown_not_zero(self):
        trace = self.root / "trace.jsonl"
        trace.write_text(json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 7, "output_tokens": 3, "cache_write_input_tokens": 2}}) + "\n")
        usage = usage_from_jsonl(trace)
        self.assertEqual(usage["totals"]["input_tokens"], 7)
        self.assertEqual(usage["totals"]["cache_write_input_tokens"], 2)
        self.assertIsNone(usage["totals"]["cached_input_tokens"])
        self.assertIsNone(usage["totals"]["reasoning_output_tokens"])

    def test_resource_guard_stops_on_missing_partition_and_ceiling(self):
        with self.assertRaisesRegex(runner.ResourceGuardStop, "cannot be priced"):
            runner._account_budget({"conditional_list_price_scenario":
                                    {"status": "unavailable", "high_usd": None}},
                                   runner.Decimal("0"), runner.Decimal("15.00"))
        with self.assertRaisesRegex(runner.ResourceGuardStop, "exceeds"):
            runner._account_budget({"conditional_list_price_scenario":
                                    {"status": "conditional_scenario", "high_usd": "15.01"}},
                                   runner.Decimal("0"), runner.Decimal("15.00"))
        total = runner._account_budget({"conditional_list_price_scenario":
                                        {"status": "conditional_scenario", "high_usd": "0.64"}},
                                       runner.Decimal("0"), runner.Decimal("15.00"))
        self.assertEqual(total, runner.Decimal("0.64"))

    def test_candidate_symlink_is_penalised_without_copying_host_target(self):
        inject = STUB.replace("Path('stage-'+s+'.txt').write_text(s)",
                              "Path('stage-'+s+'.txt').write_text(s)\n"
                              "if s == 'B':\n"
                              "    Path('outside').symlink_to('/etc/passwd')\n"
                              "    Path('.venv').mkdir()\n"
                              "    Path('.venv/also-outside').symlink_to('/etc/passwd')")
        output = self.root / "symlink-attempt"
        result = runner.run(self.manifest_path, self.fixtures, output, "stub", "fulfilment-01",
                            [sys.executable, "-c", inject], self.decision_cases)
        first = result["episodes"][0]
        self.assertFalse(first["complete"])
        self.assertEqual(first["candidate_invalid_entries"], ["outside"])
        self.assertGreaterEqual(first["failure_penalised_seconds"], self.manifest["wall_cap_seconds"])
        self.assertFalse((output / "blocks/fulfilment-01/fulfilment-01-K1/B/source/outside").exists())
        self.assertFalse((output / "blocks/fulfilment-01/fulfilment-01-K1/B/agent-visible").exists())
        self.assertEqual(result["episodes"][1]["stage"], "C")

    def test_preflight_probes_outer_mount_and_cli_without_provider_key(self):
        trial = self.root / "trial"
        trial.mkdir()
        (trial / "FEATURE.md").write_text("prompt")
        home = self.root / "private-home"
        home.mkdir()
        calls = []

        def record(argv, **kwargs):
            calls.append((argv, kwargs))
            return types.SimpleNamespace(returncode=0, stderr=b"")

        def binary(name):
            return "/usr/bin/bwrap" if name == "bwrap" else "/usr/local/bin/codex"

        with patch.object(runner_capture.shutil, "which", side_effect=binary), \
                patch.object(runner_capture.subprocess, "run", side_effect=record):
            runner_capture.codex_preflight(trial, home, read_only_trial=True)
        self.assertEqual(len(calls), 2)
        self.assertIn("--unshare-pid", calls[0][0])
        self.assertIn("--ro-bind", calls[0][0])
        self.assertEqual(calls[1][0][-2:], ["exec", "--help"])
        self.assertIn("--ro-bind", calls[1][0])
        self.assertNotIn("CODEX_API_KEY", calls[1][1]["env"])

    def test_live_command_runs_cli_only_inside_outer_mount(self):
        trial = self.root / "trial"
        home = self.root / "private-home"
        with patch.object(runner_capture.shutil, "which",
                          side_effect=lambda name: "/usr/bin/bwrap" if name == "bwrap"
                          else "/usr/local/bin/codex"):
            writable = runner_capture.codex_command(trial, home, "gpt-6-sol", "medium")
            readonly = runner_capture.codex_command(trial, home, "gpt-6-sol", "medium",
                                                     read_only_trial=True)
        for command in (writable, readonly):
            self.assertEqual(command[0], "bwrap")
            self.assertIn("--unshare-pid", command)
            self.assertEqual(command[command.index("--sandbox") + 1], "danger-full-access")
        self.assertIn("--bind", writable)
        self.assertEqual(readonly[readonly.index(str(trial)) - 1], "--ro-bind")

    def test_allocation_rejects_missing_arm_and_insufficient_blocks(self):
        original = self.manifest["blocks"][0]["assignments"][0]["arm"]
        self.manifest["blocks"][0]["assignments"][0]["arm"] = "P1"
        with self.assertRaisesRegex(ValueError, "one of each arm"):
            runner.validate_manifest(self.manifest, self.fixtures)
        self.manifest["blocks"][0]["assignments"][0]["arm"] = original
        self.manifest["blocks"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete system-by-replicate"):
            runner.validate_manifest(self.manifest, self.fixtures)

    def test_seeded_allocation_rejects_tampered_arm(self):
        assignments = self.manifest["blocks"][0]["assignments"]
        assignments[0]["arm"], assignments[1]["arm"] = assignments[1]["arm"], assignments[0]["arm"]
        with self.assertRaisesRegex(ValueError, "seeded permutation"):
            runner.validate_manifest(self.manifest, self.fixtures)


if __name__ == "__main__":
    unittest.main()
