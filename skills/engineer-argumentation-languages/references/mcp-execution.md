# MCP execution and text-model hosts

Use an official SDK and a published protocol version. Implement structured inputs and results. Prefer compact operation results with stable IDs and a separate explanation operation when full traces are large. Keep stdout reserved for protocol messages during stdio serving.

Useful operations include language validation, observation collection, argument evaluation, explanation and an explicitly named formal solver. Make IO visible in the operation contract. Store successful and failed executions so a collection failure cannot silently become evidence. Allow real deterministic tools, probabilistic analyses and model-provider clients through configured adapters. Record model identity, sampling settings and seed where available without asserting seeds guarantee reproducibility.

Bind each result to the declared request, tool version, represented environment and source. A content digest identifies bytes and detects mismatches; it does not authenticate a source or establish a proposition. For imported observations retain their measurement timestamp. Use a configured workspace and tool registry, structured argv, bounded output, timeout and strict JSON decoding. Argument source should describe reasoning and inputs; host configuration chooses executable adapters.

A text-only model emits a single operation request matching the actual host schema. For current EAL/0.1, use the flat shape `{"operation":"reason","source":"...","context":{},"collection_id":"..."}`. A different language may use a nested envelope, but its host and examples must agree. A host validates that object against the operation schema, calls MCP using a client, then provides the result as data in the next model turn. Reject multiple requests, unknown fields, markdown wrappers and invented operation names when the contract requires a single JSON object. Do not evaluate model text as code or let it redefine host executables.

Test a real subprocess server with initialise, tool discovery and invocation, plus client host parsing. Include unknown operation, malformed source, tool failure and malformed structured arguments. Declare whether an external service was actually exercised or only the adapter boundary was tested. Avoid asserting general reasoning capability: the server implements named algorithms and evidence operations.

## Autonomous interaction and economical execution

Specify the model application separately from the MCP transport. Provide operation/schema discovery, prompt or request templates, persistent argument/observation identifiers, bounded error feedback, revision handling, result retrieval and termination. A syntactically valid request can still encode the wrong engineering question; compare the checked proposition, scope and premises with the intended task. Keep those formal identities in results.

Distinguish models that can call tools natively from models that can only emit text. Both can request external reasoning through a host. A model described as non-reasoning can propose representations while the interpreter executes the specified reasoning algorithm. MCP supplies the interaction protocol; the server needs actual solvers and method implementations, and the application needs the interaction loop.

Make detailed derivations retrievable separately from short status/results. Reuse stored source, observations and method results where their identities and applicability permit it. Measure token and execution costs, including failed requests and repair attempts, before claiming savings. Do not allow compression or caching to discard assumptions, stale evidence, contradictions or method qualifiers. Keep deterministic execution caches separate from stochastic resampling requirements.

Test with actual named models on held-out tasks before claiming that low-cost models achieve the target capability. Test also a scripted client for reproducible protocol regression. These are different checks: a correct scripted request proves an interface works; model trials measure the model–host–server system’s ability to complete engineering tasks.
