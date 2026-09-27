# Python cognitive complexity measurement contract

`cognitive_complexity.py` measures the control-flow and nesting score of the
Python fulfilment package at each frozen snapshot. It is a descriptive, partial
indicator of one aspect of code understandability. It measures neither
architectural adherence nor the future cost of changing the package. Use the
separate architecture review and follow-up tasks to assess those outcomes.

The rules follow [SonarSource's white paper, version 1.7](https://www.sonarsource.com/docs/CognitiveComplexity.pdf),
including structural increments for conditionals, loops and exception handlers;
hybrid increments for `elif` and `else`; one increment for each run of the same
Boolean operator; and nesting increments. Ternaries, nested functions, decorator
wrappers, classes and shorthand comprehensions follow the Python cases in the
[SonarPython visitor at commit `6be3971f`](https://github.com/SonarSource/sonar-python/blob/6be3971f50655b946921a975aba6ba8599fa48e5/python-frontend/src/main/java/org/sonar/python/metrics/CognitiveComplexityVisitor.java).
The collector also implements the white paper's recursion-cycle increment for
unambiguous, statically named calls within one file. It treats Python `match`
as one switch-like structure and an explicit case guard as an additional nested
conditional. These two extensions are specified here, not attributed to the
pinned SonarPython visitor.

The collector traverses every `.py` source in the selected root, excluding
hidden paths and `__pycache__`. It reports per-file hashes, total tree scores,
every function's score and an optional threshold count. A nested function's
score is included in its containing function; `included_in` identifies the
overlap. The `total` visits each syntax node once and must not be reconstructed
by summing all per-function scores. The threshold (15 by default) is a locator
for high-scoring functions, not a decision rule about technical debt.

The comparison mode matches functions by relative file and qualified name.
It reports score changes for unambiguous matched names separately from added
and removed functions, and records whether the set of Python files changed.
It does not imply that a renamed function is unchanged or that lower aggregate
scores after extraction demonstrate reduced maintenance effort. Compare
baseline, A and both B arms using identical source roots and the frozen
collector; interpret changed scope and any movement of complexity between
functions.

```
python3 experiments/architecture_extension_v2/metrics/cognitive_complexity.py \
  experiments/architecture_extension_v2/materials/base/fulfilment
python3 experiments/architecture_extension_v2/metrics/cognitive_complexity.py \
  experiments/architecture_extension_v2/results/snapshots/b_treatment/fulfilment \
  --compare-before experiments/architecture_extension_v2/results/snapshots/a/fulfilment
python3 -m unittest discover -s experiments/architecture_extension_v2/metrics -p 'test_*.py'
```

With no positional path, the program accepts the EAL command binding's JSON
request on stdin. Its `input` object requires `path` and may contain
`max_function_score` and `compare_before`; it returns `value`, `observed_at`,
`context` and a `request` echo. File hashes give the measured source identity.
The EAL tool binding pins this collector's bytes. If a source file cannot be
read or parsed, collection fails rather than assigning it zero complexity.
Unknown Python statement classes also cause an error.

**Verification.** Locally, all 25 function scores annotated in SonarPython's
[reference fixture at the pinned commit](https://github.com/SonarSource/sonar-python/blob/6be3971f50655b946921a975aba6ba8599fa48e5/python-frontend/src/test/resources/metrics/cognitive-complexities.py)
were checked against this collector. Twenty-four matched exactly. The recursive
function scored 3 here versus 2 in that fixture because the reference contains
an explicit recursion TODO and the white paper adds one point for recursion.
The corresponding file scores were 92 and 91. The local regression suite covers
the documented patterns and the additions; no SonarQube product-equivalence
claim follows from these checks.

**Boundaries.** Python can rebind names, monkey patch methods, import cycles and
dispatch dynamically. The local call graph cannot decide all runtime recursion
and does not use a zero score to assert its absence. Named functions defined
twice at the same lexical name are excluded from recursion inference and
function matching. Other languages, generated source outside the selected
tree, API coupling, duplicated paths, architectural dependencies, IaC and
deferred maintenance costs lie outside this measure. These are distinct
outcomes in the experiment.
