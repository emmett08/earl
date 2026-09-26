# Coolant-loop composition and revision case

This **synthetic** bench problem asks whether the recorded conditions support
removing an 8 kW load from coolant-loop-A. Its sources are a supply-voltage
reading, two separately instrumented pump-flow readings, a heat-exchanger bench
result and a possible disagreement concerning pump A. The route from pump A
and the route from pump B both require the same supply result. The overall
statement requires an accepted flow route and the exchanger result.

The [EAL source](cooling.eal) uses structured/1 and its existing argument
graph: claim premises, alternative derivations and an objection against only
the pump A application. It does not claim to prove the physical heat-transfer
law or infer unrecorded conditions. A supported claim is limited to the
declared observations, their provenance fields, this loop, the assessment
instant and the author's stated interpretation of the bench measurements.
Threshold predicates identify usable observations; a below-threshold result
removes support for the stated positive claim without proving a negative
claim. The instrument readings are teaching data, not empirical measurements.

[Typed rules](baseline.py) supply an ordinary Python comparator: frozen
dataclass specifications, a provenance and freshness check, and a topologically
ordered AND/OR rule assessment with a local objection. It does not import the
EAL parser or solver. Its finite acyclic profile matches this task; it does
not implement EAL's general attack cycles, reusable patterns or method
registry. The source and typed configuration have different digests; both
receive the same value objects, original observation instant and context in
equivalent synthetic envelopes. Parsing/configuration preparation and
envelope construction are outside the measured reassessment interval for
both arms.

The [case fixture](cases.json) states expected statuses independently of either
implementation. Each revision names the nominal predecessor and the claims
whose expected *status* changes. Some changes defeat or remove an individual
route while leaving the final conclusion supported through pump B; inspect
the recorded argument statuses to see those changes. The cases include
withdrawal of one or both flow readings, withdrawal of the shared supply or
exchanger result, an objection with and without an alternative, flow-reading
expiry at 61 seconds, and a different coolant-loop identity. Reassessment
starts from the full revised observation set rather than reusing a cached
conclusion.

Run the local, credential-free control:

    PYTHONPATH=src python -m experiments.composition_revision.study --output /tmp/cooling-new-result

It writes source/configuration digests, fixture hash, claim/argument/evidence
statuses and elapsed evaluator time for both arms. The output directory must
be new. Nine reviewed development cases demonstrate this bounded behaviour;
they do not measure engineer authoring time, model ability, a held-out task
population or an EAL advantage over typed configuration.

For an authoring comparison, give different engineers the two starting
implementations and time the **same** subsequent requests: raise the bench
load to 10 kW with matching exchanger evidence, add a separately validated
third pump route, and change pump A's objection to apply only during a
specified calibration interval. Review semantic defects and the affected
claim paths after each change, as well as implementation and review time.
Freeze new tasks and expected outcomes before analysing them; do not treat
the nine development scenarios as fresh confirmation.
