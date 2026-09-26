"""Bounded computations for distinct engineering reasoning tasks.

A successful computation is conditional on its supplied model and evidence.
Argument-level ``require`` predicates state what result supports a conclusion.
"""
from __future__ import annotations

import itertools
import hashlib
import json
import math
import operator
import re
from fractions import Fraction
from statistics import NormalDist, stdev

from .builtin_methods import BUILTIN_SPECS

MODE_KINDS = {mode: spec.evidence_kind for mode, spec in BUILTIN_SPECS.items()}
MAX_ITEMS = 10_000
MAX_ATOMS = 12
MAX_FORMULA_NODES = 512
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")


def evidence_kind(method: str, registry=None):
    from .methods import default_registry
    contract = (registry or default_registry()).get(method)
    return contract.evidence_kind if contract else None


def validate_mode(method: str, kinds: list[str], registry=None) -> list[str]:
    """Resolve the host registry and check designated computational evidence."""
    from .methods import default_registry
    contract = (registry or default_registry()).get(method)
    if contract is None:
        return [f"Unknown registered reasoning method {method!r}; use an installed versioned identifier"]
    if not isinstance(kinds, list) or any(not isinstance(k, str) for k in kinds):
        return ["Evidence kinds must be a list of strings"]
    if len(kinds) > 4096:
        return ["At most 4096 evidence entries are allowed"]
    required = contract.evidence_kind
    if required is not None and kinds.count(required) != 1:
        return [f"Method {method!r} requires exactly one evidence entry of kind {required!r}"]
    return []


def _object(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"{label} requires exactly these fields: {', '.join(fields)}")
    return value


def _list(value, label, minimum=1, maximum=MAX_ITEMS):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{label} must be a list with {minimum}..{maximum} entries")
    return value


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    if not -1e100 <= value <= 1e100:
        raise ValueError(f"{label} must be finite and within [-1e100, 1e100]")
    return value


