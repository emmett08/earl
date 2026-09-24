#!/usr/bin/env python3
"""Freeze and execute a synthetic EAL/2 bias-attribution study.

The ledger is write-ahead: a sent or possibly sent call is never retried. A
pending call after interruption remains unknown. Neither fixture labels nor
the API key are included in model requests or ledger events.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sys
import time
from typing import Any
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.json"
SCHEMA = "eal2-bias-freeze/1"
LEDGER_SCHEMA = "eal2-bias-ledger/1"
API_URL = "https://api.openai.com/v1/responses"
STATUSES = ("NOT-APPLICABLE", "HYPOTHESISED", "COMPATIBLE", "EPISODE-SUPPORTED",
            "COMPARATIVELY-SUPPORTED", "CAUSALLY-SUPPORTED", "REJECTED", "UNDECIDED")
ROLES = ("exposure", "opportunity", "uptake", "signature", "temporal", "contrast", "rivals")
MODELS = {
    "nano": {"id": "gpt-4.1-nano-2025-04-14", "input_usd_per_million": 0.10,
             "output_usd_per_million": 0.40, "reasoning": None},
    "luna": {"id": "gpt-6-luna", "input_usd_per_million": 0.10,
             "output_usd_per_million": 0.50, "reasoning": "none"},
    "sol": {"id": "gpt-6-sol", "input_usd_per_million": 2.00,
            "output_usd_per_million": 10.00, "reasoning": "high"},
}
STAGES = {"direct": ("direct",), "independent": ("mechanism", "rival")}
KEY_PATTERN = re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def strict_json(value: str) -> Any:
    def pairs(rows: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, item in rows:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = item
        return result
    return json.loads(value, object_pairs_hook=pairs,
                      parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))


def read_json(path: Path) -> Any:
    return strict_json(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact(value: Any) -> Any:
    if isinstance(value, str):
        secret = os.environ.get("OPENAI_API_KEY", "")
        if secret:
            value = value.replace(secret, "[REDACTED]")
        return KEY_PATTERN.sub("[REDACTED]", value)
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def _eal_source(family: dict, variant: str, records: list[dict]) -> str:
    episode = family["id"] + "_" + variant
    statement = f"At the review cut, the engineering decision is warranted: {family['decision']}"
    statement = json.dumps(statement, ensure_ascii=False)
    scope = json.dumps(episode)
    defect = json.dumps(family["defect"], ensure_ascii=False)
    hypothesis = json.dumps(
        f"Candidate process hypothesis: {family['mechanism']} contributed to the recorded decision in {episode}.",
        ensure_ascii=False)
    declarations = "\n".join(
        f'''evidence record_{record["id"].lower()} {{
  tool synthetic_record; kind observation; environment review_cut; max_age 86400;
  require "episode" == {scope}; require "record_id" == "{record['id']}";
}}''' for record in records)
    process_ids = [row["id"] for row in records if row["id"] not in ("E1", "E2")]
    route = ", ".join("record_" + evidence_id.lower() for evidence_id in process_ids)
    challenge_id = ("E6" if variant == "rival" else "E4" if variant in
                    ("missing_link", "insufficient") else None)
    challenge = (f'\nobjection alternative_challenge {{ target argument hypothesis_route; evidence record_{challenge_id.lower()}; }}'
                 if challenge_id is not None else "")
    return f'''language "EAL/2";
environment review_cut {{ require "episode" == {scope}; }}
tool synthetic_record {{ version "1"; mode deterministic; }}
evidence decision_record {{
  tool synthetic_record; kind observation; environment review_cut; max_age 86400;
  require "episode" == {scope};
  require "recorded" == true;
}}
evidence defect_record {{
  tool synthetic_record; kind observation; environment review_cut; max_age 86400;
  require "episode" == {scope};
  require "defect" == {defect};
}}
{declarations}
reasoning proposed_decision {{
  method "structured/1";
  rationale "The recorded judgement is a proposed basis for the engineering decision; the source defect challenges that basis. Neither the proposal nor the objection establishes a cognitive cause.";
}}
reasoning process_inference {{
  method "structured/1";
  rationale "The candidate requires exposed cue, opportunity, actual uptake, directional signature, temporal order, a discriminating contrast, and examined rivals. These authored records alone do not establish psychological causation.";
}}
claim decision_claim {{ statement {statement}; environment review_cut; }}
claim bias_hypothesis {{ statement {hypothesis}; environment review_cut; }}
argument proposed_route {{ conclusion decision_claim; reasoning proposed_decision; evidence decision_record; }}
objection defect_challenge {{ target argument proposed_route; evidence defect_record; }}
argument hypothesis_route {{ conclusion bias_hypothesis; reasoning process_inference; evidence {route}; }}{challenge}
'''


def validate_eal_sources(cases: list[dict]) -> dict[str, str]:
    """Use the current repository parser, never an unrelated editable install."""
    root = HERE.parents[2]
    parser_file = root / "src/eal/parser.py"
    grammar_file = root / "grammar/EAL.g4"
    if not parser_file.is_file() or not grammar_file.is_file():
        raise RuntimeError("Current EAL/2 parser and grammar are needed before freezing")
    sys.path.insert(0, str(root / "src"))
    from eal.parser import parse
    from eal.semantics import validate
    if Path(sys.modules["eal.parser"].__file__).resolve() != parser_file.resolve():
        raise RuntimeError("EAL parser is not from the current repository")
    for case in cases:
        diagnostics = validate(parse(case["eal"]))
        if diagnostics:
            raise ValueError(f"EAL/2 source {case['id']} failed static validation: {diagnostics}")
    files = sorted((root / "src/eal").rglob("*.py"))
    return {"grammar/EAL.g4": digest(grammar_file.read_bytes()),
            **{file.relative_to(root).as_posix(): digest(file.read_bytes()) for file in files}}


def load_cases(path: Path = CASES) -> list[dict]:
    data = read_json(path)
    fields = {"id", "mechanism", "decision", "cue", "opportunity", "uptake", "signature",
              "contrast", "rival", "no_opportunity", "uncertain", "defect", "correction"}
    if (data.get("schema") != "eal2-bias-cases/1" or len(data.get("families", [])) != 12
            or len({row.get("id") for row in data["families"]}) != 12):
        raise ValueError("Expected twelve unique synthetic families")
    if any(set(row) != fields or any(not isinstance(v, str) or not v.strip()
                                    for v in row.values()) for row in data["families"]):
        raise ValueError("Incomplete family fixture")
    if len({row["mechanism"] for row in data["families"]}) != 12:
        raise ValueError("Mechanisms must differ across the twelve families")
    result = []
    for index, family in enumerate(data["families"]):
        for variant in ("process", "rival", "missing_link", "insufficient"):
            case_id = family["id"] + "__" + variant
            records = [
                {"id": "E1", "text": "At 2026-09-01T12:00Z, the synthetic decision was: " + family["decision"]},
                {"id": "E2", "text": "The source defect needing correction is: " + family["defect"]},
                {"id": "E3", "text": "At 2026-09-01T11:00Z: " + family["cue"]},
            ]
            if variant == "process":
                records += [
                    {"id": "E4", "text": family["opportunity"]},
                    {"id": "E5", "text": family["uptake"]},
                    {"id": "E6", "text": family["signature"]},
                    {"id": "E7", "text": family["contrast"]},
                    {"id": "E8", "text": "The comparison checked access, record scope and a different applicable technical cause; none explained the matched change."},
                ]
                status = "COMPARATIVELY-SUPPORTED"
                required = {"exposure": ["E3"], "opportunity": ["E4"], "uptake": ["E5"],
                            "signature": ["E6"], "temporal": ["E1", "E3"],
                            "contrast": ["E7"], "rivals": ["E8"]}
                rival = None
                defeater = None
            elif variant == "rival":
                records += [
                    {"id": "E4", "text": family["opportunity"]},
                    {"id": "E5", "text": "The contemporaneous reviewer ground explicitly rejects the cue as a basis."},
                    {"id": "E6", "text": family["rival"]},
                    {"id": "E7", "text": "A matched decision with the cue absent had the same result under the documented technical condition."},
                ]
                status = "REJECTED"
                required = {"rivals": ["E6"], "contrast": ["E7"]}
                rival = "r1"
                defeater = "E6"
            elif variant == "missing_link":
                missing_link = ("exposure", "opportunity", "uptake")[index // 4]
                if missing_link == "exposure":
                    records[2] = {"id": "E3", "text": "The proposed cue was created at 11:00Z but the delivery log shows the actor never received it before the decision."}
                    records += [{"id": "E4", "text": "The signed access audit confirms no exposure to the proposed cue before the decision cut."},
                                {"id": "E5", "text": family["no_opportunity"]}]
                    status = "NOT-APPLICABLE"
                    rival = "r2"
                    required = {"rivals": ["E4"]}
                    defeater = "E4"
                elif missing_link == "opportunity":
                    records += [{"id": "E4", "text": "A signed instruction locked the decision before this actor's task; the actor could only transcribe it, and had no discretion to search, weigh, or decide otherwise."},
                                {"id": "E5", "text": "The role and access audit confirms that the actor could not change the decision at this cut."}]
                    status = "NOT-APPLICABLE"
                    rival = "r2"
                    required = {"rivals": ["E4", "E5"]}
                    defeater = "E4"
                else:
                    records += [{"id": "E4", "text": family["opportunity"]},
                                {"id": "E5", "text": "The contemporaneous grounds explicitly reject the proposed cue and use an independent checked basis."},
                                {"id": "E6", "text": family["rival"]}]
                    status = "REJECTED"
                    rival = "r1"
                    required = {"rivals": ["E5", "E6"]}
                    defeater = "E5"
            else:
                records += [
                    {"id": "E4", "text": family["uncertain"]},
                    {"id": "E5", "text": ("The observed aggregate pattern is directionally compatible, but uptake and a matched contrast are not recorded."
                                           if index < 6 else "No reliable directional comparison or uptake record survives.")},
                ]
                status = "COMPATIBLE" if index < 6 else "UNDECIDED"
                required = {"exposure": ["E3"]} if index < 6 else {"rivals": ["E4"]}
                rival = None
                defeater = None
            # Order is counterbalanced between families only, not a paired order experiment.
            if index % 2:
                records = list(reversed(records))
            options = {
                "defects": [
                    {"id": "d1", "text": family["defect"]},
                    {"id": "d2", "text": "The review needs a shorter title but no source-data change."},
                    {"id": "d3", "text": "Any adverse outcome proves that the reviewer has a lasting cognitive trait."},
                ],
                "corrections": [
                    {"id": "a1", "text": family["correction"]},
                    {"id": "a2", "text": "Replace the evidence check with an AI recommendation."},
                    {"id": "a3", "text": "Give general bias-awareness training without changing the affected decision."},
                ],
                "rivals": [
                    {"id": "r1", "text": family["rival"]},
                    {"id": "r2", "text": ("Delivery audit shows the proposed cue was not received."
                                          if variant == "missing_link" and missing_link == "exposure"
                                          else "The actor could only transcribe a locked decision."
                                          if variant == "missing_link" and missing_link == "opportunity"
                                          else family["no_opportunity"])},
                    {"id": "r3", "text": "An unverified change in workload could alter the decision."},
                ],
            }
            # Stable, case-specific option permutation avoids a fixed first-choice artefact.
            rng = random.Random(digest(case_id))
            for alternatives in options.values():
                rng.shuffle(alternatives)
            result.append({
                "id": case_id, "family": family["id"], "variant": variant,
                "missing_link": missing_link if variant == "missing_link" else None,
                "mechanism": family["mechanism"], "eal": _eal_source(family, variant, records),
                "records": records, "options": options,
                "gold": {"status": status, "mechanism_id": family["mechanism"],
                         "required_roles": required, "rival_id": rival, "defeater_id": defeater,
                         "defect_id": "d1", "correction_id": "a1"},
                "role_evidence": ({"exposure": ["E3"], "opportunity": ["E4"],
                                   "uptake": ["E5"], "signature": ["E6"],
                                   "temporal": ["E1", "E3"], "contrast": ["E7"],
                                   "rivals": ["E8"]} if variant == "process" else {}),
            })
    return result


ANSWER_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": list(STATUSES)},
        "mechanism_id": {"type": ["string", "null"]},
        "evidence_ids": {"type": "object", "additionalProperties": False,
                         "properties": {role: {"type": "array", "items": {"type": "string"}}
                                        for role in ROLES}, "required": list(ROLES)},
        "rival_id": {"type": ["string", "null"]},
        "defeater_id": {"type": ["string", "null"]},
        "defect_id": {"type": ["string", "null"]},
        "correction_id": {"type": ["string", "null"]},
        "confidence": {"type": "string", "enum": ["low", "moderate", "high"]},
        "rationale": {"type": "string"},
    },
    "required": ["status", "mechanism_id", "evidence_ids", "rival_id", "defeater_id",
                 "defect_id", "correction_id", "confidence", "rationale"],
}

SYSTEM = (
    "Assess a hypothetical synthetic engineering decision episode. The EAL/2 source is an "
    "authored argument and does not prove its factual premises or a cognitive cause. "
    "A bad outcome or fluent AI recommendation alone does not establish a human cognitive bias. "
    "Use exposure, opportunity, actual uptake, directional signature, temporal order, contrast "
    "and technical or organisational rivals. Refer only to supplied record IDs; place each ID "
    "under the role it actually supports. A missing prerequisite limits the status. "
    "Correct the source defect even if psychological attribution is unresolved. Select option IDs "
    "only from the supplied options. State uncertainty in a rationale of at most 300 characters; "
    "never diagnose a person's enduring disposition. The synthetic status applies to the written "
    "hypothetical record, not an observed human population."
)


def request_body(case: dict, model: dict, stage: str, mechanism_ids: list[str],
                 max_output_tokens: int) -> dict:
    emphasis = {
        "direct": "Assess all explanations and give your disposition.",
        "mechanism": "Independently test the proposed cognitive mechanism and its required process chain.",
        "rival": "Independently seek the strongest non-cognitive or alternative explanation and any missing premise.",
    }[stage]
    public = {key: case[key] for key in ("id", "eal", "records", "options")}
    body = {
        "model": model["id"], "store": False, "max_output_tokens": max_output_tokens,
        "input": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": emphasis + "\nCandidate mechanisms: " +
             json.dumps(mechanism_ids, separators=(",", ":")) + "\nEpisode: " +
             canonical(public).decode("utf-8")},
        ],
        "text": {"format": {"type": "json_schema", "name": "bias_episode_disposition",
                            "strict": True, "schema": ANSWER_SCHEMA}},
    }
    if model["reasoning"] is not None:
        body["reasoning"] = {"effort": model["reasoning"]}
    return body


def reserved_cost(body: dict, model: dict) -> float:
    # One UTF-8 byte per input token is a deliberately conservative reservation,
    # not a token count or an assertion about provider pricing.
    input_upper_bound = len(canonical(body["input"])) + len(canonical(body["text"]))
    return (input_upper_bound * model["input_usd_per_million"] +
            body["max_output_tokens"] * model["output_usd_per_million"]) / 1_000_000


def _plan_calls(families: int, model_names: list[str], seed: int,
                max_output_tokens: int) -> tuple[list[dict], list[dict]]:
    all_cases = load_cases()
    selected = all_cases[:4 * families]
    mechanism_ids = sorted({case["mechanism"] for case in all_cases})
    calls = []
    for case in selected:
        for name in model_names:
            for topology, stages in STAGES.items():
                for stage in stages:
                    body = request_body(case, MODELS[name], stage, mechanism_ids, max_output_tokens)
                    call_id = f"{case['id']}__{name}__{topology}__{stage}"
                    calls.append({"id": call_id, "case_id": case["id"], "family": case["family"],
                                  "variant": case["variant"], "model_name": name,
                                  "topology": topology, "stage": stage,
                                  "request": body, "request_sha256": digest(body),
                                  "reserved_usd": reserved_cost(body, MODELS[name])})
    random.Random(seed).shuffle(calls)
    return selected, calls


def freeze(path: Path, *, families: int, model_names: list[str], seed: int,
           max_usd: float, max_output_tokens: int) -> dict:
    if not 1 <= families <= 12 or not model_names or len(set(model_names)) != len(model_names):
        raise ValueError("Select one to twelve families and distinct models")
    if set(model_names) - set(MODELS) or not 0 < max_usd <= 100 or not 256 <= max_output_tokens <= 4096:
        raise ValueError("Invalid models, budget or output limit")
    selected, calls = _plan_calls(families, model_names, seed, max_output_tokens)
    parser_materials = validate_eal_sources(selected)
    material = {"cases.json": digest(CASES.read_bytes()), "run.py": digest(Path(__file__).read_bytes()),
                "analyse.py": digest((HERE / "analyse.py").read_bytes()),
                "PROTOCOL.md": digest((HERE / "PROTOCOL.md").read_bytes()),
                **parser_materials}
    result = {"schema": SCHEMA, "synthetic": True, "created_utc": utc_now(),
              "materials": material, "seed": seed, "models": {name: MODELS[name]
              for name in model_names}, "max_usd": max_usd, "max_output_tokens": max_output_tokens,
              "families": families, "case_count": len(selected), "calls": calls}
    result["freeze_sha256"] = digest({key: val for key, val in result.items()
                                       if key != "freeze_sha256"})
    reserve = sum(item["reserved_usd"] for item in calls)
    if reserve > max_usd:
        raise ValueError(f"Conservative full-plan reserve ${reserve:.3f} exceeds cap ${max_usd:.2f}")
    if path.exists():
        raise FileExistsError(f"Frozen plan exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return result


def load_freeze(path: Path, *, verify_materials: bool = True) -> dict:
    result = read_json(path)
    if result.get("schema") != SCHEMA or result.get("freeze_sha256") != digest(
            {key: val for key, val in result.items() if key != "freeze_sha256"}):
        raise ValueError("Invalid or modified freeze")
    if verify_materials:
        root = HERE.parents[2]
        current = {"cases.json": digest(CASES.read_bytes()),
                   "run.py": digest(Path(__file__).read_bytes()),
                   "analyse.py": digest((HERE / "analyse.py").read_bytes()),
                   "PROTOCOL.md": digest((HERE / "PROTOCOL.md").read_bytes())}
        files = [root / "grammar/EAL.g4", *(root / "src/eal").rglob("*.py")]
        current.update({file.relative_to(root).as_posix(): digest(file.read_bytes())
                        for file in files})
        if result["materials"] != current:
            raise ValueError("Study materials changed since freeze")
    names = list(result["models"])
    if not (1 <= result["families"] <= 12 and names and set(names) <= set(MODELS)
            and result["models"] == {name: MODELS[name] for name in names}
            and 256 <= result["max_output_tokens"] <= 4096
            and 0 < result["max_usd"] <= 100):
        raise ValueError("Frozen model, budget or schedule configuration differs")
    selected, expected_calls = _plan_calls(result["families"], names,
                                           result["seed"], result["max_output_tokens"])
    if result["calls"] != expected_calls or result["case_count"] != len(selected):
        raise ValueError("Frozen request matrix differs from deterministic regeneration")
    if sum(item["reserved_usd"] for item in expected_calls) > result["max_usd"]:
        raise ValueError("Frozen full-plan reserve exceeds cap")
    return result


def preflight(timeout: float = 4.0) -> None:
    """An unauthenticated GET through the configured HTTPS proxy; 401 is expected."""
    request = urllib.request.Request("https://api.openai.com/v1/models", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise RuntimeError(f"Unexpected preflight HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            raise RuntimeError(f"Preflight HTTP {exc.code}; endpoint may be blocked") from None


def _post_response(body: dict, key: str, timeout: float = 120.0) -> tuple[dict, str | None]:
    request = urllib.request.Request(API_URL, data=canonical(body), method="POST", headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("Provider response exceeds 2 MB")
        return strict_json(data.decode("utf-8")), response.headers.get("x-request-id")


def parse_response(response: dict) -> tuple[dict | None, str | None]:
    if response.get("status") != "completed":
        return None, "non_completed:" + str(response.get("status"))
    messages = [item for item in response.get("output", []) if item.get("type") == "message"]
    content = [part for item in messages for part in item.get("content", [])]
    if any(part.get("type") == "refusal" for part in content):
        return None, "refusal"
    texts = [part.get("text") for part in content if part.get("type") == "output_text"]
    if len(texts) != 1 or not isinstance(texts[0], str):
        return None, "missing_or_multiple_output_text"
    try:
        answer = strict_json(texts[0])
        if not isinstance(answer, dict) or set(answer) != set(ANSWER_SCHEMA["required"]):
            return None, "invalid_answer_fields"
        if answer["status"] not in STATUSES or answer["confidence"] not in ("low", "moderate", "high"):
            return None, "invalid_status_or_confidence"
        if any(value is not None and not isinstance(value, str) for key, value in answer.items()
               if key in ("mechanism_id", "rival_id", "defeater_id", "defect_id", "correction_id")):
            return None, "invalid_option_type"
        if (not isinstance(answer["evidence_ids"], dict)
                or set(answer["evidence_ids"]) != set(ROLES)
                or any(not isinstance(ids, list) or any(not isinstance(eid, str) for eid in ids)
                       for ids in answer["evidence_ids"].values())):
            return None, "invalid_evidence_shape"
        if not isinstance(answer["rationale"], str) or len(answer["rationale"]) > 300:
            return None, "invalid_rationale"
        return answer, None
    except (ValueError, TypeError):
        return None, "invalid_json"


def validate_answer(answer: dict, case: dict) -> list[str]:
    errors = []
    available = {record["id"] for record in case["records"]}
    for role, ids in answer["evidence_ids"].items():
        if len(ids) != len(set(ids)) or any(eid not in available for eid in ids):
            errors.append("unknown_or_duplicate_evidence:" + role)
    options = case["options"]
    for answer_key, group in (("rival_id", "rivals"), ("defect_id", "defects"),
                              ("correction_id", "corrections")):
        if answer[answer_key] is not None and answer[answer_key] not in {
                row["id"] for row in options[group]}:
            errors.append("unknown_option:" + answer_key)
    if answer["defeater_id"] is not None and answer["defeater_id"] not in available:
        errors.append("unknown_defeater")
    if answer["mechanism_id"] is not None and answer["mechanism_id"] not in {
            item["mechanism"] for item in load_cases()}:
        errors.append("unknown_mechanism")
    return errors


def gate_answer(answer: dict, case: dict) -> tuple[dict, list[str]]:
    """A limited provenance gate using *author-labelled synthetic* process roles.

    It verifies citations, not whether the simulated psychology is real. Apply
    the same gate to both topology arms and retain raw outputs in the ledger.
    """
    errors = validate_answer(answer, case)
    needed = list(ROLES[:5]) if answer["status"] == "EPISODE-SUPPORTED" else list(ROLES)
    if answer["status"] in ("EPISODE-SUPPORTED", "COMPARATIVELY-SUPPORTED",
                            "CAUSALLY-SUPPORTED"):
        for role in needed:
            if not set(answer["evidence_ids"][role]) & set(case["role_evidence"].get(role, [])):
                errors.append("missing_supported_role:" + role)
        if answer["status"] == "CAUSALLY-SUPPORTED":
            errors.append("no_synthetic_causal_intervention")
    if errors:
        gated = dict(answer)
        gated["status"] = "UNDECIDED"
        gated["confidence"] = "low"
        return gated, errors
    return answer, []


def ledger_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events, previous = [], "0" * 64
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            event = strict_json(line)
            supplied = event.pop("event_sha256", None)
            if event.get("schema") != LEDGER_SCHEMA or event.get("previous_sha256") != previous or digest(event) != supplied:
                raise ValueError("Ledger hash chain is invalid")
            event["event_sha256"] = supplied
            events.append(event)
            previous = supplied
    return events


def append_event(path: Path, event: dict, previous: str) -> str:
    event = redact({"schema": LEDGER_SCHEMA, "previous_sha256": previous, **event})
    event["event_sha256"] = digest(event)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(canonical(event).decode("utf-8") + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return event["event_sha256"]


def _completed(events: list[dict]) -> tuple[set[str], float]:
    pending, done, spent = {}, set(), 0.0
    for event in events:
        if event["kind"] == "pending":
            if event["call_id"] in pending:
                raise ValueError("Call attempted twice")
            pending[event["call_id"]] = event["request_sha256"]
            spent += event["reserved_usd"]
        elif event["kind"] == "outcome":
            if event["call_id"] not in pending or event["call_id"] in done:
                raise ValueError("Orphan or duplicate outcome")
            done.add(event["call_id"])
            # Reservation is retained for missing usage; actual cost can be lower.
            spent -= event["reserved_usd"]
            spent += event.get("cost_usd") if event.get("cost_usd") is not None else event["reserved_usd"]
        else:
            raise ValueError("Unknown ledger event kind")
    return set(pending), spent


def _safe_to_continue(events: list[dict]) -> None:
    pending = {event["call_id"] for event in events if event["kind"] == "pending"}
    outcomes = {event["call_id"]: event for event in events if event["kind"] == "outcome"}
    if pending - set(outcomes):
        raise RuntimeError("Unresolved pending call: reconcile provider billing and response before continuation; no automatic retry")
    if any(event["result"] != "ok" for event in outcomes.values()):
        raise RuntimeError("Invalid or failed prior call: inspect retained response before continuation")


def _execute_locked(freeze_path: Path, ledger_path: Path, prior_path: Path | None = None) -> dict:
    frozen = load_freeze(freeze_path)
    if ledger_path == prior_path:
        raise ValueError("Pilot and full ledgers must be distinct")
    calls = {item["id"]: item for item in frozen["calls"]}
    prior = ledger_events(prior_path) if prior_path else []
    current = ledger_events(ledger_path)
    for event in prior + current:
        call = calls.get(event["call_id"])
        if not call or event["request_sha256"] != call["request_sha256"]:
            raise ValueError("Prior/current ledger request is not identical to this freeze")
    attempted_prior, prior_spent = _completed(prior)
    attempted_current, current_spent = _completed(current)
    if attempted_prior & attempted_current:
        raise ValueError("Call was attempted in both pilot and full ledgers")
    _safe_to_continue(prior)
    _safe_to_continue(current)
    # Preflight takes place before key lookup and before the first charge.
    preflight()
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    previous = current[-1]["event_sha256"] if current else "0" * 64
    spent = prior_spent + current_spent
    case_by_id = {case["id"]: case for case in load_cases()}
    resolved_models: dict[str, str] = {}
    for event in prior + current:
        if event["kind"] == "outcome" and event.get("returned_model"):
            name = calls[event["call_id"]]["model_name"]
            previous_model = resolved_models.setdefault(name, event["returned_model"])
            if previous_model != event["returned_model"]:
                raise RuntimeError("Returned model identity drift in existing ledger")
    for call in frozen["calls"]:
        if call["id"] in attempted_prior | attempted_current:
            continue
        if spent + call["reserved_usd"] > frozen["max_usd"]:
            raise RuntimeError("Frozen cumulative cost cap reached before next call")
        previous = append_event(ledger_path, {
            "kind": "pending", "freeze_sha256": frozen["freeze_sha256"],
            "call_id": call["id"], "request_sha256": call["request_sha256"],
            "reserved_usd": call["reserved_usd"], "utc": utc_now(),
        }, previous)
        attempted_current.add(call["id"])
        spent += call["reserved_usd"]
        start = time.monotonic()
        try:
            response, http_request_id = _post_response(call["request"], key)
            answer, failure = parse_response(response)
            if answer is not None:
                validation = validate_answer(answer, case_by_id[call["case_id"]])
            else:
                validation = []
            usage = response.get("usage") or {}
            input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
            rate = frozen["models"][call["model_name"]]
            cost = ((input_tokens * rate["input_usd_per_million"] +
                     output_tokens * rate["output_usd_per_million"]) / 1_000_000
                    if (type(input_tokens) is int and type(output_tokens) is int
                        and input_tokens >= 0 and output_tokens >= 0) else None)
            if cost is None:
                validation.append("missing_usage")
            returned = response.get("model")
            requested = rate["id"]
            if not isinstance(returned, str) or not returned.startswith(requested):
                validation.append("missing_or_wrong_returned_model")
            elif returned != resolved_models.setdefault(call["model_name"], returned):
                validation.append("returned_model_identity_drift")
            outcome = {"result": "ok" if answer is not None and not validation else "invalid",
                       "failure": failure, "validation": validation,
                       "answer": answer, "response_id": response.get("id"),
                       "http_request_id": http_request_id,
                       "returned_model": returned, "response_status": response.get("status"),
                       "incomplete_details": response.get("incomplete_details"),
                       "provider_response": response, "usage": usage, "cost_usd": cost}
        except urllib.error.HTTPError as exc:
            raw_body = exc.read(2_000_000).decode("utf-8", errors="replace")
            outcome = {"result": "provider_error", "failure": f"HTTP {exc.code}",
                       "http_status": exc.code, "http_request_id": exc.headers.get("x-request-id"),
                       "provider_error_body": raw_body, "validation": [], "answer": None,
                       "response_id": None, "returned_model": None, "response_status": None,
                       "usage": {}, "cost_usd": None}
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
            outcome = {"result": "transport_error", "failure": str(exc)[:300],
                       "validation": [], "answer": None, "response_id": None,
                       "returned_model": None, "response_status": None,
                       "usage": {}, "cost_usd": None}
        previous = append_event(ledger_path, {
            "kind": "outcome", "freeze_sha256": frozen["freeze_sha256"],
            "call_id": call["id"], "request_sha256": call["request_sha256"],
            "reserved_usd": call["reserved_usd"], "utc": utc_now(),
            "latency_seconds": round(time.monotonic() - start, 4), **outcome,
        }, previous)
        spent += (outcome["cost_usd"] if outcome["cost_usd"] is not None else
                  call["reserved_usd"]) - call["reserved_usd"]
        if outcome["result"] != "ok":
            raise RuntimeError("Provider or response validation failed; call retained without retry. Inspect the ledger.")
    return {"attempted": len(attempted_prior | attempted_current), "calls": len(calls),
            "conservative_spent_usd": round(spent, 5), "cap_usd": frozen["max_usd"]}


def execute(freeze_path: Path, ledger_path: Path, prior_path: Path | None = None) -> dict:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = ledger_path.with_name(ledger_path.name + ".lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Study ledger is locked by another executing process") from None
        return _execute_locked(freeze_path, ledger_path, prior_path)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    frozen = commands.add_parser("freeze", help="Write an immutable randomised call plan without API calls")
    frozen.add_argument("path", type=Path)
    frozen.add_argument("--families", type=int, default=12)
    frozen.add_argument("--models", nargs="+", default=list(MODELS))
    frozen.add_argument("--seed", type=int, default=240924)
    frozen.add_argument("--max-usd", type=float, default=25.0)
    frozen.add_argument("--max-output-tokens", type=int, default=4096)
    running = commands.add_parser("execute", help="Preflight then attempt each frozen call once")
    running.add_argument("freeze", type=Path)
    running.add_argument("ledger", type=Path)
    running.add_argument("--prior-ledger", type=Path)
    commands.add_parser("preflight", help="Check DNS/TCP/TLS without a key or paid request")
    args = parser.parse_args(argv)
    try:
        if args.command == "freeze":
            result = freeze(args.path, families=args.families, model_names=args.models,
                            seed=args.seed, max_usd=args.max_usd,
                            max_output_tokens=args.max_output_tokens)
            print(json.dumps({"freeze_sha256": result["freeze_sha256"],
                              "calls": len(result["calls"]), "cases": result["case_count"],
                              "reserved_usd": round(sum(c["reserved_usd"] for c in result["calls"]), 4)}))
        elif args.command == "preflight":
            preflight()
            print("OpenAI API endpoint is reachable through the configured HTTPS path; no key sent or model call made.")
        else:
            print(json.dumps(execute(args.freeze, args.ledger, args.prior_ledger)))
        return 0
    except Exception as exc:
        print("Study stopped: " + redact(str(exc)), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
