"""Independently recompute authored references using only Python's standard library.

This reviewer reads raw JSON, never imports corpus_logic, corpus_reference or
the author's generation script, and implements eligibility and three-valued
composition directly from the public task specification.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
INPUT = HERE.parent
REVIEWER = '/root/followup_scientific_review: separate AI reviewer in the same orchestration session'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def scalar_equal(left, right):
    numeric = type(left) in (int, float) and type(right) in (int, float)
    return (type(left) is type(right) or numeric) and left == right


def conjunction(values):
    if False in values:
        return False
    return None if None in values else True


def disjunction(values):
    if True in values:
        return True
    return None if None in values else False


def assess(case, snapshot):
    scope, now = snapshot['scope'], snapshot['now_minute']
    target = case['specification']['scope']
    identity_ok = all(key in scope and scalar_equal(scope[key], target[key])
                      for key in case['specification']['identity_scope_keys'])
    states, details = {}, {}
    for requirement in case['rule']['requirements']:
        candidates, checked = [], []
        for fact in snapshot['facts']:
            if fact['key'] != requirement['fact_key']:
                continue
            blockers = []
            if fact['status'] != 'active':
                blockers.append('inactive')
            if any(key not in fact['scope'] or key not in scope or
                   not scalar_equal(fact['scope'][key], scope[key])
                   for key in requirement['scope_keys']):
                blockers.append('scope_mismatch')
            age = now - fact['observed_at_minute']
            if age < 0:
                blockers.append('future')
            elif age > requirement['max_age_minutes']:
                blockers.append('stale')
            checked.append({'id': fact['id'], 'age_minutes': age, 'blockers': blockers})
            if not blockers:
                candidates.append(fact)
        if not candidates:
            states[requirement['id']] = None
            selected_id = None
        else:
            latest = max(fact['observed_at_minute'] for fact in candidates)
            newest = [fact for fact in candidates if fact['observed_at_minute'] == latest]
            if len(newest) != 1:
                raise ValueError('Public semantics require a uniquely newest eligible fact')
            selected = newest[0]
            selected_id = selected['id']
            value, bound = selected['value'], requirement['expected_value']
            operator = requirement['operator']
            if operator == 'eq':
                state = scalar_equal(value, bound)
            elif operator in ('lte', 'gte'):
                if type(value) not in (int, float) or type(bound) not in (int, float):
                    raise ValueError('Ordered requirements require numbers')
                state = value <= bound if operator == 'lte' else value >= bound
            else:
                raise ValueError('Unsupported public task operator')
            states[requirement['id']] = state
        details[requirement['id']] = {'candidates': checked, 'selected_id': selected_id}
    if case['rule']['type'] == 'all_of':
        route_states = {'all_requirements': conjunction(list(states.values()))}
        result = route_states['all_requirements']
    elif case['rule']['type'] == 'any_of':
        route_states = {route['id']: conjunction([states[key] for key in route['requirement_ids']])
                        for route in case['rule']['alternatives']}
        result = disjunction(list(route_states.values()))
    else:
        raise ValueError('Unsupported public task composition')
    if not identity_ok:
        result = None
    decision = 'undetermined' if result is None else 'ready' if result else 'not_ready'
    return {'decision': decision, 'identity_scope_valid': identity_ok,
            'requirement_states': states, 'route_states': route_states,
            'eligibility': details}


def invariant_checks(case, assessments):
    by_session = {snapshot['session']: snapshot for snapshot in case['timeline']}
    by_result = {row['session']: row for row in assessments}
    kind, rows = case['rule']['type'], []
    def check(name, condition, explanation):
        rows.append({'check': name, 'passed': bool(condition), 'explanation': explanation})
    check('complete_decisive', by_result[2]['decision'] == 'ready',
          'All obligations or the primary route are eligible and satisfied.')
    check('critical_gap_genuine', by_result[4]['decision'] == 'undetermined' and
          by_result[4]['requirement_states']['r0'] is None,
          'The unavailable requirement is necessary to decide: no false all_of conjunct or true any_of route masks its loss.')
    check('positive_restoration', by_result[6]['decision'] == 'ready' and
          by_result[6]['requirement_states']['r0'] is True,
          'Restored r0 is eligible and satisfied; ready is a decisive outcome.')
    check('negative_restoration', by_result[8]['decision'] == 'not_ready' and
          by_result[8]['requirement_states']['r0'] is False,
          'Restored r0 is eligible and fails; not_ready is a decisive outcome.')
    noncritical = by_result[10]
    if kind == 'all_of':
        check('noncritical_false_dominates_unknown', noncritical['decision'] == 'not_ready' and
              noncritical['requirement_states']['r0'] is False and
              noncritical['requirement_states']['r1'] is None,
              'False AND unknown remains false. Comparator is the negative restoration at position 8.')
        comparator = by_session[8]
        unavailable_key = case['rule']['requirements'][1]['fact_key']
    else:
        check('noncritical_true_dominates_unknown', noncritical['decision'] == 'ready' and
              noncritical['route_states']['primary'] is True and
              noncritical['route_states']['reserve'] is None,
              'True OR unknown remains true. Comparator is the positive restoration at position 6.')
        comparator = by_session[6]
        unavailable_key = case['rule']['requirements'][2]['fact_key']
    def values(snapshot):
        return {fact['key']: fact['value'] for fact in snapshot['facts']
                if fact['key'] != unavailable_key}
    check('noncritical_comparator_values_scope', values(by_session[10]) == values(comparator) and
          by_session[10]['scope'] == comparator['scope'],
          'Other requirement values and snapshot scope are unchanged; fact timestamps are refreshed to hold eligibility fixed.')
    check('constant_rule_and_admissibility', all(snapshot['scope'] == by_session[0]['scope']
          for snapshot in case['timeline']) and 'rule' not in by_session[0] and
          all('rule' not in snapshot for snapshot in case['timeline']),
          'One immutable case-level rule defines thresholds, operators, scope keys and age limits for the entire history; no snapshot overrides it.')
    check('unscheduled_continuity', all(by_session[odd]['facts'] == by_session[odd - 1]['facts'] and
          by_session[odd]['scope'] == by_session[odd - 1]['scope']
          for odd in (1, 3, 5, 7, 9)),
          'The five odd positions are retained continuity records, not additional independent live evaluation tasks.')
    check('revision_preserves_state_change', all(
          not any(by_session[position][key] != by_session[position - 1][key] for key in ('facts', 'scope')) or
          by_session[position]['evidence_revision'] > by_session[position - 1]['evidence_revision']
          for position in range(1, 11)),
          'Every change of facts or scope has a public evidence revision; elapsed time and reuse do not silently hide a change.')
    return rows


def mixed_history_checks(case):
    """Public-semantics stress cases, separate from the eight evaluated instances."""
    snapshot = deepcopy(case['timeline'][2])
    snapshot['now_minute'] = 12
    for fact in snapshot['facts']:
        fact['observed_at_minute'] = 12
    r0 = snapshot['facts'][0]
    r0.update(observed_at_minute=6, status='invalidated')
    r0['scope']['artifact_version'] = 'previous-2'
    rows = []
    def add(name, data, decision, state, blockers=None):
        result = assess(case, data)
        passed = result['decision'] == decision and result['requirement_states']['r0'] is state
        if blockers is not None:
            passed = passed and set(result['eligibility']['r0']['candidates'][0]['blockers']) == set(blockers)
        rows.append({'name': name, 'task_id': case['identifier'], 'logic_family': case['rule']['type'],
                     'snapshot': deepcopy(data), 'reference': result,
                     'expected_decision': decision, 'passed': passed})
    add('simultaneous_stale_invalidated_wrong_version', snapshot, 'undetermined', None,
        ['stale', 'inactive', 'scope_mismatch'])
    restored = deepcopy(snapshot)
    new = deepcopy(case['timeline'][6]['facts'][0])
    new.update(id='review-restored-positive', observed_at_minute=12)
    restored['facts'].append(new)
    add('fresh_restore_ignores_retained_multi_blocker_record', restored, 'ready', True)
    negative = deepcopy(restored)
    negative['facts'][-1]['value'] = case['timeline'][8]['facts'][0]['value']
    negative['facts'][-1]['id'] = 'review-restored-negative'
    add('fresh_negative_restore_is_decisive', negative, 'not_ready', False)
    newest_blocked = deepcopy(restored)
    newest_blocked['facts'][0].update(observed_at_minute=13, status='active')
    add('future_wrong_version_record_cannot_mask_eligible_restore', newest_blocked, 'ready', True,
        ['future', 'scope_mismatch'])
    boundary = deepcopy(restored)
    boundary['facts'][-1]['observed_at_minute'] = 7
    add('age_five_is_eligible', boundary, 'ready', True)
    expired = deepcopy(boundary)
    expired['facts'][-1]['observed_at_minute'] = 6
    add('age_six_is_ineligible', expired, 'undetermined', None)
    return rows


def main():
    manifest = json.loads((INPUT / 'task-manifest.json').read_text())
    corpus = json.loads((INPUT / 'task-corpus.json').read_text())
    corpus_as_manifest = {**corpus, 'schema': manifest['schema']}
    records, invariants = [], []
    for case in manifest['cases']:
        case_rows = []
        for snapshot in case['timeline']:
            result = assess(case, snapshot)
            row = {'task_id': case['identifier'], 'family': case['family'],
                   'availability_cause': case['availability_cause'],
                   'session': snapshot['session'], 'condition': snapshot['evidence_condition'],
                   'authored_decision': snapshot['expected'], **result,
                   'agreement': result['decision'] == snapshot['expected'],
                   'rule_sha256': digest(case['rule'])}
            records.append(row)
            case_rows.append(row)
        invariants.append({'task_id': case['identifier'], 'checks': invariant_checks(case, case_rows)})
    family_representatives = {case['rule']['type']: case for case in reversed(manifest['cases'])}
    mixed = [row for case in family_representatives.values() for row in mixed_history_checks(case)]
    scheduled = [row for row in records if row['session'] in (2, 4, 6, 8, 10)]
    failures = [row for row in records if not row['agreement']]
    invariant_failures = [{'task_id': item['task_id'], **check} for item in invariants
                          for check in item['checks'] if not check['passed']]
    report = {
        'schema': 'EAL/followup-independent-scientific-review/1',
        'reviewer': REVIEWER, 'reviewed_at': '2026-10-02',
        'inputs': {'task_manifest_sha256': digest(manifest),
                   'task_corpus_sha256': digest(corpus)},
        'method': 'Direct standard-library raw-fact eligibility, newest selection and strong-Kleene conjunction/disjunction; no authored generator, runtime evaluator or scoring-reference imports.',
        'authorship_independence': 'Distinct author and reviewer agents in the same orchestration session; AI authorship and shared model/family risks remain, and this is not independent human source validation.',
        'manifest_corpus_equal_except_schema': manifest == corpus_as_manifest,
        'task_count': len(manifest['cases']),
        'logic_family_count': len({case['family'] for case in manifest['cases']}),
        'snapshots_recomputed': len(records), 'agreements': len(records) - len(failures),
        'scheduled_case_positions': len(scheduled),
        'scheduled_decisions': dict(Counter(row['decision'] for row in scheduled)),
        'scheduled_conditions': dict(Counter(row['condition'] for row in scheduled)),
        'snapshot_decisions': dict(Counter(row['decision'] for row in records)),
        'disagreements': failures, 'invariant_failures': invariant_failures,
        'mixed_eligibility_tests': mixed, 'records': records, 'invariants': invariants,
        'status': 'passed' if not failures and not invariant_failures and
            all(row['passed'] for row in mixed) and manifest == corpus_as_manifest else 'failed',
        'scope_limits': [
            'Eight purposively constructed fictional instances: four availability causes per each of two logic families. Domain wording and cause are confounded.',
            'Eighty-eight snapshots, forty scheduled case positions and one hundred twenty recipient observations do not create independent population samples.',
            'The retained odd positions are continuity inputs, and mixed-history stress cases are reviewer calibration fixtures outside the participant task denominator.',
            'Agreement validates these deterministic reference calculations, not a model participant capability or the scorer\'s open-domain accuracy.',
            'Protocol, live budget, actual matched state, raw output retention and participant prompt review require separate execution receipts.',
        ],
    }
    path = HERE / 'independent-reference-review.json'
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    markdown = f'''# Independent task reference review

Reviewer: {REVIEWER}. Review date: 2026-10-02.

Status: **{report['status']}**. The independent standard-library calculation agrees with all
{report['agreements']}/{report['snapshots_recomputed']} authored references. It imports neither
`corpus_logic` nor `corpus_reference`, and does not execute the author's input generator.
Run from the repository root with:

```sh
python3 experiments/model_transfer/followup/review/independent_reference_review.py
```

The eight fictional instances span two logic families and four availability causes per
family. The forty scheduled case positions include **8 undetermined and 32 decisive**
answers: 20 ready and 12 not_ready. Positions 0 and all odd continuity positions remain
in the 88-reference review but are outside the recipient denominator. Manifest and
corpus content match except for their declared schema identifiers.

Each critical loss removes the decisive r0 eligibility. The all_of tasks have no false
conjunct to mask this loss; the any_of tasks have a false reserve route and an unknown
primary route. Positive restoration supplies eligible, satisfied r0; negative restoration
supplies eligible, failed r0. Both recover a decisive answer. Noncritical loss is compared
against position 8 in all_of tasks (a remaining false conjunct makes false AND unknown
false), and position 6 in any_of tasks (a remaining true route makes true OR unknown
true). Other requirement values and scope are held fixed, while timestamps are refreshed
to keep unrelated eligibility fixed. One case-level rule and unchanged admission limits
apply throughout each history.

All case invariants pass. Twelve additional reviewer fixtures, six per logic family,
exercise a retained record
with simultaneous stale/inactive/wrong-version blockers; positive and negative restores
while that record remains; a future/wrong-version record; and the inclusive age-five
boundary versus age six. These fixtures are separate machinery checks, not extra sampled
tasks or participant observations.

The author and reviewer are distinct AI agents in the same orchestration session. The
review is unblinded to authored answers, but computes its decision before comparing it;
the evaluator is independently implemented. Shared AI-family failure modes remain.
The instances are deliberate laboratory constructions, not independent human-sampled
cases. Domain wording is confounded with availability cause. Successful deterministic
checks establish bounded material/reference coherence; they establish neither general
human engineering performance nor open-domain scorer accuracy. Live prompts, state
matching, output/error retention, counts and the USD 2 stop require separate runner and
protocol review.

The JSON receipt records exact input hashes, every selected fact and eligibility blocker,
requirement and route states, all 88 decisions, invariant checks and mixed-history inputs.
'''
    (HERE / 'independent-reference-review.md').write_text(markdown)
    print(json.dumps({key: report[key] for key in ('status', 'task_count', 'snapshots_recomputed',
                                                 'agreements', 'scheduled_case_positions',
                                                 'scheduled_decisions')}))
    if report['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
