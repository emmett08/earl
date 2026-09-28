"""Compare exactly the declared scalar feature correspondences."""
from __future__ import annotations


from .strategy import BuiltinStrategy
from .validation import _list, _name, _object, _result


def _analogical(value):
    _object(value, ("relevant_features", "source", "target"), "analogy")
    features = [_name(feature, "feature") for feature in
                _list(value["relevant_features"], "relevant_features", maximum=256)]
    if len(set(features)) != len(features):
        raise ValueError("Relevant feature names must be unique")
    source, target = value["source"], value["target"]
    if not isinstance(source, dict) or not isinstance(target, dict):
        raise ValueError("Source and target must be feature maps")
    missing = sorted(feature for feature in features if feature not in source or feature not in target)
    if missing:
        return _result(False, "The relevant-feature mapping is incomplete", complete=False,
                       missing=missing, match_fraction=None, mismatches=[], assumptions_verified=False)

    def scalar(item):
        if isinstance(item, (dict, list)):
            raise ValueError("Mapped feature values must be JSON scalars")
        return item

    def equal(left, right):
        scalar(left)
        scalar(right)
        numeric = lambda x: isinstance(x, (float, int)) and not isinstance(x, bool)
        return (type(left) is type(right) or numeric(left) and numeric(right)) and left == right

    mismatches = [feature for feature in features if not equal(source[feature], target[feature])]
    return _result(True, "Declared features compared exactly; feature relevance and conclusion transfer remain authored reasoning",
                   complete=True, feature_count=len(features), matched=len(features) - len(mismatches),
                   match_fraction=(len(features) - len(mismatches)) / len(features), mismatches=mismatches,
                   missing=[], interpretation="feature_correspondence", assumptions_verified=False)


STRATEGY = BuiltinStrategy("analogical", _analogical)
