# Scoped composition in EAL/3

EAL/3 package 3.2.0 retains the typed evidence, assumption, reasoning, claim, argument, objection, proposition and reviewed-directive mappings. ANTLR recognition is followed by lexical binding, hygienic expansion, typed validation, local method evaluation and a separately selected argument calculus. [The syntax comparison](eal3-syntax-comparison.md) shows original-to-EAL/3 structural mappings. [EAL.g4](../grammar/EAL.g4) is the complete grammar; generated recognisers are committed and checked against ANTLR 4.13.2.

## Names, modules and source imports

`module release { ... }` qualifies local declarations as `release.name`. Nested modules and block arguments add further components. References use nearest lexical lookup or a qualified name; forward references are allowed. A context groups defaults without creating a namespace. Typed pattern bodies are closed: external declarations must be parameters even when an outer module contains a matching global name.

`import "library.eal" as library` adds source declarations under the alias. The parser requires an explicit trusted resolver; it never opens files itself. `ReasoningService` supplies a confined workspace `.eal` resolver. A submitted root source resolves imports from that workspace; imported files resolve their own imports relative to their file. Absolute paths, backslashes, root escape, import cycles and missing imports fail. Each dependency is read once per parse, so multiple aliases share one immutable source snapshot. The source digest covers root bytes and dependency digests. Imported origins retain `source_file` and line span. Imports never install Python methods or tool bindings.

## Defaults and multiple evidence

```eal
context environment lab, tool probe, kind test, max_age 60 {
  evidence first {
    input {"sensor": "left"}
    require valid and count(samples) >= 3
  }
  evidence second {
    input {"sensor": "right"}
    require valid and sum(samples) / count(samples) < 10
  }
}
```

Every evidence declaration is independent. Defaults cascade, explicit fields override them, and Boolean/numerical JSON identities remain distinct. Two declarations do not establish independent measurements. See [language](language.md) for the complete applicable-field list and required-field checks.

## Compound and recursive patterns

```eal
pattern each(c: claim, r: reasoning, es: evidence[]) decreases es {
  when es {
    argument item = [evidence head(es)] via r => c
    apply rest = each(c=c, r=r, es=tail(es))
  }
}
apply checks = each(c=passed, r=measured, es=[first, second])
```

This creates `checks.item` and `checks.rest.item`, with original evidence identities. Each route supports `passed` independently. In contrast, a compact `[evidence es]` flow requires every evidence item conjunctively. An empty expanded support list fails the ordinary argument checks.

Compound patterns may contain claims, environments, tools, reasoning, assumptions, arguments, objections, nested definitions and applications. Application-local declarations are hygienically qualified, including nested calls. Scalar parameter kinds are `claim`, `reasoning`, `evidence`, `assumption`, `environment` and `tool`; `[]` makes a list of that kind. Named bindings are exact; passing a wrong kind, undeclared name, duplicate binding or list into a scalar fails. No string substitution or arbitrary capture is used.

Recursive calls in a cycle must pass `tail` of the caller's declared decreasing list to the callee's measure under a `when` nonempty guard. `head` and `tail` are typed structural selectors, not expression functions. Unused template metadata and termination conditions are checked. Source recursion that cannot prove strict decrease is rejected. Runtime depth/application/reference budgets independently bound expansion, and exhaustion exposes no partial successful expansion.

A compact application's identity is its generated argument identity. A compound application names a namespace; objections to one route explicitly target its qualified argument, for example `checks.item`. Premise support remains through claims, preserving alternative derivations. Ordinary premise cycles are rejected; attack cycles are valid and may remain undecided.

## Pure expressions and typed results

Expressions are a closed pure language with finite JSON operands, strict Boolean/numerical types, explicit unknown fields, scalar arithmetic and rationally scaled dimensional quantities. Functions cannot access files, time, network or host methods. Known dimension incompatibilities fail statically; dynamic type and finite-value checks apply at runtime. Property paths are not EAL declaration references.

A typed proposition may inherit explicit subject, quantity, unit, scope, interval and query defaults. Its result expression must use declared method outputs with compatible types and output meanings. Basis outputs are converted to the proposition unit before expression evaluation. Neither inherited metadata nor a satisfied expression proves correspondence between prose and the physical observation.

## Conditional transfer between environments

A `structured/1` reasoning declaration can carry:

```eal
transfer from simulation to bench assuming correspondence reviewed "review/transport-1"
```

Its argument has exactly one typed source premise and explicitly depends on the named target-environment assumption, whose validation evidence must be usable. The target claim is typed and in the target environment. Subject, quantity, unit, query and result must be identical under typed JSON identity; the target interval is contained in the source interval. Scope may differ only through this explicit relation. This is a checked conditional transport step, not an implicit environment conversion or proof of physical transport adequacy. Results record `correspondence_checked: true`, `transport_justification_verified: false` and `prose_verified: false`.

Distinct runtime contexts are supplied as `{"$environments": {"simulation": {...}, "bench": {...}}}`. Each environment and evidence request sees its selected object, including observation identity and reuse fingerprints. A missing selected environment supplies an empty context rather than borrowing another scope. Flat single-environment context remains supported.

## Remaining boundaries

Host budgets can be configured through Python `ExecutionLimits` or CLI/MCP/JSON launcher `--limits FILE`; the source cannot grant itself resources. Compiled snapshots bind budgets and exporter replay checks them. Construction/search exhaustion, worker timeout or memory exhaustion is incomplete and cannot establish acceptance. Collector output, transport and process deadlines remain separately bounded.

The optional `argumentation/aspic/2` profile supplies grounded/preferred/stable extensions, credulous/sceptical queries, minimum-rank and last-link numerical/partial preferences, and finite premise-founded cyclic construction. It does not enumerate infinitely repeated cyclic arguments, infer omitted contraries, prove first-order prose or authenticate physical observations. These are explicit semantic and operational boundaries. [The solver specification](aspic-method.md) defines them.

A complete runnable example is [scoped review](../examples/scoped-review/README.md). Tests exercise round-trip identity, local references, recursion termination, JSON type distinctions, dimensional mismatches, scope transfer and hand-calculated formal extensions. They establish implemented behaviour, not human authoring or model-performance gains.
