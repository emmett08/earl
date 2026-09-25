"""The built-in contract source remains identical while metadata moves modules."""
import json
from pathlib import Path
import sys

from eal.builtin_methods import BUILTIN_SPECS
from eal.extensions import RMS_CONTRACT
from eal.methods import default_registry
from eal.modes import MODE_KINDS, assess_mode
from eal.propositions import OUTPUTS, QUERY_FIELDS


SNAPSHOT = Path(__file__).parent / 'fixtures' / 'builtin-registry-py312.json'
BASELINE_FINGERPRINT_PY312 = '31ad450d8b06500f2e294d0c9e1d5d5d7b9397a1e4d089f3a598b92494e228e5'


def test_descriptors_equal_the_pre_refactor_snapshot():
    expected = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    actual = default_registry().describe()
    # The executable code digest contains CPython bytecode. All other fields,
    # including the numerical implementation source digests, are portable.
    if sys.implementation.name == 'cpython' and sys.version_info[:2] == (3, 12):
        assert actual == expected
        assert default_registry().fingerprint == BASELINE_FINGERPRINT_PY312
    else:
        for descriptor in (*expected.values(), *actual.values()):
            descriptor.pop('implementation_code_digest')
        assert actual == expected


def test_public_method_metadata_is_derived_from_the_versioned_specs():
    registry = default_registry()
    assert MODE_KINDS == {mode: spec.evidence_kind for mode, spec in BUILTIN_SPECS.items()}
    assert OUTPUTS == {mode: spec.outputs for mode, spec in BUILTIN_SPECS.items() if spec.outputs}
    assert QUERY_FIELDS == {mode: spec.query_fields for mode, spec in BUILTIN_SPECS.items() if spec.outputs}
    for mode, spec in BUILTIN_SPECS.items():
        contract = registry.get(spec.identifier)
        assert contract.builtin_mode == mode
        assert contract.evidence_kind == spec.evidence_kind
        assert contract.query_fields == spec.query_fields
        assert contract.outputs == spec.outputs
        assert contract.exact_unit == spec.exact_unit
        assert contract.implementation_version == spec.implementation_version


def test_installed_method_preserves_builtin_contracts_and_uses_the_same_dispatch():
    baseline = default_registry()
    installed = baseline.with_method(RMS_CONTRACT)
    assert baseline.get(RMS_CONTRACT.identifier) is None
    assert installed.fingerprint != baseline.fingerprint
    assert all(installed.describe()[key] == value for key, value in baseline.describe().items())
    computed = assess_mode(RMS_CONTRACT.identifier, [
        {'id': 'sample', 'kind': RMS_CONTRACT.evidence_kind,
         'value': {'origin': 0, 'samples': [5, -5]}}], [], registry=installed)
    assert computed['status'] == 'supported'
    assert computed['details']['rms'] == 5