def _integer(value, label, minimum=0, maximum=1_000_000_000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be an integer in [{minimum}, {maximum}]")
    return value


def _name(value, label):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be an identifier of at most 64 characters")
    return value


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(f"{label} must contain 1..4096 characters and be nonblank")
    return value


def _probability(value, label):
    value = _number(value, label)
    if not 0 <= value <= 1:
        raise ValueError(f"{label} must be in [0, 1]")
    return value


def _result(ok, reason, **details):
    return {"status": "supported" if ok else "unsupported",
            "reasons": [reason], "details": details}


def _check_json(value):
    """Bound every input before mode-specific traversal, including cycles."""
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if count > 100_000 or depth > 64:
            raise ValueError("Evidence exceeds JSON node or depth limits")
        if item is None or isinstance(item, bool):
            continue
        if isinstance(item, str):
            if len(item) > 4096:
                raise ValueError("Evidence strings are limited to 4096 characters")
            item.encode("utf-8")
        elif isinstance(item, (int, float)):
            _number(item, "Evidence number")
        elif isinstance(item, dict):
            if len(item) > MAX_ITEMS:
                raise ValueError("Evidence object exceeds member limit")
            for key, child in item.items():
                if not isinstance(key, str) or len(key) > 4096:
                    raise ValueError("Evidence object keys must be bounded strings")
                key.encode("utf-8")
                pending.append((child, depth + 1))
        elif isinstance(item, list):
            if len(item) > MAX_ITEMS:
                raise ValueError("Evidence list exceeds entry limit")
            pending.extend((child, depth + 1) for child in item)
        else:
            raise ValueError("Evidence must contain only JSON values")


def _deductive(value):
    _object(value, ("premises", "conclusion"), "logical_case")
    premises = _list(value["premises"], "Logical premises", minimum=0, maximum=128)
    atoms, budget = set(), [MAX_FORMULA_NODES]

    def check(formula, depth=0):
        budget[0] -= 1
        if budget[0] < 0 or depth > 32:
            raise ValueError("Logical formulas exceed 512 total nodes or depth 32")
        if isinstance(formula, str):
            atoms.add(_name(formula, "Propositional atom"))
            return
        if not isinstance(formula, dict) or len(formula) != 1:
            raise ValueError("A formula is an atom or one not/and/or/implies object")
        op, operand = next(iter(formula.items()))
        if op == "not":
            check(operand, depth + 1)
        elif op in ("and", "or", "implies"):
            _list(operand, f"{op} operands", minimum=2, maximum=2 if op == "implies" else 128)
            for child in operand:
                check(child, depth + 1)
        else:
            raise ValueError(f"Unsupported logical operator {op!r}")

    for formula in [*premises, value["conclusion"]]:
        check(formula)
    if len(atoms) > MAX_ATOMS:
        raise ValueError("Finite deduction supports at most 12 distinct atoms")

    def truth(formula, assignment):
        if isinstance(formula, str):
            return assignment[formula]
        op, operand = next(iter(formula.items()))
        if op == "not":
            return not truth(operand, assignment)
        if op == "and":
            return all(truth(item, assignment) for item in operand)
        if op == "or":
            return any(truth(item, assignment) for item in operand)
        return not truth(operand[0], assignment) or truth(operand[1], assignment)

    atoms = sorted(atoms)
    satisfying = 0
    counterexample = None
    for values in itertools.product((False, True), repeat=len(atoms)):
        assignment = dict(zip(atoms, values))
        if all(truth(formula, assignment) for formula in premises):
            satisfying += 1
            if counterexample is None and not truth(value["conclusion"], assignment):
                counterexample = assignment
    consistent = satisfying > 0
    entailed = counterexample is None
    return _result(consistent,
                   "Finite entailment established with satisfiable premises" if consistent and entailed
                   else "Premises are inconsistent" if not consistent else "A counterexample refutes entailment",
                   entailed=entailed, consistent_premises=consistent, counterexample=counterexample,
                   atoms=atoms, valuations=2 ** len(atoms), satisfying_premise_valuations=satisfying)


def _inductive(value):
    _object(value, ("successes", "trials", "confidence"), "sample")
    n = _integer(value["trials"], "trials", minimum=1)
    k = _integer(value["successes"], "successes", maximum=n)
    confidence = _number(value["confidence"], "confidence")
    if not 0.001 <= confidence <= 0.999999:
        raise ValueError("confidence must be in [0.001, 0.999999]")
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    p = k / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return _result(True, "Wilson interval computed under the stated binomial sampling model",
                   estimate=p, lower=max(0.0, centre - half), upper=min(1.0, centre + half),
                   sample_size=n, successes=k, confidence=confidence, method="wilson_score",
                   interpretation="approximate_frequentist", assumptions_verified=False)


def _abductive(value):
    _object(value, ("observed", "candidates"), "hypotheses")
    _text(value["observed"], "observed evidence description")
    candidates = _list(value["candidates"], "candidates", minimum=2, maximum=128)
    priors, log_weights = {}, {}
    for item in candidates:
        _object(item, ("name", "prior", "likelihood"), "hypothesis")
        name = _name(item["name"], "hypothesis name")
        if name in priors:
            raise ValueError("Hypothesis names must be unique")
        prior = _probability(item["prior"], "prior")
        likelihood = _probability(item["likelihood"], "likelihood")
        priors[name] = prior
        log_weights[name] = (math.log(prior) + math.log(likelihood)
                             if prior > 0 and likelihood > 0 else -math.inf)
    total_prior = math.fsum(priors.values())
    if not math.isclose(total_prior, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("Prior probabilities must sum to 1 within absolute tolerance 1e-9")
    maximum = max(log_weights.values())
    if maximum == -math.inf:
        return _result(False, "The supplied hypotheses assign zero probability to the observed evidence",
                       posterior={}, best=None, ties=[], assumptions_verified=False)
    weights = {name: math.exp(weight - maximum) for name, weight in log_weights.items()}
    normaliser = math.fsum(weights.values())
    posterior = {name: weight / normaliser for name, weight in weights.items()}
    best_probability = max(posterior.values())
    ties = sorted(name for name, probability in posterior.items()
                  if math.isclose(probability, best_probability, rel_tol=0.0, abs_tol=1e-12))
    return _result(True, "Posterior probabilities computed within the supplied finite hypothesis model",
                   posterior=posterior, best=ties[0] if len(ties) == 1 else None,
                   best_posterior=best_probability, ties=ties if len(ties) > 1 else [],
                   log_evidence_probability=maximum + math.log(normaliser) - math.log(total_prior),
                   assumptions_verified=False)


def _causal(value):
    _object(value, ("assignment", "treatment", "control"), "experiment")
    if value["assignment"] != "randomised":
        raise ValueError("This causal calculation requires declared randomised assignment")
    groups = []
    for name in ("treatment", "control"):
        groups.append([_number(item, name) for item in _list(value[name], name, minimum=2)])
    treatment, control = groups
    # Subtract the represented means before rounding: two large, neighbouring
    # integer means must not collapse to the same binary64 value and erase an
    # observed treatment effect. Fraction also retains each supplied float's
    # exact binary value; it does not infer additional measurement precision.
    mt = sum(map(Fraction, treatment), Fraction()) / len(treatment)
    mc = sum(map(Fraction, control), Fraction()) / len(control)
    def numeric(value):
        rounded = value.numerator if value.denominator == 1 else float(value)
        if value and rounded == 0:
            raise ValueError("Computed mean or contrast underflows the representable number range")
        return rounded

    # Compute standard deviations before combining their contributions. Forming
    # floating variances first can underflow even when the final square root is
    # representable (for example, a standard error of 1e-200).
    se = math.hypot(stdev(treatment) / math.sqrt(len(treatment)),
                    stdev(control) / math.sqrt(len(control)))
    if se == 0 and any(any(item != group[0] for item in group) for group in groups):
        raise ValueError("Computed standard error underflows the representable number range")
    return _result(True, "Randomised two-group mean contrast computed; assignment and causal assumptions require evidence",
                   estimate=numeric(mt - mc), standard_error=se,
                   treatment_mean=numeric(mt), control_mean=numeric(mc),
                   treatment_size=len(treatment), control_size=len(control),
                   sample_size=len(treatment) + len(control), assumptions_verified=False)


def _counterfactual(value):
    _object(value, ("variables", "intervention", "outcome"), "causal_model")
    variables = value["variables"]
    if not isinstance(variables, dict) or not 1 <= len(variables) <= 32:
        raise ValueError("variables must contain 1..32 structural equations")
    equations = {}
    for name, equation in variables.items():
        _name(name, "variable name")
        _object(equation, ("intercept", "coefficients", "noise"), "structural equation")
        coefficients = equation["coefficients"]
        if not isinstance(coefficients, dict) or len(coefficients) > 32:
            raise ValueError("coefficients must map at most 32 variables to numbers")
        if any(parent not in variables for parent in coefficients):
            raise ValueError("Structural equation references an unknown parent variable")
        equations[name] = (_number(equation["intercept"], "intercept"),
                           {parent: _number(c, "coefficient") for parent, c in coefficients.items()},
                           _number(equation["noise"], "noise"))
    _object(value["intervention"], ("variable", "value"), "intervention")
    changed = _name(value["intervention"]["variable"], "intervention variable")
    outcome = _name(value["outcome"], "outcome")
    if changed not in equations or outcome not in equations:
        raise ValueError("Intervention and outcome must name declared variables")
    setting = _number(value["intervention"]["value"], "intervention value")
    order = []
    remaining = dict(equations)
    while remaining:
        ready = sorted(name for name, (_, parents, _) in remaining.items()
                       if all(parent in order for parent in parents))
        if not ready:
            raise ValueError("Structural equations must be acyclic, including zero-coefficient references")
        for name in ready:
            order.append(name)
            del remaining[name]

    def solve(intervene):
        result = {}
        for name in order:
            intercept, parents, noise = equations[name]
            if intervene and name == changed:
                result[name] = setting
            else:
                terms = [intercept, noise, *(c * result[parent] for parent, c in parents.items())]
                result[name] = sum(terms) if all(type(term) is int for term in terms) else math.fsum(terms)
            _number(result[name], "Computed structural value")
        return result

    factual, counterfactual = solve(False), solve(True)
    return _result(True, "Intervention evaluated in an acyclic affine model with the same supplied exogenous values",
                   factual=factual[outcome], counterfactual=counterfactual[outcome],
                   difference=counterfactual[outcome] - factual[outcome],
                   factual_values=factual, counterfactual_values=counterfactual,
                   outcome=outcome, evaluation_order=order, assumptions_verified=False)


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


def _temporal(value):
    _object(value, ("start", "end", "max_gap", "events", "property", "semantics"), "trace")
    if value["semantics"] != "sampled":
        raise ValueError("Temporal mode supports only explicitly sampled semantics")
    start, end, max_gap = [_number(value[key], key) for key in ("start", "end", "max_gap")]
    if start > end or max_gap <= 0:
        raise ValueError("Trace requires start <= end and max_gap > 0")
    _object(value["property"], ("operator", "value"), "trace property")
    comparisons = {"lt": operator.lt, "le": operator.le, "eq": operator.eq,
                   "ne": operator.ne, "ge": operator.ge, "gt": operator.gt}
    op = value["property"]["operator"]
    if not isinstance(op, str) or op not in comparisons:
        raise ValueError("Trace property operator must be lt/le/eq/ne/ge/gt")
    threshold = _number(value["property"]["value"], "property value")
    events = _list(value["events"], "events")
    times, failures = [], []
    for event in events:
        _object(event, ("time", "value"), "trace event")
        time = _number(event["time"], "event time")
        observation = _number(event["value"], "event value")
        if not start <= time <= end or times and time <= times[-1]:
            raise ValueError("Events must be strictly time-ordered and within the declared interval")
        times.append(time)
        if not comparisons[op](observation, threshold):
            failures.append(time)
    largest_gap = max((b - a for a, b in zip(times, times[1:])), default=0.0)
    coverage = times[0] == start and times[-1] == end and largest_gap <= max_gap
    holds = not failures
    return _result(coverage,
                   "The sampled property holds throughout the complete declared sampling contract" if coverage and holds
                   else "The sampling contract has a gap or missing endpoint" if not coverage
                   else "The sampled trace contains a property violation",
                   holds=holds, coverage=coverage, sample_size=len(events), largest_gap=largest_gap,
                   violation_count=len(failures), violation_times=failures,
                   semantics="sampled", continuous_truth_established=False)


_COMPUTATIONS = {"deductive": _deductive, "inductive": _inductive, "abductive": _abductive,
                 "causal": _causal, "counterfactual": _counterfactual,
                 "analogical": _analogical, "temporal": _temporal}


def assess_mode(method: str, evidence: list[dict], premises: list[dict], registry=None) -> dict:
    """Return a bounded versioned method result without executing tools or trusting prose.

    Evidence entries are ``{id, kind, value}``; premise entries contain ``status``.
    The caller separately checks premise support and argument requirements.
    """
    from .methods import check_implementation_identity, default_registry, execute_extension, schema_errors
    registry = registry or default_registry()

    def identified(result):
        return {**result, "method": method,
                "reasons": [f"Method {method}: {reason}" for reason in result["reasons"]]}

    try:
        if not isinstance(evidence, list) or len(evidence) > 4096:
            raise ValueError("Evidence must be a list with at most 4096 entries")
        if not isinstance(premises, list) or len(premises) > 4096:
            raise ValueError("Premises must be a list with at most 4096 entries")
        if any(not isinstance(item, dict) or not isinstance(item.get("kind"), str) or
               "value" not in item or not isinstance(item.get("id"), str) for item in evidence):
            raise ValueError("Each evidence entry requires id, kind and value")
        if len({item["id"] for item in evidence}) != len(evidence):
            raise ValueError("Evidence identifiers must be unique")
        if any(not isinstance(item, dict) for item in premises):
            raise ValueError("Premise entries must be objects")
        # The authored method still consumes evidence entries. It must not make
        # malformed, nonfinite or cyclic payloads usable merely because it has
        # no designated numerical calculation.
        for item in evidence:
            _check_json(item["value"])
        errors = validate_mode(method, [item["kind"] for item in evidence], registry=registry)
        if errors:
            return identified({"status": "unsupported", "reasons": errors, "details": {}})
        contract = registry.get(method)
        if contract.builtin_mode is not None:
            check_implementation_identity(contract)
        selected = None
        if contract.builtin_mode == "structured":
            available = bool(evidence) or any(item.get("status") in ("supported", "contested") for item in premises)
            payload = {}
        else:
            selected = next(item for item in evidence if item["kind"] == contract.evidence_kind)
            payload = selected["value"]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
        input_digest = hashlib.sha256(encoded).hexdigest()
        if len(encoded) > contract.max_input_bytes:
            raise ValueError("Method input exceeds byte limit")
        errors = schema_errors(payload, contract.input_schema)
        if errors:
            raise ValueError("Method input contract violation: " + "; ".join(errors))
        if contract.builtin_mode == "structured":
            result = _result(available, "Authored support is available; prose sufficiency is not mechanically established"
                             if available else "Structured reasoning requires evidence or a supported premise",
                             **contract.implementation(payload))
        else:
            result = (contract.implementation(payload) if contract.builtin_mode
                      else execute_extension(contract, payload))
        # Domain checks inside a computation can be stricter than the schema;
        # neither replaces the registered input/output contract. In particular,
        # bounded inputs can produce a numerical result outside the output's
        # represented range. A failed computation may intentionally return only
        # diagnostic fields, so the success schema applies to usable results.
        if result["status"] == "supported":
            errors = schema_errors(result["details"], contract.output_schema)
            if errors:
                raise ValueError("Method output contract violation: " + "; ".join(errors))
            encoded = json.dumps(result["details"], sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False).encode("utf-8")
            if len(encoded) > contract.max_output_bytes:
                raise ValueError("Method output exceeds byte limit")
        # Host provenance is not a method output and cannot overwrite a field
        # supplied under the registered result contract.
        if selected is not None:
            result["evidence_id"] = selected["id"]
            # Bind the computation to the exact finite JSON input it consumed.
            # Adequacy can then detect a collection substituted after assessment,
            # including an untyped method input that has no proposition query.
            result["input_digest"] = input_digest
        return identified(result)
    except (ValueError, TypeError, OverflowError, RecursionError, KeyError, UnicodeError) as exc:
        return identified(_result(False, f"Method evaluation failed: {exc}"))
