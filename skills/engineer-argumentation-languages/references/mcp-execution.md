# MCP execution and text-model hosts

Use an official SDK and a published protocol version. Implement structured inputs and results. Prefer compact operation results with stable IDs and a separate explanation operation when full traces are large. Keep stdout reserved for protocol messages during stdio serving.

Useful operations include language validation, observation collection, argument evaluation, explanation and an explicitly named formal solver. Make IO visible in the operation contract. Store successful and failed executions so a collection failure cannot silently become evidence. Allow real deterministic tools, probabilistic analyses and model-provider clients through configured adapters. Record model identity, sampling settings and seed where available without asserting seeds guarantee reproducibility.

Bind each result to the declared request, tool version, represented environment and source. A content digest identifies bytes and detects mismatches; it does not authenticate a source or establish a proposition. For imported observations retain their measurement timestamp. Use a configured workspace and tool registry, structured argv, bounded output, timeout and strict JSON decoding. Argument source should describe reasoning and inputs; host configuration chooses executable adapters.

A text-only model may emit a request such as `{"operation":"reason","arguments":{...}}`. A host validates that object against the operation schema, calls MCP using a client, then provides the result as data in the next model turn. Reject multiple requests, unknown fields, markdown wrappers and invented operation names when the contract requires a single JSON object. Do not evaluate model text as code or let it redefine host executables.

Test a real subprocess server with initialise, tool discovery and invocation, plus client host parsing. Include unknown operation, malformed source, tool failure and malformed structured arguments. Declare whether an external service was actually exercised or only the adapter boundary was tested. Avoid asserting general reasoning capability: the server implements named algorithms and evidence operations.
