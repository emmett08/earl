"""A source-language change must not relabel retained experiment observations."""
import json
from pathlib import Path
import tomllib

import pytest

from eal import __version__
from eal.discovery import EXAMPLE, describe_language
from eal.parser import parse
from eal.semantics import validate
from experiments.model_transfer.run_state import RunState


@pytest.mark.parametrize('header', ['EAL/2', 'EAL/unknown', 'EAL/3-preview'])
def test_only_eal3_is_valid_even_with_newline_fields(header):
    program = parse(EXAMPLE.replace('EAL/3', header))
    diagnostic = next(d for d in validate(program) if d.code == 'unsupported_language')
    assert diagnostic.expected == 'EAL/3'


def test_current_discovery_and_experiment_plans_agree():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    assert __version__ == project['version']
    capabilities = describe_language()
    assert capabilities['implementation_version'] == __version__
    assert capabilities['languages'] == ['EAL/3']
    assert capabilities['source_syntax'] == 'EAL/3'
    for path in (root / 'experiments/model_transfer').glob('*plan.json'):
        plan = json.loads(path.read_text())
        assert plan['source_language'] == 'EAL/3'
        assert plan['protocol_version'] == '7.0.0'


@pytest.mark.parametrize('header', [None, 'EAL/2'])
def test_earlier_collection_plans_cannot_start_under_eal3(tmp_path, header):
    plan = {} if header is None else {'source_language': header}
    with pytest.raises(ValueError, match='New collection requires an EAL/3 plan'):
        with RunState(tmp_path, plan).locked():
            pytest.fail('Collection of a relabelled earlier treatment was admitted')
    assert not (tmp_path / 'execution-contract.json').exists()
