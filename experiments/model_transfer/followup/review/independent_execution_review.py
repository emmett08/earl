"""Check frozen follow-up records without importing the runner or its scorers.

Run with --run /path/to/retained/rehearsal. This is a standard-library review of
the retained wire requests, raw task inputs and independently computed reference
receipt. Scripted transport records are never promoted to model measurements.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from independent_reference_review import assess, digest

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[3]
POSITIONS = (2, 4, 6, 8, 10)
LEVELS = ('facts', 'eal', 'conventional')
FORBIDDEN = ('expected_decisions', 'authored_decision', 'evidence_condition',
             'availability_cause', 'manipulated_requirement_ids',
             'manipulated_fact_keys', 'noncritical_comparator_session',
             'restoration_requirement_id', 'comparison_condition', 'pairing_id')


def read(path):
    return json.loads(Path(path).read_text())


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def keys(value):
    if isinstance(value, dict):
        yield from value
        for child in value.values():
            yield from keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from keys(child)


def expected_measurement(case, position):
    snapshot = case['timeline'][position]
    now = (datetime(2026, 9, 28, 10, tzinfo=timezone.utc) +
           timedelta(minutes=snapshot['now_minute'])).isoformat().replace('+00:00', 'Z')
    target = {key: case['specification']['scope'][key]
              for key in case['specification']['identity_scope_keys']}
    return {'observed_at': now, 'value': {
        'task_id': case['identifier'], 'rule_digest': digest(case['rule']),
        'rule': case['rule'], 'target_identity': target,
        'target_identity_digest': digest(target), 'now_minute': snapshot['now_minute'],
        'scope': snapshot['scope'], 'facts': snapshot['facts']}}, now


def normalised_messages(messages):
    result = []
    for message in messages:
        item = dict(message)
        content = item.get('content', '')
        prefix = 'Current task facts and any supplied computed conclusion:\n'
        if isinstance(content, str) and content.startswith(prefix):
            packet = json.loads(content[len(prefix):])
            packet.pop('decision', None)
            item['content'] = prefix + json.dumps(packet, sort_keys=True, separators=(',', ':'))
        result.append(item)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    plan, rows, calls = read(run / 'plan.json'), read(run / 'rows.json'), read(run / 'calls.json')
    manifest = read(HERE.parent / 'task-manifest.json')
    corpus = {case['identifier']: case for case in manifest['cases']}
    checks, failures = [], []
    def check(name, passed, detail):
        row = {'check': name, 'passed': bool(passed), 'detail': detail}
        checks.append(row)
        if not passed:
            failures.append(row)
    check('frozen_manifest', plan['task_manifest'] == manifest and
          plan['task_manifest_sha256'] == digest(manifest),
          'Retained plan contains the exact independently reviewed raw manifest.')
    check('current_frozen_plan', plan == read(HERE.parent / 'plan.json'),
          'Reviewed rehearsal uses the final current frozen plan and its embedded protocol.')
    check('allocation', len(rows) == 8 and len({row['case'] for row in rows}) == 8 and
          {row['case'] for row in rows} == set(corpus) and
          sum(len(row['variants']) for row in rows) == 120,
          'Eight donor blocks and 120 recipient variants; no denominator inflation.')
    check('no_native_tools', plan['native_tools'] == [False] and
          plan['donor_native_tools'] is False and all(not call['request'].get('tools') for call in calls),
          'Neither donor nor recipient wire requests contain native tools.')
    ids, input_groups, requests, state_checks, context_rows = [], 0, 0, 0, []
    by_session = {}
    for call in calls:
        by_session.setdefault(call['session_id'], []).append(call)
    for row in rows:
        case = corpus[row['case']]
        expected_cells = {(position, level) for position in POSITIONS for level in LEVELS}
        actual_cells = {(v['recipient_session'], v['level']) for v in row['variants']}
        check(row['block_id'] + ':crossing', actual_cells == expected_cells and len(row['variants']) == 15,
              'One recipient per fixed position and reasoner.')
        snapshots = row.get('donor_snapshots', {})
        histories = [{key: value for key, value in snapshots[str(position)].items()
                      if key != 'collector_state_sha256'} for position in POSITIONS]
        check(row['block_id'] + ':common_donor', all(item == histories[0] for item in histories),
              'Only the external collector state changes across five positions; donor workspace and logical observations are identical.')
        for position in POSITIONS:
            variants = [v for v in row['variants'] if v['recipient_session'] == position]
            measurements, prompts = [], []
            expected, now = expected_measurement(case, position)
            reference = assess(case, case['timeline'][position])['decision']
            for variant in variants:
                sid = variant['session_id']
                ids.append(sid)
                result = variant.get('result') or {}
                packet = result.get('task_context') or {}
                inputs = packet.get('inputs') or {}
                measurements.append(inputs)
                check(sid + ':raw_inputs', inputs.get('measurement') == expected and inputs.get('now') == now and
                      case['specification']['natural_language_rule'] in inputs.get('specification', ''),
                      'Exact raw facts, scope, criterion, artificial current time and observation timestamp are delivered.')
                check(sid + ':conclusion', ('decision' not in packet if variant['level'] == 'facts' else
                      packet.get('decision') == reference),
                      'Facts withhold a computed conclusion; host-reasoner conclusion matches the independently computed reference.')
                check(sid + ':state', variant['input_snapshot'] == snapshots[str(position)] and
                      variant.get('shared_state_unchanged') is True,
                      'Recipient starts from its matched donor state and cannot mutate the shared state.')
                state_checks += 1
                messages = result.get('initial_messages') or []
                first_requests = by_session.get(sid, [])
                check(sid + ':wire_prompt', bool(first_requests) and
                      first_requests[0]['request']['input'] == messages,
                      'Retained initial prompt equals the first actual wire request.')
                requests += len(first_requests)
                rendered = json.dumps(messages)
                check(sid + ':oracle_metadata_absent', not set(keys(packet)) & set(FORBIDDEN) and
                      not any('"' + forbidden + '"' in rendered for forbidden in FORBIDDEN) and
                      'Project files:' not in rendered,
                      'No authored answer-key/intervention metadata or donor notes enter the participant prompt. expected_value is a public criterion, not an answer key.')
                prompts.append(normalised_messages(messages))
                context_rows.append({'session_id': sid, 'task_id': case['identifier'],
                    'position': position, 'reasoner': variant['level'], 'reference': reference,
                    'task_input_sha256': digest(inputs), 'prompt_sha256': digest(messages)})
            check(row['block_id'] + f':position-{position}:matched_inputs',
                  all(inputs == measurements[0] for inputs in measurements) and
                  all(prompt == prompts[0] for prompt in prompts),
                  'Across reasoners, only the delivered computed decision field differs; facts, dates, time, prompts and notes exposure match.')
            input_groups += 1
    check('recipient_unique_ids', len(ids) == len(set(ids)) == 120, 'All recipient identifiers are unique.')
    rate = plan['models'][plan['donor']]
    per_call = ((plan['max_request_bytes'] + 4096) * rate['input_per_million'] +
                plan['max_output_tokens'] * rate['output_per_million']) / 1e6
    envelope = 128 * plan['max_calls_per_session'] * per_call
    check('reservation_envelope', abs(envelope - 1.048576) < 1e-12 and envelope <= plan['budget_usd'],
          'At configured official rates, all 256 maximum calls fit within the USD 2 reservation ceiling.')
    check('no_task_repetition_claim', plan['repetitions'] == 1,
          'One repetition establishes no stochastic repeatability or principal-study power.')
    provenance = read(run / 'provenance.json')
    if provenance.get('execution_kind') == 'scripted':
        labels = read(run / 'scripted-labels.json')
        check('scripted_assessor_provenance', labels.get('assessor', {}).get('kind') == 'scripted',
              'Fixed rehearsal labels are explicitly scripted; no human or AI model assessment is invented.')
        annotated = read(run / 'annotated-rows.json')
        recipients = [variant['result'] for row in annotated for variant in row['variants']]
        check('scripted_always_ready_control', sum(result['score'].get('substantive_match') is True
              for result in recipients) == 60 and len(recipients) == 120,
              'The fixed always-ready fixture matches 20/40 references per reasoner and cannot pass the all-40 task criterion.')
    report = {'schema': 'EAL/followup-independent-execution-review/1',
        'reviewer': '/root/followup_scientific_review: separate AI reviewer in the same orchestration session',
        'reviewed_at': '2026-10-02', 'status': 'passed' if not failures else 'failed',
        'execution_kind': provenance.get('execution_kind', 'see retained provenance'),
        'run': str(run), 'input_hashes': {name: file_hash(run / name)
                                      for name in ('plan.json', 'rows.json', 'calls.json', 'provenance.json')},
        'task_manifest_sha256': digest(manifest), 'checks': checks, 'failures': failures,
        'reviewed_source_sha256': {name: file_hash(SOURCE / 'experiments/model_transfer' / name)
            for name in ('restoration.py', 'diagnostic_design.py', 'diagnostic_measurement.py',
                         'diagnostic_reporting.py', 'diagnostics.py', 'reasoning_context.py',
                         'session.py', 'answers.py', 'annotations.py', 'scoring.py',
                         'provider.py', 'execution.py', 'rehearse.py')},
        'recipient_contexts_checked': len(context_rows), 'matched_position_groups': input_groups,
        'recipient_state_checks': state_checks, 'recipient_api_attempt_records': requests,
        'configured_cost': {'rates_usd_per_million': {'input': rate['input_per_million'], 'output': rate['output_per_million']},
                            'maximum_calls': 256, 'reservation_per_call_usd': per_call,
                            'reservation_envelope_usd': envelope, 'two_repeat_envelope_usd': 2 * envelope,
                            'shared_cap_usd': plan['budget_usd']},
        'contexts': context_rows,
        'limits': ['A scripted rehearsal validates only tested delivery and record paths; no actual model accuracy or empirical cost follows.',
                   'Task identifiers include their availability cause as public authored asset names; all three reasoners receive the same identity. Cause-domain wording remains confounded.',
                   'Same-family AI review and automated scoring can share errors; neither reference agreement nor masked judge agreement supplies independent human or open-domain accuracy validation.',
                   'The official model page lists the configured snapshot and rates but labels the model Deprecated; account availability requires an actual successful provider request.',
                   'Primary substantive endpoint is communicated verdict correctness plus internal explanatory consistency. Factual explanation accuracy requires a separate measure and is unassessed.']}
    (HERE / 'independent-execution-review.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'recipient_contexts_checked',
                                                 'matched_position_groups', 'recipient_state_checks')}))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
