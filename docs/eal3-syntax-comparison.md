# EAL/3 authoring and structural correspondence

Newlines terminate fields; braces group declarations without indentation rules. Typed arrows make grounds, warrant, conclusion and objection target visible. Context defaults eliminate repeated metadata while materialising the same typed fields before validation. Qualified lexical names and hygienic templates add composition without changing evidence identity. Pure expressions expose checked computation rather than quoted property-name boilerplate. Source grammar, binding, typing and inference remain distinct passes.

The [complete ANTLR grammar](../grammar/EAL.g4) is authoritative. [Composition](eal3-composition.md) specifies additional modules, imports, nested block arguments, typed lists, terminating recursion, quantities and conditional transfer. [The formal solver](aspic-method.md) specifies extension and preference policies.

These mock cases express the same original core records and reviewed rank relation. They concern synthetic test data; review metadata is supplied, not authenticated.

## Original semicolon notation

```antlr
language "EAL/2";
environment test_run {
  require "service" == "orders-api";
}
tool probe {
  version "1";
}
evidence primary {
  tool probe;
  kind test;
  environment test_run;
  max_age 60;
  input {"sensor":"primary"};
  require "passed" == true;
}
evidence gap {
  tool probe;
  kind test;
  environment test_run;
  max_age 60;
  input {"sensor":"gap"};
  require "detected" == true;
}
claim measured {
  statement "The synthetic primary check passes.";
  environment test_run;
}
claim ready {
  statement "The synthetic result is reportable under the reviewed relation.";
  environment test_run;
}
reasoning measured_rule {
  method "structured/1";
  rationale "The declared synthetic check is relevant to this bounded claim.";
}
pattern checked(c: claim, r: reasoning, e: evidence) {
  conclusion c;
  reasoning r;
  evidence e;
}
apply primary_route = checked(c=measured, r=measured_rule, e=primary);
argument report {
  conclusion ready;
  reasoning measured_rule;
  premises measured;
}
objection trace_gap {
  target argument primary_route;
  evidence gap;
}
rank primary_route 700 reviewed "synthetic-review/primary";
```

## EAL/3

```eal
language "EAL/3"
environment test_run {
  require service == "orders-api"
}
tool probe {
  version "1"
}
context environment test_run, tool probe, kind test, max_age 60 {
  evidence primary {
    input {"sensor":"primary"}
    require passed == true
  }
  evidence gap {
    input {"sensor":"gap"}
    require detected == true
  }
  claim measured {
    statement "The synthetic primary check passes."
  }
  claim ready {
    statement "The synthetic result is reportable under the reviewed relation."
  }
}
reasoning measured_rule {
  method "structured/1"
  rationale "The declared synthetic check is relevant to this bounded claim."
}
pattern checked(c: claim, r: reasoning, e: evidence) = [evidence e] via r => c
apply primary_route = checked(c=measured, r=measured_rule, e=primary)
argument report = [premises measured] via measured_rule => ready
objection trace_gap = [evidence gap] -x> argument primary_route
rank primary_route 700 reviewed "synthetic-review/primary"
```

| Source feature | Typed mapping retained |
|---|---|
| Context default | Materialised environment/tool/kind/age/input metadata on the applicable declaration |
| Bare key comparison | Original property path, comparator and typed JSON scalar |
| Typed flow | Conclusion, reasoning, evidence, assumptions, premise lists and optional evidence binding |
| Compact pattern/application | Typed parameters, exact named bindings, generated argument identity and source origin |
| Objection arrow | Explicit target kind/identity and evidence/premise lists |
| Proposition block | Subject, quantity, unit, scope, interval, query JSON and checked result criterion |
| Reviewed directives | Strictness, rank, directed contrary and review string preserved; new `prefer` adds explicit partial priorities |
| Nested blocks/compound templates | Qualified ordinary typed declarations after hygienic lowering, with original observation identities |

Existing comparator, metadata, JSON, typing and local evaluation capabilities remain represented. Additional expressions and composition rules extend the source language; they do not infer prose, create measurements or remove required metadata. Host budgets and finite formal semantics remain explicit boundaries.
