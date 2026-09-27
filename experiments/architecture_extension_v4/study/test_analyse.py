"""Synthetic contract examples for v4 completeness and balanced contrasts."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import analyse
from masked_review import COMMON, SYSTEM
from runner_capture import digest, json_write, tree_digest, tree_entries


class AnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="v4-analysis-synthetic-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.fixtures = self.root / "fixtures"
        self.systems = ("fulfilment", "entitlement", "reservation")
        for system in self.systems:
            source = self.fixtures / system / "source"
            source.mkdir(parents=True)
            (source / "ARCHITECTURE.md").write_text("Synthetic fixture only.\n", encoding="utf-8")
        self.manifest = {
            "schema": "architecture-extension-v4/manifest/1",
            "systems": list(self.systems), "replicate_blocks_per_system": 3,
            "wall_cap_seconds": 60,
            "decision_probes": {"case_ids": ["clean", "defeated"], "wall_cap_seconds": 120},
            "blocks": [{"id": f"{system}-{index}", "system": system,
                        "assignments": [{"clone": f"K{clone}", "arm": arm}
                                        for clone, arm in enumerate(analyse.ARMS, 1)]}
                       for system in self.systems for index in (1, 2, 3)],
            "critical_check_ids": {system: {stage: ["synthetic.invariant"] for stage in analyse.STAGES}
                                   for system in self.systems},
        }
        self.manifest_path = self.root / "manifest.json"
        json_write(self.manifest_path, self.manifest)

    def _episode(self, output: Path, block: dict, assignment: dict, stage: str) -> dict:
        system, arm, clone = block["system"], assignment["arm"], assignment["clone"]
        stage_dir = output / "blocks" / block["id"] / clone / stage
        stage_dir.mkdir(parents=True)
        source = stage_dir / "source"
        shutil.copytree(self.fixtures / system / "source", source)
        source_sha = analyse._source_digest(source)
        tree_sha = tree_digest(tree_entries(source))
        acquisition = {"P0": 0.0, "P1": 1.0, "P2": 2.0}[arm]
        actual = {"P0": 20.0, "P1": 18.0, "P2": 15.0}[arm]
        shared = "a" * 64
        common = {"facts": ["synthetic"], "guidance": ["test"], "status": "active",
                  "selected_action": "check", "shared_material_digest": shared,
                  "source_tree_sha256": tree_sha}
        packet = ({"status": "no_packet", "selected": None} if arm == "P0" else
                  {"status": "matched_shared_material", "selected_arm": arm,
                   "shared_material_digest": shared, "source_tree_sha256": tree_sha,
                   "selected": {**common, "packet_text": arm},
                   "counterfactual": {**common, "packet_text": "P2" if arm == "P1" else "P1"}})
        json_write(stage_dir / "packet-host.json", packet)
        json_write(stage_dir / "input.json", {"source_tree_sha256": tree_sha})
        json_write(stage_dir / "output.json", {"source_tree_sha256": tree_sha})
        invocation = {"system": system, "block": block["id"], "clone": clone,
                      "arm": arm, "stage": stage, "wall_cap_seconds": 60,
                      "actual_wall_seconds": actual, "exit_code": 0, "timed_out": False,
                      "smoke_only": False}
        json_write(stage_dir / "invocation.json", invocation)
        assessment = {"system": system, "stage": stage, "source_sha256": source_sha,
                      "passed": 1, "total": 1, "valid": True,
                      "findings": {"synthetic.invariant": {"status": "pass", "detail": "synthetic"}}}
        json_write(stage_dir / "assessment.json", assessment)
        trace = stage_dir / "agent.jsonl"
        trace.write_text("", encoding="utf-8")
        usage = {"status": "unreported", "totals": {field: None for field in analyse.TOKEN_FIELDS}}
        json_write(stage_dir / "resource-use.json", {"usage": usage,
                                                    "agent_trace_sha256": digest(trace),
                                                    "provider_bill": None})
        row = {"schema": "architecture-extension-v4/episode/1", "system": system,
               "block": block["id"], "clone": clone, "arm": arm, "stage": stage,
               "input_source_tree_sha256": tree_sha, "output_source_tree_sha256": tree_sha,
               "packet_shared_material_digest": None if arm == "P0" else shared,
               "packet_acquisition_seconds": acquisition,
               "actual_agent_wall_seconds": actual,
               "assessor_host_seconds_excluded_from_treatment": 0.1,
               "failure_penalised_seconds": actual + acquisition,
               "complete": True, "assessor_passed": 1, "assessor_failed": 0,
               "assessor_invalid": 0, "assessment_sha256": digest(stage_dir / "assessment.json"),
               "agent_exit_code": 0, "agent_timed_out": False,
               "smoke_only": False, "resource_use": usage}
        json_write(stage_dir / "episode.json", row)
        return row

    def _case_root(self) -> Path:
        root = self.root / "decision-cases"
        definitions = {}
        for system in self.systems:
            definitions[system] = {}
            for case_id in ("clean", "defeated"):
                directory = root / system / case_id
                source = directory / "source"
                shutil.copytree(self.fixtures / system / "source", source)
                state = {"schema": "synthetic-state/1", "system": system, "case_id": case_id}
                json_write(directory / "state.json", state)
                definitions[system][case_id] = {
                    "source_tree_sha256": tree_digest(tree_entries(source)),
                    "state_sha256": digest(directory / "state.json"),
                    "expected_action": "ALLOW" if case_id == "clean" else "HOLD",
                    "allowed_actions": ["ALLOW", "HOLD", "OTHER"], "guidance": "Synthetic facts"}
        json_write(root / "cases.json", {"schema": "architecture-v4-decision-cases/1",
                                         "systems": definitions})
        return root

    def _decision(self, output: Path, block: dict, assigned: dict,
                  case_id: str, case_root: Path, *, smoke: bool) -> dict:
        system, arm, clone = block["system"], assigned["arm"], assigned["clone"]
        definition = analyse._read(case_root / "cases.json")["systems"][system][case_id]
        directory = output / "blocks" / block["id"] / clone / f"decision-{case_id}"
        directory.mkdir()
        state = analyse._read(case_root / system / case_id / "state.json")
        expected = definition["expected_action"]
        selected_action = "ALLOW" if arm == "P0" else expected
        response = json.dumps({"action": selected_action})
        prompt = directory / "visible-prompt.md"
        prompt.write_text("Synthetic decision prompt\n", encoding="utf-8")
        (directory / "visible-instructions.md").write_text(
            "Read the current decision case. Do not change source files. "
            "Return only the requested JSON action.\n", encoding="utf-8")
        shared = "b" * 64
        selected = {"system": system, "case_id": case_id, "arm": arm,
                    "source_tree_sha256": definition["source_tree_sha256"],
                    "state_sha256": definition["state_sha256"],
                    "expected_action": expected, "allowed_actions": definition["allowed_actions"],
                    "shared_material_digest": shared,
                    "facts": {key: value for key, value in state.items() if key != "case_id"},
                    "guidance": definition["guidance"], "prompt_text": "Synthetic decision prompt"}
        if arm == "P2":
            selected["formal"] = {"route": "synthetic"}
        json_write(directory / "packet-host.json", {"selected": selected,
                                                      "shared_material_digest": shared})
        json_write(directory / "input.json", {
            "case_source_tree_sha256": definition["source_tree_sha256"],
            "files": tree_entries(case_root / system / case_id / "source"),
            "visible_prompt_sha256": digest(prompt)})
        invocation = {"system": system, "block": block["id"], "clone": clone,
                      "arm": arm, "case_id": case_id, "smoke_only": smoke,
                      "wall_cap_seconds": 120, "actual_wall_seconds": 10.0,
                      "exit_code": 0, "timed_out": False}
        json_write(directory / "invocation.json", invocation)
        trace = directory / "agent.jsonl"
        trace.write_text(response + "\n", encoding="utf-8")
        usage = {"status": "unreported", "totals": None}
        price = {"status": "unpriced", "list_price_usd": None, "billed_usd": None}
        json_write(directory / "resource-use.json", {
            "usage": usage, "price": price, "agent_trace_sha256": digest(trace)})
        from decision_probe import score
        result = {"schema": "architecture-extension-v4/decision-probe/1",
                  "system": system, "block": block["id"], "clone": clone, "arm": arm,
                  "case_id": case_id, "agent": "stub", "smoke_only": smoke,
                  "source_tree_sha256": definition["source_tree_sha256"],
                  "packet_shared_material_digest": shared,
                  "expected_action": expected, "allowed_actions": definition["allowed_actions"],
                  "score": score(response, expected, definition["allowed_actions"]),
                  "agent_completed": True, "actual_agent_wall_seconds": 10.0,
                  "packet_acquisition_seconds": 1.0, "agent_exit_code": 0,
                  "agent_timed_out": False, "resource_use": usage, "price": price}
        json_write(directory / "decision.json", result)
        return result

    def _run_output(self, *, omit: tuple[str, str, str] | None = None,
                    smoke: bool = False, with_decisions: bool = False,
                    missing_decision: tuple[str, str, str] | None = None) -> Path:
        output = self.root / "output"
        output.mkdir()
        shutil.copyfile(self.manifest_path, output / "manifest.json")
        rows = []
        decisions = []
        case_root = self._case_root() if with_decisions else None
        for block in self.manifest["blocks"]:
            for assigned in block["assignments"]:
                for stage in analyse.STAGES:
                    if (block["id"], assigned["clone"], stage) == omit:
                        continue
                    row = self._episode(output, block, assigned, stage)
                    if smoke:
                        row["smoke_only"] = True
                        path = output / "blocks" / block["id"] / assigned["clone"] / stage
                        invocation = analyse._read(path / "invocation.json")
                        invocation["smoke_only"] = True
                        json_write(path / "invocation.json", invocation)
                        json_write(path / "episode.json", row)
                    rows.append(row)
                if case_root is not None:
                    for case_id in ("clean", "defeated"):
                        if (block["id"], assigned["clone"], case_id) != missing_decision:
                            decisions.append(self._decision(output, block, assigned, case_id,
                                                            case_root, smoke=smoke))
        json_write(output / "summary.json", {
            "schema": "architecture-extension-v4/run/1", "manifest_sha256": digest(self.manifest_path),
            "status": "completed_smoke_only" if smoke else "complete_acquisition",
            "smoke_only": smoke, "selected_blocks": [block["id"] for block in self.manifest["blocks"]],
            "episodes": rows, "decision_probes": decisions})
        return output

    def _review(self, output: Path, *, disagreement: bool = False,
                adjudicate: bool = False) -> tuple[Path, Path]:
        release = self.root / "review"
        mapping_path = self.root / "host-map.json"
        (release / "reviewer-1").mkdir(parents=True)
        (release / "reviewer-2").mkdir(parents=True)
        catalogue, mapping, forms = [], [], []
        summary = analyse._read(output / "summary.json")
        for index, row in enumerate(summary["episodes"]):
            candidate_id = f"case-{index:02}"
            sequence_id = f"sequence-{row['block']}-{row['clone']}"
            base = {"candidate_id": candidate_id, "sequence_id": sequence_id,
                    "system": row["system"], "stage": row["stage"],
                    "source_tree_sha256": row["output_source_tree_sha256"]}
            catalogue.append(base)
            mapping.append({**base, "block": row["block"], "clone": row["clone"],
                            "arm": row["arm"]})
            reviews = []
            for reviewer in (1, 2):
                findings = {anchor: {"status": "absent", "severity": None,
                                     "locations": [], "mechanism": "", "alternative_reading": ""}
                            for anchor in {**COMMON, **SYSTEM[row["system"]]}}
                if disagreement and index == 0 and reviewer == 2:
                    findings["coherent_state"] = {"status": "present", "severity": "minor",
                                                  "locations": ["service.py:1"],
                                                  "mechanism": "Synthetic concern",
                                                  "alternative_reading": "No concern"}
                reviews.append({**base, "reviewed_at_utc": "2026-09-27T10:00:00Z",
                                "findings": findings, "additional_findings": [],
                                "overall_architecture_judgement": "No concern identified",
                                "overall_rationale": "Synthetic example"})
            forms.append(reviews)
        json_write(release / "release.json", {"schema": "architecture-extension-v4/masked-review/1",
                                              "cases": catalogue})
        for reviewer in (1, 2):
            json_write(release / f"reviewer-{reviewer}" / "form.json", {
                "schema": "architecture-extension-v4/masked-review/1",
                "reviewer_id": f"synthetic-reviewer-{reviewer}",
                "sealed_at_utc": "2026-09-27T11:00:00Z", "cases": [case[reviewer - 1] for case in forms]})
        if adjudicate:
            json_write(release / "adjudication.json", {
                "schema": "architecture-extension-v4/masked-review/1",
                "adjudicator_id": "synthetic-adjudicator",
                "sealed_at_utc": "2026-09-27T12:00:00Z",
                "reviewer_1_sealed_sha256": digest(release / "reviewer-1/form.json"),
                "reviewer_2_sealed_sha256": digest(release / "reviewer-2/form.json"),
                "cases": [{"candidate_id": case["candidate_id"], "grounds": "Synthetic adjudication",
                           "unresolved": [],
                           "resolution": {"coherent_state": {"status": "absent", "severity": None}}
                           if index == 0 else None}
                          for index, case in enumerate(catalogue)]})
        json_write(mapping_path, {"schema": "architecture-extension-v4/masked-review/1",
                                  "host_only": True, "review_release": str(release.resolve()),
                                  "source_run": str(output.resolve()), "cases": mapping})
        return release, mapping_path

    def test_no_result_directory_retains_every_assigned_stage(self) -> None:
        report = analyse.analyse(self.manifest_path, [], fixtures=self.fixtures,
                                 replay_assessors=False)
        self.assertEqual(report["coverage"]["expected_episodes"], 81)
        self.assertEqual(report["coverage"]["missing_episodes"], 81)
        self.assertEqual(len(report["lineages"]), 27)
        self.assertIsNone(report["time_contrast"]["system_balanced_difference_seconds"])

    def test_one_missing_stage_blocks_all_primary_contrasts(self) -> None:
        output = self._run_output(omit=("fulfilment-1", "K3", "D"))
        report = analyse.analyse(self.manifest_path, [output], fixtures=self.fixtures,
                                 replay_assessors=False)
        self.assertEqual(report["coverage"]["sealed_episodes"], 80)
        self.assertEqual(report["coverage"]["missing_episodes"], 1)
        self.assertEqual(report["time_contrast"]["status"], "pending_incomplete_assignment")
        self.assertIsNone(report["time_contrast"]["system_balanced_difference_seconds"])

    def test_complete_balanced_difference_uses_lineages_not_episodes(self) -> None:
        output = self._run_output()
        report = analyse.analyse(self.manifest_path, [output], fixtures=self.fixtures,
                                 replay_assessors=False)
        self.assertEqual(report["coverage"]["sealed_episodes"], 81)
        self.assertEqual(report["time_contrast"]["status"], "descriptive_complete")
        self.assertEqual(report["time_contrast"]["system_balanced_difference_seconds"],
                         {"p2_minus_p1_seconds": -4.0, "p2_minus_p0_seconds": -6.0})
        self.assertEqual(report["critical_checks"]["status"], "reported")
        self.assertTrue(all(row["status"] == "pass" for row in report["critical_checks"]["per_episode"]))
        self.assertIsNone(report["priced_resource_use"]["list_price_usd"])

    def test_bad_penalty_is_invalid_record_not_an_imputed_zero(self) -> None:
        output = self._run_output()
        path = output / "blocks/fulfilment-1/K3/D/episode.json"
        record = analyse._read(path)
        record["failure_penalised_seconds"] = 0
        json_write(path, record)
        summary_path = output / "summary.json"
        summary = analyse._read(summary_path)
        for row in summary["episodes"]:
            if (row["block"], row["clone"], row["stage"]) == ("fulfilment-1", "K3", "D"):
                row["failure_penalised_seconds"] = 0
        json_write(summary_path, summary)
        report = analyse.analyse(self.manifest_path, [output], fixtures=self.fixtures,
                                 replay_assessors=False)
        self.assertEqual(report["coverage"]["integrity_invalid_episodes"], 1)
        self.assertIsNone(report["time_contrast"]["system_balanced_difference_seconds"])

    def test_smoke_only_cannot_be_presented_as_empirical_effect(self) -> None:
        output = self._run_output(smoke=True)
        report = analyse.analyse(self.manifest_path, [output], fixtures=self.fixtures,
                                 replay_assessors=False)
        self.assertEqual(report["coverage"]["sealed_episodes"], 81)
        self.assertEqual(report["time_contrast"]["status"], "smoke_only")
        self.assertIsNone(report["time_contrast"]["system_balanced_difference_seconds"])

    def test_review_mapping_waits_for_two_sealed_independent_reports(self) -> None:
        output = self._run_output()
        release, mapping = self._review(output)
        report = analyse.analyse(self.manifest_path, [output], fixtures=self.fixtures,
                                 replay_assessors=False, review_releases=[release],
                                 review_mappings=[mapping])
        self.assertEqual(report["masked_architecture_review"]["status"], "reported_masked_findings")
        self.assertEqual(len(report["masked_architecture_review"]["result"]), 81)
        form_path = release / "reviewer-2/form.json"
        form = analyse._read(form_path)
        form["sealed_at_utc"] = None
        json_write(form_path, form)
        report = analyse.analyse(self.manifest_path, [output], fixtures=self.fixtures,
                                 replay_assessors=False, review_releases=[release],
                                 review_mappings=[mapping])
        self.assertEqual(report["masked_architecture_review"]["status"], "pending_sealed_adjudication")
        self.assertIsNone(report["masked_architecture_review"]["result"])

    def test_disagreement_requires_bound_later_adjudication(self) -> None:
        output = self._run_output()
        release, mapping = self._review(output, disagreement=True)
        report = analyse.analyse(self.manifest_path, [output], fixtures=self.fixtures,
                                 replay_assessors=False, review_releases=[release],
                                 review_mappings=[mapping])
        self.assertEqual(report["masked_architecture_review"]["status"], "pending_sealed_adjudication")
        # The helper writes the adjudicator's digest-bound decision after the
        # two reviewer forms; the first release remains blinded until then.
        cases = analyse._read(release / "release.json")["cases"]
        json_write(release / "adjudication.json", {
            "schema": "architecture-extension-v4/masked-review/1",
            "adjudicator_id": "synthetic-adjudicator",
            "sealed_at_utc": "2026-09-27T12:00:00Z",
            "reviewer_1_sealed_sha256": digest(release / "reviewer-1/form.json"),
            "reviewer_2_sealed_sha256": digest(release / "reviewer-2/form.json"),
            "cases": [{"candidate_id": case["candidate_id"], "grounds": "Synthetic adjudication",
                       "unresolved": [],
                       "resolution": {"coherent_state": {"status": "absent", "severity": None}}
                       if index == 0 else None}
                      for index, case in enumerate(cases)]})
        report = analyse.analyse(self.manifest_path, [output], fixtures=self.fixtures,
                                 replay_assessors=False, review_releases=[release],
                                 review_mappings=[mapping])
        self.assertEqual(report["masked_architecture_review"]["status"], "reported_masked_findings")
        self.assertEqual(report["masked_architecture_review"]["result"][0]["adjudicated_findings"][
            "coherent_state"]["status"], "absent")

    def test_complete_decision_pairs_contrast_systems_equally(self) -> None:
        output = self._run_output(with_decisions=True)
        report = analyse.analyse(self.manifest_path, [output], fixtures=self.fixtures,
                                 replay_assessors=False,
                                 decision_cases=self.root / "decision-cases")
        self.assertEqual(report["decision_probe"]["coverage"]["expected_probes"], 54)
        self.assertEqual(report["decision_probe"]["coverage"]["valid_pairs"], 27)
        self.assertEqual(report["decision_probe"]["status"], "descriptive_complete")
        self.assertEqual(report["decision_probe"]["contrast"]["system_balanced_difference"],
                         {"p2_minus_p1": 0.0, "p2_minus_p0": 1.0})

    def test_missing_decision_probe_prevents_pair_contrast(self) -> None:
        output = self._run_output(with_decisions=True,
                                  missing_decision=("fulfilment-1", "K3", "defeated"))
        report = analyse.analyse(self.manifest_path, [output], fixtures=self.fixtures,
                                 replay_assessors=False,
                                 decision_cases=self.root / "decision-cases")
        self.assertEqual(report["decision_probe"]["coverage"]["sealed_probes"], 53)
        self.assertEqual(report["decision_probe"]["status"], "pending_incomplete_or_invalid_pair")
        self.assertIsNone(report["decision_probe"]["contrast"])

    def test_retained_decision_prompt_is_required_after_workspace_disposal(self) -> None:
        output = self._run_output(with_decisions=True)
        (output / "blocks/fulfilment-1/K3/decision-clean/visible-prompt.md").unlink()
        report = analyse.analyse(self.manifest_path, [output], fixtures=self.fixtures,
                                 replay_assessors=False,
                                 decision_cases=self.root / "decision-cases")
        self.assertEqual(report["decision_probe"]["coverage"]["integrity_invalid_probes"], 1)
        self.assertEqual(report["decision_probe"]["coverage"]["valid_pairs"], 26)
        self.assertIsNone(report["decision_probe"]["contrast"])

    def test_host_case_identity_must_not_appear_in_agent_visible_facts(self) -> None:
        output = self._run_output(with_decisions=True)
        packet_path = output / "blocks/fulfilment-1/K3/decision-clean/packet-host.json"
        packet = analyse._read(packet_path)
        packet["selected"]["facts"]["case_id"] = "clean"
        json_write(packet_path, packet)
        report = analyse.analyse(self.manifest_path, [output], fixtures=self.fixtures,
                                 replay_assessors=False,
                                 decision_cases=self.root / "decision-cases")
        self.assertEqual(report["decision_probe"]["coverage"]["integrity_invalid_probes"], 1)
        self.assertEqual(report["decision_probe"]["coverage"]["valid_pairs"], 26)
        self.assertIsNone(report["decision_probe"]["contrast"])

    def test_complete_records_in_unfinished_run_do_not_release_contrasts(self) -> None:
        output = self._run_output(with_decisions=True)
        summary_path = output / "summary.json"
        summary = analyse._read(summary_path)
        summary["status"] = "running"
        json_write(summary_path, summary)
        report = analyse.analyse(self.manifest_path, [output], fixtures=self.fixtures,
                                 replay_assessors=False, decision_cases=self.root / "decision-cases")
        self.assertEqual(report["time_contrast"]["status"], "pending_acquisition_completion")
        self.assertEqual(report["decision_probe"]["status"], "pending_acquisition_completion")
        self.assertIsNone(report["decision_probe"]["contrast"])

    def test_correct_defeated_action_without_correct_clean_action_is_not_retraction(self) -> None:
        output = self._run_output(with_decisions=True)
        summary_path = output / "summary.json"
        summary = analyse._read(summary_path)
        from decision_probe import score
        for case_id, selected in (("clean", "OTHER"), ("defeated", "HOLD")):
            directory = output / "blocks/fulfilment-1/K1" / f"decision-{case_id}"
            trace = directory / "agent.jsonl"
            response = json.dumps({"action": selected}) + "\n"
            trace.write_text(response, encoding="utf-8")
            resource = analyse._read(directory / "resource-use.json")
            resource["agent_trace_sha256"] = digest(trace)
            json_write(directory / "resource-use.json", resource)
            record = analyse._read(directory / "decision.json")
            record["score"] = score(response, record["expected_action"], record["allowed_actions"])
            json_write(directory / "decision.json", record)
            for item in summary["decision_probes"]:
                if (item["block"], item["clone"], item["case_id"]) == (
                        "fulfilment-1", "K1", case_id):
                    item["score"] = record["score"]
        json_write(summary_path, summary)
        report = analyse.analyse(self.manifest_path, [output], fixtures=self.fixtures,
                                 replay_assessors=False, decision_cases=self.root / "decision-cases")
        pair = next(pair for pair in report["decision_probe"]["pairs"] if (
            pair["block"], pair["clone"]) == ("fulfilment-1", "K1"))
        self.assertFalse(pair["both_correct"])
        self.assertFalse(pair["changed_to_correct_defeated_action"])


if __name__ == "__main__":
    unittest.main()
