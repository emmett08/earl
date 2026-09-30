"""Validated study materials and deterministic paired allocation."""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
ARMS = ("ordinary", "eal")
TRANSFERS = (
    "same_developer_same_model", "same_developer_different_model",
    "different_developer_same_model", "different_developer_different_model",
)


def _fields(value: Any, required: set[str], optional: set[str] = set()) -> dict:
    if not isinstance(value, dict) or required - value.keys() or value.keys() - required - optional:
        raise ValueError(f"Expected fields {sorted(required)} and optional {sorted(optional)}")
    return value


def _name(value: Any) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise ValueError(f"Invalid study identifier: {value!r}")
    return value


def _string(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected non-empty text")
    return value


@dataclass(frozen=True)
class Model:
    identifier: str
    version: str
    size_class: str
    command: tuple[str, ...]
    timeout_seconds: int

    @classmethod
    def read(cls, identifier: str, raw: Any) -> Model:
        data = _fields(raw, {"version", "size_class", "command"}, {"timeout_seconds"})
        command = data["command"]
        timeout = data.get("timeout_seconds", 120)
        if (not isinstance(command, list) or not command or
                any(not isinstance(part, str) or not part for part in command)):
            raise ValueError("Model command must be a non-empty argv list")
        if type(timeout) is not int or not 1 <= timeout <= 600:
            raise ValueError("Model timeout_seconds must be 1..600")
        if data["size_class"] not in ("small", "large"):
            raise ValueError("Model size_class must be small or large")
        return cls(_name(identifier), _string(data["version"]), data["size_class"],
                   tuple(command), timeout)


@dataclass(frozen=True)
class Slot:
    identifier: str
    sender: str
    recipient: str
    initial_model: str
    later_model: str

    @classmethod
    def read(cls, raw: Any, models: dict[str, Model]) -> Slot:
        data = _fields(raw, {"id", "sender", "recipient", "initial_model", "later_model"})
        slot = cls(*(_name(data[key]) for key in
                     ("id", "sender", "recipient", "initial_model", "later_model")))
        if slot.initial_model not in models or slot.later_model not in models:
            raise ValueError("Slot references a model missing from the plan")
        return slot

    @property
    def transfer(self) -> str:
        return ("same" if self.sender == self.recipient else "different") + "_developer_" + (
            "same" if self.initial_model == self.later_model else "different") + "_model"


@dataclass(frozen=True)
class Case:
    identifier: str
    seed_dir: Path
    initial_question: str
    later_question: str
    transfer: str
    slots: tuple[Slot, Slot]
    later_now: str | None

    @classmethod
    def read(cls, raw: Any, root: Path, models: dict[str, Model]) -> Case:
        data = _fields(raw, {"id", "seed_dir", "initial_question", "later_question",
                             "transfer", "slots"}, {"later_now"})
        name = _name(data["id"])
        location = Path(_string(data["seed_dir"]))
        if location.is_absolute() or ".." in location.parts or location == Path("."):
            raise ValueError(f"Invalid case seed_dir for {name}")
        seed = (root / location).resolve()
        if not seed.is_dir() or not seed.is_relative_to(root.resolve()):
            raise ValueError(f"Case {name} has no contained seed directory")
        if any(path.is_symlink() for path in seed.rglob("*")):
            raise ValueError(f"Case {name} contains a symlink")
        slots = data["slots"]
        if not isinstance(slots, list) or len(slots) != 2:
            raise ValueError("A matched case requires exactly two participant slots")
        pair = tuple(Slot.read(slot, models) for slot in slots)
        if pair[0].identifier == pair[1].identifier:
            raise ValueError("Participant slot IDs must differ")
        if (pair[0].initial_model != pair[1].initial_model or
                pair[0].later_model != pair[1].later_model):
            raise ValueError("Matched arms must have the same model transition")
        if {pair[0].sender, pair[0].recipient} & {pair[1].sender, pair[1].recipient}:
            raise ValueError("Matched arms require independent developer teams")
        transfer = data["transfer"]
        if transfer not in TRANSFERS or any(slot.transfer != transfer for slot in pair):
            raise ValueError(f"Developer/model identities do not match {transfer!r}")
        later_now = data.get("later_now")
        if later_now is not None:
            from eal.evaluator import parse_time
            if not isinstance(later_now, str):
                raise ValueError("later_now must be a timezone-aware instant")
            parse_time(later_now)
        return cls(name, seed, _string(data["initial_question"]),
                   _string(data["later_question"]), transfer, pair, later_now)


@dataclass(frozen=True)
class StudyDesign:
    study_id: str
    phase: str
    meaningful_difference: float
    primary_min_pairs: int
    session_minutes: dict[str, float]
    max_model_calls: int
    models: dict[str, Model]
    cases: tuple[Case, ...]
    source: Path
    digest: str

    @classmethod
    def load(cls, path: str | Path) -> StudyDesign:
        source = Path(path).resolve()
        raw_bytes = source.read_bytes()
        data = _fields(json.loads(raw_bytes), {"schema", "study_id", "phase",
                                              "meaningful_difference", "primary_min_pairs",
                                              "session_minutes", "max_model_calls",
                                              "models", "cases"}, {"source_language"})
        if "source_language" in data and data["source_language"] != "EAL/3":
            raise ValueError("The current study instrument requires EAL/3 source")
        if data["schema"] != "EAL/transfer-study-plan/2":
            raise ValueError("Unexpected study plan schema")
        if data["phase"] not in ("pilot", "confirmation"):
            raise ValueError("Study phase must be pilot or confirmation")
        difference = data["meaningful_difference"]
        minimum = data["primary_min_pairs"]
        if (isinstance(difference, bool) or not isinstance(difference, (int, float))
                or not 0 < difference <= 1 or type(minimum) is not int or minimum < 1):
            raise ValueError("Invalid practical threshold or primary case count")
        if not isinstance(data["models"], dict) or not data["models"]:
            raise ValueError("The study needs pinned model commands")
        models = {key: Model.read(key, value) for key, value in data["models"].items()}
        if len({model.version for model in models.values()}) != len(models):
            raise ValueError("Distinct model IDs must name distinct pinned versions, not aliases")
        if not isinstance(data["cases"], list) or not data["cases"]:
            raise ValueError("The study needs cases")
        cases = tuple(Case.read(raw, source.parent, models) for raw in data["cases"])
        if len({case.identifier for case in cases}) != len(cases):
            raise ValueError("Case IDs must be unique")
        minutes = _fields(data["session_minutes"], {"initial", "later"})
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
               not 0 < value <= 480 for value in minutes.values()):
            raise ValueError("Session time limits must be finite minutes in (0, 480]")
        calls = data["max_model_calls"]
        if type(calls) is not int or not 1 <= calls <= 1000:
            raise ValueError("max_model_calls must be 1..1000, including failures")
        if data["phase"] == "confirmation":
            if repeated_developers(cases):
                raise ValueError("Confirmation requires distinct developers across cases")
            if sum(case.transfer == TRANSFERS[-1] for case in cases) < minimum:
                raise ValueError("Confirmation has fewer primary cases than primary_min_pairs")
        return cls(_name(data["study_id"]), data["phase"], difference, minimum, minutes, calls,
                   models, cases, source,
                   hashlib.sha256(raw_bytes).hexdigest())

    def allocations(self, seed: int) -> dict[str, Any]:
        if type(seed) is not int or seed < 0:
            raise ValueError("Allocation seed must be a non-negative integer")
        assignments = []
        for case in self.cases:
            bit = random.Random(f"{seed}:{case.identifier}").randrange(2)
            for index, slot in enumerate(case.slots):
                assignments.append({
                    "case_id": case.identifier, "slot_id": slot.identifier,
                    "arm": ARMS[(index + bit) % 2], "transfer": case.transfer,
                    "sender": slot.sender, "recipient": slot.recipient,
                    "initial_model": slot.initial_model, "later_model": slot.later_model,
                })
        return {"schema": "EAL/transfer-allocation/1", "study_id": self.study_id,
                "plan_sha256": self.digest, "seed": seed, "assignments": assignments}


def repeated_developers(cases: tuple[Case, ...]) -> list[str]:
    """Same-person continuity within a case is intended; cross-case reuse is not independent."""
    seen: set[str] = set()
    repeated: set[str] = set()
    for case in cases:
        people = {person for slot in case.slots for person in (slot.sender, slot.recipient)}
        repeated.update(seen & people)
        seen.update(people)
    return sorted(repeated)
