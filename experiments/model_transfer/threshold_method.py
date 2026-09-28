"""Host-installed threshold computation for synthetic measurements."""
from eal.methods import MethodContract, default_registry


def compare_measurement(report: dict) -> dict:
    """A negative comparison remains a completed, usable calculation."""
    value, threshold = report['reading'], report['threshold']
    meets = value <= threshold if report['direction'] == 'at_most' else value >= threshold
    return {'reading': value, 'threshold': threshold, 'meets': meets, 'fails': not meets}


NUMBER = {'type': 'number', 'minimum': 0, 'maximum': 1e9}
CONTRACT = MethodContract(
    identifier='experiment/threshold/1', evidence_kind='threshold_measurement',
    input_schema={'type': 'object', 'properties': {
        'reading': NUMBER, 'threshold': NUMBER,
        'direction': {'type': 'string', 'enum': ['at_most', 'at_least']}},
        'required': ['reading', 'threshold', 'direction'], 'additionalProperties': False},
    query_schema={'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False},
    output_schema={'type': 'object', 'properties': {
        'reading': NUMBER, 'threshold': NUMBER,
        'meets': {'type': 'boolean'}, 'fails': {'type': 'boolean'}},
        'required': ['reading', 'threshold', 'meets', 'fails'], 'additionalProperties': False},
    outputs={'reading': 'basis', 'threshold': 'basis', 'meets': 'boolean', 'fails': 'boolean'},
    quantities=(), exact_unit=False, implementation=compare_measurement,
    implementation_version='model-transfer-threshold-1',
)


def registry():
    return default_registry().with_method(CONTRACT)
