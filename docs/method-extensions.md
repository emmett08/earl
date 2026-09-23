# Host-registered reasoning methods

EAL/0.3 can call a new reasoning calculation without extending its grammar. The host registers a pure implementation and its exact versioned contract. Source selects that contract by name; it cannot import a module, supply Python code or choose an executable path.

```eal
reasoning rms_method {
  method "engineering/rms/1";
  rationale "Compute RMS deviation from the declared origin over this finite sample.";
}
```

The legacy `mode causal;` declaration retains its meaning. Built-in methods also have explicit identifiers such as `causal/1`. An extension cannot replace a built-in identity or alias. `method` declarations require EAL/0.3; EAL/0.1 and EAL/0.2 continue to use their existing syntax.

## Runnable engineering example

The optional `engineering/rms/1` method computes root-mean-square deviation from a declared origin. It has a different algorithm and evidence shape from the existing methods. The source in [`examples/rms.eal`](../examples/rms.eal) uses a typed pressure proposition, `query {"origin":0};`, and `result "rms" <= 5;`. Its observation contains `{ "origin": 0, "samples": [3, 4] }` in kPa. The result is approximately 3.535534 kPa.

Enable the example explicitly in the operator's command:

```sh
python -m eal.cli --workspace . --registry examples/rms-tools.toml \
  --methods eal.extensions:example_registry \
  validate examples/rms.eal

python -m eal.server --workspace . --registry examples/rms-tools.toml \
  --methods eal.extensions:example_registry
```

The server uses ordinary MCP discovery, collection, reasoning and explanation. For the supplied synthetic historical observation, use context `{"site":"bench"}` and assessment time `2026-09-23T12:00:00Z`. The observation is intentionally not refreshed when reread. Without the registered host factory, the same source reports an unknown method.

Python hosts can use the same registry:

```python
from eal.extensions import example_registry
from eal.runtime import ReasoningService

service = ReasoningService(".", "examples/rms-tools.toml",
                           method_registry=example_registry())
```

## Contract and interpreter obligations

`MethodContract` carries the following meanings:

| Field | Required meaning |
|---|---|
| `identifier` | Stable name and positive integer version, for example `engineering/rms/1` |
| `evidence_kind` | Exactly one computational evidence source of this kind is required |
| `input_schema` | Complete typed payload shape, numerical/string/collection bounds and required fields |
| `query_schema` | Exactly the fields defining the mathematical question; all are required and present in the input schema |
| `output_schema` | Complete typed result shape that a successful callback must return |
| `outputs` | Claim-addressable result paths and their `boolean`, `basis` or `dimensionless` interpretation |
| `quantities` | Permitted input measurement quantities |
| `exact_unit` | Whether input and proposition units must be identical; required when query constants carry the measurement unit |
| `implementation` | Trusted, importable module-level Python function from one JSON object to one JSON object |
| `implementation_version` | Explicit version of the implementation, including relevant external dependencies |
| resource limits | Maximum input/output bytes, address space and elapsed execution time |

A registry is extended using `default_registry().with_method(contract)`. Registration copies contracts; modifying the original schema or a returned discovery object cannot change the installed meaning. Duplicate identities and reserved built-in execution profiles are rejected. Non-function callables, closures, lambdas and functions defined only in an interactive `__main__` module are rejected explicitly.

Before evaluation, name resolution locates the exact registered method, checks the evidence kind, query schema, quantity, output path and predicate type. Runtime binding checks subject, environment, model or episode scope, whole interval containment and exact equality of the declared query fields. It records the entire supplied formal problem and digest. Changed observations may change a conclusion; a changed mathematical question cannot silently answer the old claim.

Input and output schemas use this bounded JSON-schema subset: `type` (`object`, `array`, `string`, `number`, `integer`, `boolean`, `null`, or bounded `json`), `properties`, `required`, `additionalProperties` (false or a schema), `items`, `minItems`, `maxItems`, `minimum`, `maximum`, `minLength`, `maxLength`, `enum` and `anyOf`. Unknown schema features fail registration. Booleans are never numbers or integers. Every alternative shares the validation node/depth budget. Method algorithms impose any stronger domain conditions their schemas cannot express; built-in formula and causal-model procedures retain their existing checks.

An extension returns only its output object. The interpreter assigns computation status after schema validation; a callback cannot return an unchecked status envelope that bypasses those checks. Exceptions, malformed or nonfinite results, output overflow, process failure and timeouts produce an unusable computation with diagnostics. A correctly computed zero, false predicate or other negative finding remains usable for the appropriate formal proposition.

## Units and interpretation

A proposition's `quantity` and `unit` name the **input measurement basis**. Each output has its own interpretation. RMS has `basis` interpretation and uses the pressure unit; `sample_size` has `dimensionless` interpretation and uses unit `1`. A sample count of two pressure measurements therefore never means two kPa. Boolean outputs have no numerical unit. The assessment returns the actual comparison value and `output_unit` explicitly.

The registered author must state this interpretation correctly. A typed schema alone cannot establish that a numerical algorithm computes its declared statistic. `exact_unit=False` permits output conversion and is appropriate only when query matching does not reinterpret dimensional constants. The RMS method requires exact units because its `origin` is dimensional. Adding a method therefore includes tests of its mathematical procedure and unit interpretation, not just successful registration.

## Execution and reproducibility

Custom functions execute in a fresh POSIX worker process created with `spawn`, so calls from threaded MCP servers do not inherit thread locks. Worker startup has a separate five-second limit; the registered execution timeout begins after the worker is ready. The runtime enforces elapsed timeout, CPU/address-space limits and bounded JSON input/output. It stops a timed-out worker and returns a diagnostic; it does not wait indefinitely for a cooperative callback. Callback stdout and stderr cannot corrupt MCP transport. The argument and observation objects in the caller cannot be mutated through the child process.

The host must supply pure, trusted functions. The process boundary is a resource control, not a filesystem or network sandbox, and it cannot establish purity. POSIX process resource limits are currently required for custom functions; unsupported platforms return an explicit diagnostic. Built-ins retain their existing finite algorithms and resource bounds.

Discovery and assessments record a registry fingerprint, complete contracts, entry-point source and loaded-code digests and declared implementation versions. Entry-point digests are captured at registration; subsequent discovery does not reopen implementation files or change the installed identity. The worker compares its loaded entry-point code with the registered digest before executing, rejecting a changed implementation. The fingerprint covers contract meaning, output/unit policy and limits. It does **not** hash every imported dependency, closure value, global variable or operating-system library. Hosts must version those dependencies and preserve the environment needed to reproduce their registered calculations. Changing a method implementation or contract should use a new versioned identifier and implementation version; a source digest is evidence of entry-point identity, not a proof of mathematical correctness.
