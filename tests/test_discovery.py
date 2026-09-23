"""A text model must receive an executable reference through the installed API."""
from eal.discovery import describe_language
from eal.parser import parse
from eal.semantics import validate


def test_discovery_example_is_executable_and_contracts_available():
    reference = describe_language()
    assert not validate(parse(reference["example"]))
    assert reference["languages"] == ["EAL/2"]
    assert reference["method_registry_fingerprint"]
    assert reference["typed_bindings"]["methods"]
    assert reference["typed_bindings"]
    assert "query JSON" in reference["syntax"]["claim"]
    assert set(reference["methods"]) == {
        "structured/1", "deductive/1", "inductive/1", "abductive/1", "causal/1",
        "counterfactual/1", "analogical/1", "temporal/1",
    }
