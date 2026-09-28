"""Synthetic engineering cases and an oracle independent of the EAL evaluator."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys

from eal.knowledge import EALKnowledgeBase, ModelContextAdapter
from experiments.transfer_study.workspace import read_json, write_json

FIRST = "2026-09-28T10:00:00Z"
EARLY = "2026-09-28T10:01:00Z"
LATE = "2026-09-28T10:10:00Z"


@dataclass(frozen=True)
class Case:
    identifier: str
    initial_latency: int
    later_latency: int | None
    later_at: str
    assumption_until: str | None = None

    def measurement(self, stage: str) -> dict:
        value = self.initial_latency if stage == "initial" else self.later_latency
        return {"value": {} if value is None else {"latency_ms": value},
                "observed_at": FIRST if stage == "initial" or self.later_at == EARLY else self.later_at}

    def oracle(self, stage: str) -> dict:
        """Direct specification calculation; never read EAL's status to grade an answer."""
        now = FIRST if stage == "initial" else self.later_at
        value = self.initial_latency if stage == "initial" else self.later_latency
        if self.assumption_until and now > self.assumption_until:
            return {"decision": "undetermined", "basis": "assumption_expired"}
        if value is None:
            return {"decision": "undetermined", "basis": "measurement_missing"}
        return {"decision": "ready" if value <= 200 else "not_ready",
                "basis": "criterion_met" if value <= 200 else "criterion_failed"}

    def specification(self) -> str:
        return ("Assess readiness of the orders service for the stated scope. A valid report "
                "with latency_ms <= 200 establishes ready; latency_ms > 200 establishes not_ready. "
                "Reports are usable for 300 seconds after observed_at, inclusively. Missing, stale "
                "or unavailable measurements require undetermined. A failed assumption also "
                "requires undetermined; it does not establish not_ready. " +
                (f"The operating assumption is valid from {FIRST} through {self.assumption_until}. "
                 if self.assumption_until else "No additional operating assumption is required. "))

    def source(self) -> str:
        assumption = (f'assumption window {{ statement "The operating assumption holds in this interval."; '
                      f'environment scope; validate report; valid_from "{FIRST}"; '
                      f'valid_until "{self.assumption_until}"; }}' if self.assumption_until else "")
        return f'''language "EAL/2";
environment scope {{ require "service" == "orders"; }}
tool probe {{ version "1"; }}
evidence report {{ tool probe; kind measurement; environment scope; max_age 300;
  require "latency_ms" <= 200; }}
{assumption}
reasoning measured {{ method "structured/1"; rationale "The scoped measurement satisfies the specified inclusive latency limit while the declared assumptions hold."; }}
claim ready {{ statement "The orders service meets the readiness criterion in the specified scope."; environment scope; }}
argument result {{ conclusion ready; reasoning measured; evidence report;
  {"assumptions window;" if self.assumption_until else ""} }}
'''


CASES = (
    Case("fresh_positive", 180, 180, EARLY),
    Case("fresh_negative", 240, 240, EARLY),
    Case("refresh_positive", 240, 180, LATE),
    Case("refresh_negative", 180, 240, LATE),
    Case("missing_measurement", 180, None, LATE),
    Case("expired_assumption", 180, 180, EARLY, "2026-09-28T10:00:30Z"),
)


class Project:
    """Present only project artefacts and the public collector interface to a model."""

    def __init__(self, root: Path, case: Case, arm: str):
        self.root, self.case, self.arm = root, case, arm
        self.workspace = root / "project"
        self.workspace.mkdir(parents=True)
        self.state = root / "collector-state.json"
        self.events: list[dict] = []
        self.stage = "initial"
        self.set_stage("initial")
        (self.workspace / "specification.txt").write_text(case.specification())
        if arm == "eal":
            (self.workspace / "argument.eal").write_text(case.source())
            # The binding is stable across stages. State is external tool data, not a project artefact.
            collector = Path(__file__).with_name("collector.py").resolve()
            (self.workspace / "tools.toml").write_text(
                '[tools.probe]\nkind="command"\nversion="1"\n' +
                'argv=' + json.dumps([sys.executable, str(collector), str(self.state.resolve())]) +
                '\ntimeout_seconds=10\nmax_output_bytes=4096\ninherit_env=[]\n')
            self.knowledge = EALKnowledgeBase(self.workspace, self.workspace / "tools.toml")
            self.knowledge.register("argument.eal", entry_id="orders", context={"service": "orders"}, claims=["ready"])

    def set_stage(self, stage: str) -> None:
        self.stage = stage
        write_json(self.state, self.case.measurement(stage))

    def probe(self) -> dict:
        result = read_json(self.state)
        self.events.append({"stage": self.stage, "kind": "native_probe", "output": result})
        return result

    def context(self, question: str) -> list[dict]:
        if self.arm != "eal":
            return []
        self.knowledge = EALKnowledgeBase(self.workspace, self.workspace / "tools.toml")
        result = ModelContextAdapter(self.knowledge).prepare(
            question, "orders", "ready", now=FIRST if self.stage == "initial" else self.case.later_at)
        self.events.append({"stage": self.stage, "kind": "eal_assess", "assessment": result["assessment"]})
        return result["messages"][:-1]

    def files(self) -> dict[str, str]:
        return {path.name: path.read_text() for path in sorted(self.workspace.iterdir())
                if path.is_file() and path.suffix in (".txt", ".md", ".eal")}

    def persist(self, files: dict) -> None:
        if not isinstance(files, dict) or len(files) > 4:
            raise ValueError("Output files must be an object with at most four project notes")
        for name, content in files.items():
            if (name != Path(name).name or not name.endswith((".md", ".txt")) or
                    name == "specification.txt" or not isinstance(content, str) or len(content) > 8000):
                raise ValueError("Only bounded new .md/.txt project notes are accepted")
        for name, content in files.items():
            (self.workspace / name).write_text(content)
