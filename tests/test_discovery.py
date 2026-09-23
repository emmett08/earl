"""A text model must receive an executable reference through the installed API."""
from eal.discovery import describe_language
from eal.parser import parse
from eal.semantics import validate


def test_discovery_example_is_executable_and_contracts_available():
    reference = describe_language()
    assert not validate(parse(reference["example"]))
    assert reference["languages"] == ["EAL/0.1", "EAL/0.2"]
    assert reference["typed_bindings"]
    assert "query JSON" in reference["syntax"]["claim"]
    assert set(reference["methods"]) == {
        "structured", "deductive", "inductive", "abductive", "causal",
        "counterfactual", "analogical", "temporal",
    }
