#!/usr/bin/env python3
"""Build deterministic synthetic roots for the developmental mechanism schedule.

Brief and reference rules are authored here. The EAL and parse-derived JSON
views are generated from the same source. None of these records is a real
engineering observation, signed acquisition, or human-adjudicated reference.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from eal.extensions import root_mean_square
from eal.formatter import semantic_ir
from eal.modes import _inductive, _causal, _counterfactual, _abductive, _analogical
from eal.parser import parse
from eal.sampled_negative import sampled_negative


HERE = Path(__file__).resolve().parent
NOW = "2026-09-24T12:10:00Z"
AT = "2026-09-24T12:05:00Z"
START = "2026-09-24T12:00:00Z"
END = "2026-09-24T12:09:00Z"

GENEALOGY = {
    "rollout_admission": ("Prior release_provenance example", "Admission generation and pinned image in a Kubernetes namespace; tool-version forgery"),
    "relay_trip_window": ("Prior thermal_soak freshness example", "Protective relay trip pulse and time criterion; expired commissioning trace"),
    "chilled_valve_stroke": ("Prior thermal_soak freshness example", "Valve travel and seating switch; changed plant context"),
    "edge_config_quorum": ("Prior release_provenance conjunction example", "Two edge-zone acknowledgements for one config revision; second-reader version swap"),
    "archive_restore_identity": ("Prior release_provenance identity example", "Separate approved-digest and restore reports for one object plus duration; changed restore object identity"),
    "air_handler_flow": ("Prior numerical threshold record example", "Air handler operating point and intake flow; point changes while measurement is constant"),
    "bearing_vibration_rms": ("Prior vibration-rms example", "Different four-sample motor sign pattern, threshold and run binding; same RMS contract"),
    "sump_pump_trial": ("Prior pressure-trial example", "Randomised flow contrast in m3/s; imported reader version changes"),
    "queue_ack_lower_bound": ("Prior mixed-reasoning inductive example", "Queue acknowledgement Wilson interval at 400 trials; subject mismatch"),
    "dryer_intervention": ("Prior vent_model example", "Dryer heater to outlet-temperature two-node affine model; stale model record"),
    "inverter_fault_posterior": ("Prior mixed-reasoning abductive example", "Finite phase-alert hypothesis posterior; method version mismatch"),
    "fixture_feature_match": ("Prior mixed-reasoning analogical example", "Exact four-feature fixture fraction; candidate context mismatch"),
    "fuel_particle_nondetection": ("Prior sampled-negative example", "Calibration-qualified strict upper-bound non-detection; trace scope mismatch"),
    "chiller_flow_counterexample": ("Prior sampled-counterexample example", "Incomplete interval with observed chiller-flow breach in L/s; reader version mismatch"),
    "storage_error_nondetection": ("Prior sampled-negative example", "Inclusive block-error threshold and complete two-second spacing; expired imported trace"),
    "crane_speed_counterexample": ("Prior sampled-counterexample example", "Strict speed boundary equality in m/s as witness despite partial coverage; subject mismatch"),
    "reactor_alarm_nondetection": ("Prior sampled-negative example", "Fifteen-second concentration detector capacity and complete coverage; episode context mismatch"),
    "robot_axis_displacement_counterexample": ("Prior sampled-counterexample example", "Axis-displacement breach in mm with narrowed input validity interval"),
    "packet_loss_generator": ("Prior network_failover example", "Separate generator diagnosis as claim premise for defence; wrong diagnosis origin"),
    "laser_calibration_defence": ("Prior defended-instrument example", "Optics audit repairs a cut-width challenge; stale audit observation"),
    "database_lease_defence": ("Prior network_failover example", "Lease-renewal test challenged at reasoning level; independent injector diagnosis and wrong reader version"),
    "conveyor_jam_challenge": ("Prior defended-instrument example", "Jam alarm targets claim directly; no authored defence despite extraneous diagnosis record"),
    "water_loop_pressure_challenge": ("Prior network_failover example", "Pressure-collapse objection targets reasoning; wrong-plant attack record withdrawn"),
    "firmware_watchdog_challenge": ("Prior defended-instrument example", "Watchdog objection to boot-duration argument; expired attack record withdrawn"),
}


def j(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(j(value).encode('utf-8')).hexdigest()


def envelope(value, context, tool, at=AT):
    return {"value": value, "observed_at": at, "context": context,
            "request": {"context": context, "input": {}, "mode": "deterministic",
                        "tool": tool, "tool_version": "1"}}


def base(root_id, family, brief, context, claim, source, records, invalid_evidence,
         invalid_field, invalid_value, valid_status, invalid_status, rationale,
         method_result, *, method_factory=None, reference_rule=None):
    invalid = deepcopy(records)
    if invalid_field == "observed_at":
        invalid[invalid_evidence]["observed_at"] = invalid_value
    elif invalid_field == "request.tool_version":
        invalid[invalid_evidence]["request"]["tool_version"] = invalid_value
    elif invalid_field == "context":
        invalid[invalid_evidence]["context"] = invalid_value
    elif invalid_field.startswith("value."):
        invalid[invalid_evidence]["value"][invalid_field.split(".", 1)[1]] = invalid_value
    else:
        raise ValueError(invalid_field)
    source_digest=hashlib.sha256(source.encode('utf-8')).hexdigest()
    names=', '.join(f'{name}={value["request"]["tool"]}/1 at {value["observed_at"]} value-sha256:{digest(value["value"])[:16]}'
                    for name,value in records.items())
    return {
        "id": root_id, "family": family, "brief": brief, "source": f"{root_id}.eal",
        "semantic_view": f"{root_id}.semantic.json", "context": context,
        "now": NOW, "claim": claim, "valid_records": records,
        "invalid_records": invalid, "valid_status": valid_status,
        "invalid_status": invalid_status,
        "absent_status": "unsupported",
        "wrong_proposal": "out_of_scope",
        "eligibility_memo": (f"Source sha256:{source_digest}; current task {j(context)} at {NOW}. "
                             f"Imported records {names} match their declared tool versions, empty acquisition inputs, task context and 1800-second age bounds; "
                             f"their source-level evidence predicates and applicable typed metadata are admissible. "
                             f"This memo does not state whether the claim is supported or whether physical acquisition is authentic."),
        "method_result": method_result,
        "full_status": {"status": valid_status,
                        "decisive_basis": f"The selected {claim} status follows from the admitted {', '.join(records)} records and the authored argument for this synthetic task; method output alone does not authenticate the measurements.",
                        "claim":claim,"source_sha256":source_digest,"context":context,"assessed_at":NOW,
                        "records_sha256":digest(records)},
        "invalid_verdict": {"status": valid_status, "claim":claim,
                            "source_sha256":"0"*64,"context":context,
                            "assessed_at":"2026-09-24T10:00:00Z", "records_sha256":digest(records)},
        "reference_rule": reference_rule or {
            "changed_record": invalid_evidence, "changed_field": invalid_field,
            "required_value": records[invalid_evidence]["observed_at"]
                if invalid_field == "observed_at" else None,
            "valid": valid_status, "invalid": invalid_status,
        },
        "method_factory": method_factory,
        "_source": source,
    }


def eligibility_roots():
    # Distinct physical/software questions and predicates; no inherited old
    # source or merely renamed old task is counted as a fresh root.
    specs = [
        ("rollout_admission", "Does the Orion API admission log identify the pinned image digest in the payments namespace at generation 34?",
         {"cluster": "arc-1", "namespace": "payments"}, "The admission log records the pinned Orion image at generation 34.",
         [("admission", "admission_reader", "provenance", {"workload": "orion-api", "image": "sha256:d742", "generation": 34, "admission_verified": True},
           [('workload','==','orion-api'), ('image','==','sha256:d742'), ('generation','==',34), ('admission_verified','==',True)])],
         "admission", "request.tool_version", "0", "The imported record must originate from the declared reader version"),
        ("relay_trip_window", "Did relay R17's current commissioning trace record a trip below 45 ms for a test pulse of at least 610 A?",
         {"substation": "N10", "relay": "R17"}, "The R17 record reports a qualifying commissioned trip.",
         [("trip", "relay_reader", "test", {"pulse_a": 645, "trip_ms": 39, "commissioning": "C7"},
           [('pulse_a','>=',610), ('trip_ms','<',45), ('commissioning','==','C7')])],
         "trip", "observed_at", "2026-09-24T10:30:00Z", "A historic relay pulse cannot establish the current commissioning record"),
        ("chilled_valve_stroke", "Does the synthetic stroke report show chilled valve V6 reached at least 39 mm and seated on its sixth cycle?",
         {"plant": "cold-loop-3", "device": "V6"}, "The V6 cycle six stroke report meets its travel and seating criteria.",
         [("stroke", "stroke_reader", "test", {"cycle": 6, "travel_mm": 41, "seat_switch": True},
           [('cycle','==',6), ('travel_mm','>=',39), ('seat_switch','==',True)])],
         "stroke", "context", {"plant": "cold-loop-2", "device": "V6"}, "A report from a different plant is ineligible"),
        ("edge_config_quorum", "Do two independent edge acknowledgements identify config revision E19 in both zones before claiming a completed propagation?",
         {"service": "edge-map", "rollout": "E19"}, "Both named edge zones report revision E19 for this rollout.",
         [("north_ack", "north_reader", "ack", {"zone": "north", "revision": "E19", "ack": True},
           [('zone','==','north'), ('revision','==','E19'), ('ack','==',True)]),
          ("south_ack", "south_reader", "ack", {"zone": "south", "revision": "E19", "ack": True},
           [('zone','==','south'), ('revision','==','E19'), ('ack','==',True)])],
         "south_ack", "request.tool_version", "7", "The second zone's result must be tied to its installed reader"),
        ("archive_restore_identity", "Did a restore drill for object A72 match the expected digest and complete in less than 300 seconds?",
         {"vault": "vault-C", "exercise": "D4"}, "The separately acquired A72 approved-digest record and D4 restore report identify the same pinned digest, and the restore report states a content match within 300 seconds.",
         [("restore", "restore_reader", "restore", {"object": "A72", "digest": "sha256:12af", "elapsed_s": 274, "match": True},
           [('object','==','A72'), ('digest','==','sha256:12af'), ('elapsed_s','<',300), ('match','==',True)]),
          ("approved", "approval_reader", "provenance", {"object":"A72", "digest":"sha256:12af", "approval_valid":True},
           [('object','==','A72'),('digest','==','sha256:12af'),('approval_valid','==',True)])],
         "restore", "value.object", "A73", "A72 and A73 are different restoration subjects"),
        ("air_handler_flow", "Does the P9 sensor's AHU-8 intake balance report show at least 125 litres per second on operating point B2?",
         {"building": "annex-4", "ahu": "AHU-8"}, "The B2 AHU-8 report gives an intake of at least 125 litres per second.",
         [("balance", "flow_reader", "measurement", {"point": "B2", "flow_l_s": 132, "sensor": "P9"},
           [('point','==','B2'), ('flow_l_s','>=',125), ('sensor','==','P9')])],
         "balance", "value.point", "B1", "The measured number belongs to a different balancing point"),
    ]
    roots = []
    for root_id, brief, context, statement, entries, changed, changed_field, changed_value, rationale in specs:
        lines = ["language \"EAL/2\";", "environment task_scope {" ]
        lines += [f"  require {j(k)} == {j(v)};" for k,v in context.items()]
        lines += ["}"]
        records = {}
        names = []
        for evidence, tool, kind, value, predicates in entries:
            names.append(evidence)
            lines += [f"tool {tool} {{ version \"1\"; mode deterministic; }}",
                      f"evidence {evidence} {{", f"  tool {tool}; kind {kind}; environment task_scope; max_age 1800;"]
            lines += [f"  require {j(k)} {op} {j(v)};" for k,op,v in predicates]
            lines += ["}"]
            records[evidence] = envelope(value, context, tool)
        lines += ["reasoning registered_record { method \"structured/1\"; rationale \"These imported records report only the stated bounded test, identity and operating point; the acquisition assertion requires independent authentication.\"; }",
                  f"claim accepted_record {{ statement {j(statement)}; environment task_scope; }}",
                  f"argument source_report {{ conclusion accepted_record; reasoning registered_record; evidence {', '.join(names)}; }}"]
        roots.append(base(root_id, "eligibility", brief, context, "accepted_record", "\n".join(lines)+"\n",
                          records, changed, changed_field, changed_value, "supported", "unsupported", rationale,
                          {"authored": True, "mechanically_proved": False},
                          reference_rule={"conditions": {entry[0]: [list(p) for p in entry[4]] for entry in entries},
                                          "changed_field":changed_field,"valid":"supported","invalid":"unsupported"}))
    return roots


def exact_method_output(method, payload):
    """Supply the actual installed computation output, without a claim status.

    The separate brief-rule checker independently calculates the decisive
    scalar and does not use these implementation functions.
    """
    implementations={
        'engineering/rms/1':root_mean_square,
        'causal/1':_causal, 'inductive/1':_inductive,
        'counterfactual/1':_counterfactual, 'abductive/1':_abductive,
        'analogical/1':_analogical,
    }
    computed=implementations[method](payload)
    return computed['details'] if 'details' in computed else computed


def typed_roots():
    # Six different computations, each restricted to the output of an exact
    # registered method and its typed proposition. One numeric result alone
    # cannot establish physical causality, calibration or representativeness.
    specs = [
      dict(id="bearing_vibration_rms", brief="For motor M73's identified four-sample run, was RMS vibration velocity about zero at most 0.43 m/s?", ctx={"site":"drive-5", "motor":"M73"}, subject="M73", quantity="velocity", unit="m/s", scope="run-M73-4", method="engineering/rms/1", kind="measurement_series", query={"origin":0}, payload={"origin":0,"samples":[0.2,-0.3,0.4,-0.5]}, result=("rms","<=",0.43), calc={"rms":0.3674234614174767,"sample_size":4}, change=("value.scope","run-M73-3"), factory="eal.extensions:example_registry"),
      dict(id="sump_pump_trial", brief="In the declared randomised sump pump trial, did treated flow exceed control flow by at least 0.004 m3/s?", ctx={"plant":"sump-2", "trial":"P9"}, subject="pump-S2", quantity="volumetric_flow", unit="m3/s", scope="trial-P9", method="causal/1", kind="experiment", query={"assignment":"randomised"}, payload={"assignment":"randomised","treatment":[0.032,0.034,0.033],"control":[0.027,0.028,0.026]}, result=("estimate",">=",0.004), calc={"estimate":0.006}, change=("request.tool_version","0")),
      dict(id="queue_ack_lower_bound", brief="Under the stated binomial sampling model, does the 95% Wilson lower bound for successful queue acknowledgements in 400 trials exceed 0.96?", ctx={"service":"task-queue", "cohort":"Q7"}, subject="queue-Q7", quantity="probability", unit="1", scope="ack-Q7-400", method="inductive/1", kind="sample", query={"confidence":0.95}, payload={"successes":397,"trials":400,"confidence":0.95}, result=("lower",">",0.96), calc={"estimate":0.9925,"lower":0.9779}, change=("value.subject","queue-Q6")),
      dict(id="dryer_intervention", brief="Within the supplied affine dryer model and its fixed exogenous terms, does setting heater_power to 4 predict outlet_delta at most 9 K?", ctx={"machine":"dryer-11", "model":"D2"}, subject="dryer-11", quantity="temperature_difference", unit="K", scope="model-D2", method="counterfactual/1", kind="causal_model", query={"variables":{"heater_power":{"intercept":2,"coefficients":{},"noise":0},"outlet_delta":{"intercept":1,"coefficients":{"heater_power":2},"noise":0}},"intervention":{"variable":"heater_power","value":4},"outcome":"outlet_delta"}, payload=None, result=("counterfactual","<=",9), calc={"factual":5,"counterfactual":9,"difference":4}, change=("observed_at","2026-09-24T10:00:00Z")),
      dict(id="inverter_fault_posterior", brief="For the stipulated finite fault model given the phase-alert pattern, is the leading fault hypothesis posterior at least 0.70?", ctx={"line":"converter-4", "episode":"F8"}, subject="converter-4", quantity="probability", unit="1", scope="fault-model-F8", method="abductive/1", kind="hypotheses", query={"observed":"phase_alert","candidates":[{"name":"sensor","prior":0.6,"likelihood":0.8},{"name":"winding","prior":0.4,"likelihood":0.2}]}, payload=None, result=("best_posterior",">=",0.70), calc={"best_posterior":0.8571428571428571,"best":"sensor"}, change=("value.method","abductive/2")),
      dict(id="fixture_feature_match", brief="For the four predeclared fixture features, does candidate C21 match at least three quarters of the reference values exactly?", ctx={"bench":"assembly-7", "candidate":"C21"}, subject="C21", quantity="dimensionless", unit="1", scope="feature-check-C21", method="analogical/1", kind="analogy", query={"relevant_features":["mount","drive","diameter","firmware"],"source":{"mount":"M6","drive":"dual","diameter":12,"firmware":"A"},"target":{"mount":"M6","drive":"dual","diameter":12,"firmware":"B"}}, payload=None, result=("match_fraction",">=",0.75), calc={"match_fraction":0.75,"matched":3,"feature_count":4}, change=("context",{"bench":"assembly-7","candidate":"C20"})),
    ]
    roots=[]
    for s in specs:
        source = ["language \"EAL/2\";", "environment task_scope {"]
        source += [f"  require {j(k)} == {j(v)};" for k,v in s['ctx'].items()]
        source += ["}", "tool numerical_reader { version \"1\"; mode deterministic; }",
                   f"evidence numerical_input {{ tool numerical_reader; kind {s['kind']}; environment task_scope; max_age 1800; require \"schema\" == \"EAL/typed-input/1\"; }}",
                   f"reasoning numerical_step {{ method {j(s['method'])}; rationale \"Evaluate the named finite method on this exact query and attached record; the computation does not verify physical interpretation or source authenticity.\"; }}"]
        path, op, expected = s['result']
        source += ["claim computed_record {", f"  statement {j(s['brief'])};", "  environment task_scope;",
                   "  proposition {", f"    subject {j(s['subject'])};", f"    quantity {j(s['quantity'])};",
                   f"    unit {j(s['unit'])};", f"    scope {j(s['scope'])};",
                   f"    valid_from {j(START)};", f"    valid_until {j(END)};",
                   f"    query {j(s['query'])};", f"    result {j(path)} {op} {j(expected)};",
                   "  }", "}",
                   "argument measured_route { conclusion computed_record; reasoning numerical_step; evidence numerical_input; binding numerical_input; }"]
        value = {"schema":"EAL/typed-input/1", "method":s['method'], "subject":s['subject'],
                 "quantity":s['quantity'], "unit":s['unit'], "scope":s['scope'],
                 "valid_from":START, "valid_until":END,
                 "payload":s['payload'] if s['payload'] is not None else s['query']}
        if s['method'] in ("inductive/1", "causal/1", "engineering/rms/1"):
            assert all(value['payload'].get(k)==v for k,v in s['query'].items())
        records={"numerical_input":envelope(value,s['ctx'],"numerical_reader")}
        field, invalid = s['change']
        roots.append(base(s['id'],"typed_numerical",s['brief'],s['ctx'],"computed_record",
                          "\n".join(source)+"\n", records,"numerical_input",field,invalid,
                          "supported","unsupported", f"exact method/proposition input correspondence must hold for {s['method']}",
                          {"method":s['method'],"query":s['query'],"subject":s['subject'],"scope":s['scope'],
                           "output":exact_method_output(s['method'],value['payload']),
                           "qualification":"Calculation from supplied typed values; acquisition and engineering assumptions unverified"},
                          method_factory=s.get('factory'), reference_rule={"method":s['method'],"required_scope":s['scope'],
                            "required_subject":s['subject'],"query":s['query'],"result_path":path,"operator":op,
                            "threshold":expected,"expected_value":s['calc'].get(path),"changed_field":field,
                            "valid":"supported","invalid":"unsupported"}))
    return roots


def sampled_roots():
    specs=[
      ("fuel_particle_nondetection","In the finite fuel-filter sample sequence, can the calibrated 0.35 limit detector support non-detection of normalised particle scores at or above 0.4?",{"rig":"filter-F2","batch":"F8"}, "filter-F2", "particle-samples-F8", "dimensionless","1", "non_detection",0.4,"lt",(0,3,6,9),(0.18,0.20,0.23,0.21),3,0.35,0.90,"value.scope","particle-samples-F7"),
      ("chiller_flow_counterexample","Does the logged sampled chiller branch trace contain a flow excursion above 7 L/s, despite incomplete coverage of the full run?",{"chiller":"C17","run":"U4"},"C17","flow-U4","volumetric_flow","L/s","counterexample",7,"le",(1,4,7),(6.2,7.3,6.5),3,6.5,0.85,"request.tool_version","0"),
      ("storage_error_nondetection","During the complete sampled block-check window, did a calibrated detector record no dimensionless error score above 0.5?",{"array":"B19","scan":"S3"},"B19","block-check-S3","dimensionless","1","non_detection",0.5,"le",(0,2,4,6),(0.1,0.2,0.1,0.3),2,0.45,0.93,"observed_at","2026-09-24T09:20:00Z"),
      ("crane_speed_counterexample","Does any observed crane-travel sample reach or exceed the strict 1.2 m/s speed limit?",{"crane":"G5","lift":"L8"},"G5","travel-L8","velocity","m/s","counterexample",1.2,"lt",(0,5,10),(0.8,1.2,0.9),5,1.0,0.8,"value.subject","G6"),
      ("reactor_alarm_nondetection","With sampled five-second coverage and the stipulated detector contract, is there no recorded normalised concentration score at or above 0.6?",{"vessel":"M4","episode":"A6"},"M4","alarm-A6","dimensionless","1","non_detection",0.6,"lt",(0,5,10,15),(0.1,0.2,0.4,0.2),5,0.55,0.91,"context",{"vessel":"M4","episode":"A5"}),
      ("robot_axis_displacement_counterexample","Did at least one finite robot-axis displacement sample exceed the declared 11 mm ceiling?",{"robot":"arm-12","move":"K9"},"arm-12","axis-displacement-K9","length","mm","counterexample",11,"le",(0,2,4,6),(8,9,12,7),2,10,0.8,"value.valid_until","2026-09-24T12:07:00Z"),
    ]
    roots=[]
    for rid,brief,ctx,subject,scope,quantity,unit,mode,bound,op,times,values,gap,limit,sensitivity,field,invalid in specs:
        query={"mode":mode,"start":times[0] if mode=="non_detection" else 0,
               "end":times[-1] if mode=="non_detection" else times[-1]+1,
               "max_gap":gap,"property":{"operator":op,"value":bound},"semantics":"sampled",
               "detector_contract":{"maximum_detection_limit":limit,"minimum_sensitivity":sensitivity}}
        payload={**query,"events":[{"time":t,"value":v} for t,v in zip(times,values)],
                 "calibration":{"detection_limit":limit-0.02,"sensitivity_lower_bound":sensitivity+0.02}}
        source=["language \"EAL/2\";","environment task_scope {"]
        source += [f"  require {j(k)} == {j(v)};" for k,v in ctx.items()]
        source += ["}","tool trace_reader { version \"1\"; mode deterministic; }",
                   "evidence trace_input { tool trace_reader; kind sampled_negative_trace; environment task_scope; max_age 1800; require \"schema\" == \"EAL/typed-input/1\"; }",
                   "reasoning sampled_step { method \"engineering/sampled-negative/1\"; rationale \"A finite sampled negative finding is conditioned on sample coverage and detector capability; no continuous-time or physical truth follows from this imported trace.\"; }",
                   "claim sampled_finding {",f"  statement {j(brief)};","  environment task_scope;",
                   "  proposition {",f"    subject {j(subject)};",f"    quantity {j(quantity)};",f"    unit {j(unit)};",
                   f"    scope {j(scope)};",f"    valid_from {j(START)};",f"    valid_until {j(END)};",
                   f"    query {j(query)};", "    result \"finding\" == true;", "  }", "}",
                   "argument sampled_route { conclusion sampled_finding; reasoning sampled_step; evidence trace_input; binding trace_input; }"]
        value={"schema":"EAL/typed-input/1","method":"engineering/sampled-negative/1",
               "subject":subject,"quantity":quantity,"unit":unit,"scope":scope,
               "valid_from":START,"valid_until":END,"payload":payload}
        records={"trace_input":envelope(value,ctx,"trace_reader")}
        roots.append(base(rid,"sampled_negative",brief,ctx,"sampled_finding","\n".join(source)+"\n",records,
                          "trace_input",field,invalid,"supported","unsupported",
                                          "the complete typed sampled query must bind to this subject, quantity, unit, interval and acquisition",
                          {"method":"engineering/sampled-negative/1","query":query,"subject":subject,"scope":scope,
                           "output":sampled_negative(payload),
                           "qualification":"Finite sampled finding; record acquisition and physical detector capability remain assertions"},
                          method_factory="eal.sampled_negative:sampled_negative_registry",
                          reference_rule={"mode":mode,"property":query['property'],"coverage":mode=="non_detection",
                            "subject":subject,"scope":scope,"changed_field":field,"valid":"supported","invalid":"unsupported"}))
    return roots


def objection_roots():
    specs=[
      ("packet_loss_generator", "For switch SX-4's failover test, is the measured transfer claim still usable after a packet-loss alert and a separate generator-origin diagnosis?", {"rack":"R8","switch":"SX-4"}, "The SX-4 transfer was no greater than 220 ms in the declared run.", "transfer_ms",208,220,"alert","packet_loss","diagnosis","generator_injection",True,"diagnosis","value.origin","unresolved"),
      ("laser_calibration_defence", "Can station LT-8's cut-width pass record survive an independent overwidth report when a separate optics audit identifies that report's calibration fault?", {"line":"laser-2","station":"LT-8"}, "The LT-8 recorded cut-width test passed the pinned drawing.", "width_mm",0.95,1.0,"overwidth","overwidth_seen","audit","optics_probe_fault",True,"audit","observed_at","2026-09-24T10:00:00Z"),
      ("database_lease_defence", "Does a lease-renewal timing result remain supported when a timeout alert is attributed by a separate trace to a synthetic test injector?", {"cluster":"db-east","shard":"S12"}, "The S12 lease-renewal test completed within 150 ms.", "renewal_ms",138,150,"timeout","timeout_alert","trace","injector_origin",True,"trace","request.tool_version","0"),
      ("conveyor_jam_challenge", "Does conveyor C7's throughput test remain unchallenged after a current jam alarm for that belt? Treat an alarm identifying another belt as inapplicable.", {"facility":"sort-3","conveyor":"C7"}, "The C7 throughput test reports at least 90 parcels per minute without a qualifying objection.", "parcels_per_min",94,90,"jam","jam_observed","diagnosis","drive_coupling_fault",False,"jam","value.event","wrong_belt"),
      ("water_loop_pressure_challenge", "Can a bounded booster pressure test support the loop claim while a qualifying downstream pressure-collapse observation remains unanswered?", {"plant":"water-6","loop":"L3"}, "The L3 pump test supplies an unchallenged pressure observation of at least 320 kPa.", "pressure_kpa",325,320,"collapse","pressure_drop","diagnosis","sensor_fault",False,"collapse","context",{"plant":"water-5","loop":"L3"}),
      ("firmware_watchdog_challenge", "Does the boot completion log settle the F10 firmware start claim when a separate watchdog-reset record applies to that same boot?", {"device":"servo-13","boot":"F10"}, "The F10 boot finished within 6 seconds without a qualifying watchdog challenge.", "boot_s",5.1,6,"watchdog","reset_seen","diagnosis","test_fixture_reset",False,"watchdog","observed_at","2026-09-24T10:00:00Z"),
    ]
    roots=[]
    for rid,brief,ctx,statement,measure,value,limit,alert_id,alert_flag,diag_id,diag_flag,defended,changed,field,invalid in specs:
        target_kind={'database_lease_defence':'reasoning', 'conveyor_jam_challenge':'claim',
                     'water_loop_pressure_challenge':'reasoning'}.get(rid,'argument')
        target_name={'reasoning':'test_step','claim':'operational_record','argument':'primary_test'}[target_kind]
        cmp='>=' if measure in ('parcels_per_min','pressure_kpa') else '<='
        values={"test":{"episode":next(iter(ctx.values())),measure:value,"passed":True},
                alert_id:{"event":alert_flag,"severity":"high","active":True},
                diag_id:{"origin":diag_flag,"independently_checked":bool(defended)}}
        tools={"test":"test_reader",alert_id:"alert_reader",diag_id:"diagnosis_reader"}
        records={e:envelope(v,ctx,tools[e]) for e,v in values.items()}
        source=["language \"EAL/2\";","environment task_scope {"]
        source += [f"  require {j(k)} == {j(v)};" for k,v in ctx.items()]
        source += ["}"]
        for e in ('test',alert_id,diag_id):
            source += [f"tool {tools[e]} {{ version \"1\"; mode deterministic; }}",
                       f"evidence {e} {{ tool {tools[e]}; kind measurement; environment task_scope; max_age 1800;"]
            if e=='test':
                source += [f"  require {j(measure)} {cmp} {j(limit)};", "  require \"passed\" == true;"]
            elif e==alert_id:
                source += [f"  require \"event\" == {j(alert_flag)};", "  require \"active\" == true;"]
            else:
                source += [f"  require \"origin\" == {j(diag_flag)};", "  require \"independently_checked\" == true;"]
            source += ["}"]
        source += ["reasoning test_step { method \"structured/1\"; rationale \"The finite test log supports its explicitly bounded result, conditional on the authored inference and acquisition identity.\"; }",
                   f"claim operational_record {{ statement {j(statement)}; environment task_scope; }}",
                   "argument primary_test { conclusion operational_record; reasoning test_step; evidence test; }",
                   f"objection recorded_alert {{ target {target_kind} {target_name}; evidence {alert_id}; }}"]
        if defended:
            source += ["reasoning diagnostic_step { method \"structured/1\"; rationale \"The separate diagnosis records the stipulated origin of the alert; physical sufficiency remains authored.\"; }",
                       "claim diagnostic_confirmed { statement \"The separate diagnostic report identifies the alert source for this episode.\"; environment task_scope; }",
                       f"argument diagnostic_route {{ conclusion diagnostic_confirmed; reasoning diagnostic_step; evidence {diag_id}; }}",
                       "objection diagnostic_defence { target objection recorded_alert; premises diagnostic_confirmed; }"]
        # A diagnostic record is deliberately present for three tasks but has
        # no qualifying defence argument. Its presence in a record bundle
        # cannot erase an objection; both renderings expose the same graph.
        roots.append(base(rid,"objection_defence",brief,ctx,"operational_record","\n".join(source)+"\n",
                          records,changed,field,invalid,
                          "supported" if defended else "contested",
                          "contested" if defended else "supported",
                          "the selected objection or separate defence must have a qualifying, fresh record",
                          {"method":"structured/1","details":{"authored":True,"mechanically_proved":False}},
                          reference_rule={"primary":"test","alert":alert_id,"defence":diag_id if defended else None,
                                          "target_kind":target_kind,
                                          "changed_field":field,"valid":"supported" if defended else "contested",
                                          "invalid":"contested" if defended else "supported"}))
    return roots


def main():
    roots=eligibility_roots()+typed_roots()+sampled_roots()+objection_roots()
    assert len(roots)==24 and len({r['id'] for r in roots})==24
    assert {f:sum(r['family']==f for r in roots) for f in ('eligibility','typed_numerical','sampled_negative','objection_defence')} == {
        'eligibility':6,'typed_numerical':6,'sampled_negative':6,'objection_defence':6}
    for r in roots:
        prior,difference=GENEALOGY[r['id']]
        r['genealogy']={'nearest_prior':prior,'mechanism_difference':difference,
                        'sampling_note':'Selected synthetic task; related family members share code and are not independent population draws'}
        source=r.pop('_source')
        (HERE/r['source']).write_text(source,encoding='utf-8')
        ir=semantic_ir(parse(source))
        (HERE/r['semantic_view']).write_text(json.dumps(ir,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    corpus={"schema":"eal2-mechanism-roots/1","version":"developmental-1",
            "review":{"status":"pending_independent_human_review","reviewer_placeholders":["masked_reference_a","masked_reference_b"],
                      "genealogy_rationale":"Twenty-four newly written ordinary questions in four mechanism families, with different equipment, outcome relation, evidence conditions and source; related family members are correlated and selected, not independent population draws. Existing public examples were inspected before construction.",
                      "reference_status":"single_author_rule_plus_local_machine_crosscheck",
                      "acquisition_status":"unsigned_synthetic_file_envelopes_only"},
            "roots":roots}
    (HERE/'manifest.json').write_text(json.dumps(corpus,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
