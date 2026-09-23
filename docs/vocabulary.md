# Executable vocabulary

EAL/0.2 adds a formal scalar proposition and its binding to a computation. EAL/0.1 remains supported. EAL/0.3 adds registered method selection and compositional objections and defences; earlier versions retain their original objection behaviour. A declaration name identifies one object; references are resolved before evaluation, including forward references. Clause order follows the grammar.

| Spelling | Meaning and operands | Evaluation effect or boundary |
|---|---|---|
| `claim` | A named proposition, its explanatory `statement`, and `environment` | Receives the status of its applicable supporting arguments. The statement is never interpreted as a formula. |
| `argument` | One `conclusion`, one `reasoning` method, and named grounds | Required grounds combine conjunctively. Alternative arguments for a claim remain distinct. |
| `premises` | Claims required by an argument or EAL/0.3 objection | Their derivations and final acceptability are evaluated. Shared identity does not create additional observations or independence. |
| `reasoning` | A named method application with a `mode` or versioned `method`, `rationale` and optional `backing` observations | Computational modes calculate a specified result; structured support records an authored relation. Rationale text is not executable logic. |
| `evidence` | A collection and eligibility specification; within an argument, references to those specifications | Actual observations are separate runtime records. Records must match the source, tool, inputs and environment, and satisfy freshness and value predicates. |
| `kind` | The observation's method-specific data contract | A logical case cannot substitute for a sample or intervention experiment. |
| `tool` | A configured observation producer with a declared `version` and execution `mode` | Host configuration supplies its executable. Source never defines command paths. |
| `deterministic`, `nondeterministic` | The declared variability of tool execution | Neither word certifies validity, truth or statistical independence. |
| `environment` | A named conjunction of predicates over supplied context | Failed predicates make dependent claims out of scope. Context identity does not establish physical conditions. |
| `assumption` | A stated proposition requiring validation evidence within an optional interval | Missing validation or expiry removes current support. It does not prove the assumption false. This profile requires empirical support; it has no separate hypothetical assumption discharge calculus. |
| `validate` | An assumption's required evidence reference | Names the observation used to support applicability; it is not an organisational approval. |
| `valid_from`, `valid_until` | Timezone-aware instants bounding applicability | Intervals are half open: the starting instant is included and the ending instant excluded. |
| `max_age` | Maximum age in seconds of the original observation | Age equal to the limit is usable. Reimporting a file does not refresh its observation time. |
| `require` | A field path, scalar comparison and expected value | Looks up a context, observation or computed output field according to its declaration. Missing fields and incompatible types fail the condition. |
| `proposition` | A typed, explicitly scoped formal query and result condition attached to a claim | Its `subject`, `quantity`, `unit`, `scope`, interval, `query` and result must correspond to the bound computation. Available in EAL/0.2 and later. |
| `query` | The defining fields of the formal problem, excluding the live observations allowed by its method contract | Rejects a returned calculation of a different problem. JSON is a bounded method data structure, never executable code. |
| `result` | A method output path, comparison and scalar threshold | States the formal conclusion being checked. A successful negative finding can support an explicitly negative condition. |
| `binding` | The designated computational evidence reference for a typed claim's argument | Checks the input envelope, method query, identity, dimensions and interval before applying the result condition. It cannot authenticate measurement provenance. |
| `objection` | A supported challenge to a claim, assumption, reasoning application or EAL/0.3 argument/objection | EAL/0.3 permits evidence and claim subarguments as grounds. Targeting another objection supplies a defence under the same applicability rules. |
| `target` | The category and name challenged by an objection | `claim`, `reasoning`, `assumption`; EAL/0.3 also `argument` and `objection`. Reasoning targets affect applications in the objection source environment. |
| `method` | The exact versioned identifier of an installed host contract | Selects the contract and computation; source cannot install or replace code. Legacy unversioned mode aliases are not accepted in this clause. |

The spelling `mode` is retained for compatibility in two disjoint declaration contexts: tool variability and the selected reasoning computation. The fields have distinct AST types and accepted values. `valid` in an API result means static well-formedness; it is never the truth of a claim. The stored `collected_at` field retains the original observation time; `ingested_at` records ingestion. These existing names are documented rather than given competing aliases.

## Why the new constructs are needed

Removing `proposition` would lose the distinction between prose and checked formal content. Removing `query` would permit a tool to answer a different mathematical problem while preserving superficial labels. Removing `binding` would make the association between a computational input and a typed conclusion implicit or ambiguous. Subject, quantity and scope identity remain distinct: identical dimensions do not make two physical quantities or model episodes interchangeable.

No new core keyword was added for an individual numerical algorithm or model provider. The typed input envelope is versioned separately as `EAL/typed-input/1`. EAL/0.3 extends the method set by host registration of typed, versioned contracts; it requires no grammar change for each new calculation. Source-defined executable plug-ins remain excluded.

`supported`, `contested`, `unsupported` and `out_of_scope` describe an argument assessment. They are not four truth values. EAL/0.3 also exposes the separate acceptance labels `accepted`, `rejected` and `undecided` for its explicitly constructed support/attack graph. Its construction and least-information equations are defined in the argument model. Rejection is a decision about acceptance under those relations, not the falsity of the claim. The independent grounded operation retains its ordinary argument-and-attack interface.
