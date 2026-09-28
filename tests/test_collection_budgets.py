"""Collection budgets fail before any command can run or observation is stored."""

from __future__ import annotations

import json
import sys

import pytest

from eal.runtime import (
    MAX_COLLECTION_CONTEXT_BYTES,
    MAX_COLLECTION_EVIDENCE,
    MAX_COLLECTION_OUTPUT_BYTES,
    ReasoningService,
)
from eal.tool_acquisition import MAX_REQUEST_BYTES


def _source(count: int, *, large_input: str | None = None) -> str:
    declarations = []
    for index in range(count):
        input_clause = (f'input {{"payload":"{large_input}"}}; ' if index == count - 1 and large_input else "")
        declarations.append(
            f'evidence reading_{index} {{ tool runner; kind test; environment lab; '
            f'max_age 60; {input_clause}require "ok" == true; }}'
        )
    return '\n'.join([
        'language "EAL/2";',
        'environment lab { require "site" == "bench"; }',
        'tool runner { version "1"; }',
        *declarations,
        'reasoning measured { method "structured/1"; rationale "These observations support the scoped claim."; }',
        'claim works { statement "The checked operation works."; environment lab; }',
        'argument support { conclusion works; reasoning measured; evidence reading_0; }',
    ])


def _service(tmp_path, *, output_limit: int = 1024) -> tuple[ReasoningService, object]:
    marker = tmp_path / 'executed'
    script = tmp_path / 'collector.py'
    script.write_text(
        "import json, pathlib\n"
        "pathlib.Path('executed').touch()\n"
        "print(json.dumps({'value': {'ok': True}}))\n",
        encoding='utf-8',
    )
    registry = tmp_path / 'tools.toml'
    registry.write_text(
        '[tools.runner]\nkind="command"\nversion="1"\n'
        f'argv={json.dumps([sys.executable, str(script)])}\n'
        f'max_output_bytes={output_limit}\nmodel_access="general"\n',
        encoding='utf-8',
    )
    return ReasoningService(tmp_path, registry), marker


def _assert_no_effects(service: ReasoningService, marker) -> None:
    assert not marker.exists()
    assert service.store.list(kind='observation') == []
    assert service.store.list(kind='collection') == []


def test_context_limit_refuses_collection_before_executing(tmp_path):
    service, marker = _service(tmp_path)
    context = {'site': 'bench', 'padding': 'x' * MAX_COLLECTION_CONTEXT_BYTES}
    with pytest.raises(ValueError, match='Collection context exceeds'):
        service.collect(_source(1), context, model_access=True)
    _assert_no_effects(service, marker)


def test_evidence_count_limit_refuses_collection_before_executing(tmp_path):
    service, marker = _service(tmp_path)
    with pytest.raises(ValueError, match='evidence requests'):
        service.collect(_source(MAX_COLLECTION_EVIDENCE + 1), {'site': 'bench'}, model_access=True)
    _assert_no_effects(service, marker)


def test_later_oversized_request_does_not_execute_earlier_request(tmp_path):
    service, marker = _service(tmp_path)
    source = _source(2, large_input='x' * (MAX_REQUEST_BYTES - 2000))
    context = {'site': 'bench', 'padding': 'y' * 3000}
    with pytest.raises(ValueError, match="Tool request for 'reading_1' exceeds"):
        service.collect(source, context, model_access=True)
    _assert_no_effects(service, marker)


def test_aggregate_declared_output_budget_refuses_collection_before_executing(tmp_path):
    service, marker = _service(tmp_path, output_limit=MAX_COLLECTION_OUTPUT_BYTES // 2 + 1)
    with pytest.raises(ValueError, match='Collection output allowance exceeds'):
        service.collect(_source(2), {'site': 'bench'}, model_access=True)
    _assert_no_effects(service, marker)


def test_small_collection_still_executes_and_persists(tmp_path):
    service, marker = _service(tmp_path)
    result = service.collect(_source(1), {'site': 'bench'}, model_access=True)
    assert marker.exists()
    assert result['records']['reading_0']['status'] == 'ok'
    assert service.store.get(result['collection_id'], kind='collection')['records']['reading_0']['status'] == 'ok'
