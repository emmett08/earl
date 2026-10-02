"""Reproduce fresh AI-authored synthetic evidence-loss/restoration inputs.

This is material construction, not participant output or empirical validation.
Run from the repository root. Answer-key review has a separate recorded role.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parent
CREATED = '2026-10-02T13:28:09+00:00'
AUTHOR = '/root/restoration_design: AI material author in the same orchestration session'
CAUSES = ('missing', 'stale', 'invalidated', 'version_mismatch')
CONDITIONS = {0: 'donor_complete', 2: 'complete', 4: 'critical_gap',
              6: 'restored_positive', 8: 'restored_negative', 10: 'noncritical_gap'}

# Entries: identity, label, fact keys, natural-language rule, limit, pass/fail values.
TASKS = {
    'all_of': (
        ('release', 'Fictional service release', ('latency_ms', 'rollback_tested', 'approval'),
         'Release is ready exactly when latency is at most 120 milliseconds, rollback is tested, and approval is granted.', 120, 90, 150),
        ('backup', 'Fictional backup acceptance', ('restore_seconds', 'digest_matches', 'retention_confirmed'),
         'Backup is ready exactly when restore duration is at most 180 seconds, the digest matches, and retention is confirmed.', 180, 150, 210),
        ('assembly', 'Fictional assembly handoff', ('inspection_defects', 'torque_verified', 'serial_registered'),
         'Assembly handoff is ready exactly when inspection has zero defects, torque is verified, and the serial is registered.', 0, 0, 1),
        ('export', 'Fictional export publication', ('validation_errors', 'signature_verified', 'owner_approved'),
         'Export publication is ready exactly when validation has zero errors, the signature is verified, and the owner approved it.', 0, 0, 1),
    ),
    'any_of': (
        ('routing', 'Fictional routing activation', ('primary_delay_ms', 'primary_authenticated', 'fallback_available', 'fallback_authenticated'),
         'Routing is ready when either the primary route has delay at most 120 milliseconds and is authenticated, or the fallback route is available and authenticated.', 120, 90, 150),
        ('restore', 'Fictional restore route selection', ('online_restore_seconds', 'online_digest_matches', 'archive_available', 'archive_digest_matches'),
         'Restore is ready when either the online route takes at most 180 seconds and its digest matches, or the archive route is available and its digest matches.', 180, 150, 210),
        ('cooling', 'Fictional cooling activation', ('main_response_ms', 'main_interlock_passed', 'reserve_available', 'reserve_interlock_passed'),
         'Cooling activation is ready when either the main circuit responds within 40 milliseconds and its interlock passes, or the reserve circuit is available and its interlock passes.', 40, 35, 50),
        ('readpath', 'Fictional read path activation', ('replica_delay_ms', 'replica_authorised', 'cache_available', 'cache_authorised'),
         'The read path is ready when either the replica delay is at most 15 milliseconds and it is authorised, or the cache is available and authorised.', 15, 10, 20),
    ),
}


def unavailable(facts, index, cause, now):
    """Change exactly one requirement's fact eligibility, retaining its value."""
    if cause == 'missing':
        facts.pop(index)
    elif cause == 'stale':
        facts[index]['observed_at_minute'] = now - 6
    elif cause == 'invalidated':
        facts[index]['status'] = 'invalidated'
    else:
        facts[index]['scope']['artifact_version'] = 'previous-2'


def task(kind, index, cause):
    short, label, keys, natural, limit, passing, failing = TASKS[kind][index]
    identifier = f'followup-{kind}-{short}-{cause}'
    scope = {'asset': identifier, 'artifact_version': 'current-3'}
    requirements = [
        {'id': f'r{i}', 'fact_key': key, 'operator': 'lte' if i == 0 else 'eq',
         'expected_value': limit if i == 0 else True, 'max_age_minutes': 5,
         'scope_keys': ['asset', 'artifact_version']}
        for i, key in enumerate(keys)
    ]
    rule = {'type': kind, 'requirements': requirements}
    if kind == 'any_of':
        rule['alternatives'] = [
            {'id': 'primary', 'requirement_ids': ['r0', 'r1']},
            {'id': 'reserve', 'requirement_ids': ['r2', 'r3']},
        ]
    timeline = []
    for session in range(11):
        if session % 2:
            snapshot = deepcopy(timeline[-1])
            snapshot.update(session=session, now_minute=session,
                            evidence_condition='unscheduled_continuity')
            timeline.append(snapshot)
            continue
        values = [passing, True, True] if kind == 'all_of' else [passing, True, False, True]
        condition = CONDITIONS[session]
        if condition == 'restored_negative' or condition == 'noncritical_gap' and kind == 'all_of':
            values[0] = failing
        facts = [{'id': f'{identifier}-fact-{i}', 'key': key, 'value': value,
                  'observed_at_minute': session, 'scope': deepcopy(scope), 'status': 'active'}
                 for i, (key, value) in enumerate(zip(keys, values))]
        manipulated = []
        if condition == 'critical_gap':
            unavailable(facts, 0, cause, session)
            manipulated = ['r0']
        elif condition == 'noncritical_gap':
            other = 1 if kind == 'all_of' else 2
            unavailable(facts, other, cause, session)
            manipulated = [f'r{other}']
        expected = ('undetermined' if condition == 'critical_gap' else
                    'not_ready' if condition == 'restored_negative' or condition == 'noncritical_gap' and kind == 'all_of'
                    else 'ready')
        snapshot = {'session': session, 'now_minute': session, 'scope': deepcopy(scope),
                    'facts': facts, 'expected': expected, 'evidence_revision': session // 2,
                    'evidence_condition': condition, 'availability_cause': cause,
                    'manipulated_requirement_ids': manipulated,
                    'restoration_requirement_id': 'r0', 'pairing_id': identifier,
                    'manipulated_fact_keys': [keys[int(value[1:])] for value in manipulated],
                    'comparison_condition': ('restored_negative' if kind == 'all_of' else 'restored_positive')
                    if condition == 'noncritical_gap' else 'complete',
                    'noncritical_comparator_session': 8 if kind == 'all_of' else 6}
        timeline.append(snapshot)
    return {'identifier': identifier, 'family': f'followup-{kind}',
            'authored_task_id': identifier, 'availability_cause': cause,
            'specification': {
                'scope_description': f'{label}; synthetic asset {identifier}; assess version current-3 only.',
                'natural_language_rule': natural,
                'scope': scope, 'identity_scope_keys': ['asset'],
            }, 'rule': rule, 'timeline': timeline}


def main():
    cases = [task(kind, index, cause) for kind in TASKS for index, cause in enumerate(CAUSES)]
    provenance = {
        'author': AUTHOR,
        'reviewer': '/root/followup_scientific_review: separate AI reviewer in the same orchestration session; independent raw-fact calculation',
        'construction': 'external_ai',
        'population': 'Eight deliberately authored fictional task instances in two three-valued logic families; four availability causes each.',
        'sampling': 'Purposive balanced coverage; no representative or random human-task sample.',
        'created_at': CREATED,
        'limits': [
            'External to the existing pilot corpus, authored by a separate AI agent in the same session; no independent human authorship or external investigator validation.',
            'The automated reference check and separate AI raw-fact review are not blinded human adjudication, external investigator independence, or human task validation.',
            'Domains are fictional and threshold values are artificial; no real measurement, model participant call, or field data was used in construction.',
            'The four causes use different task instances and remain confounded with task-domain wording; causal estimates of cause differences are not identified.',
            'Odd positions preserve prior facts and scope and are unscheduled continuity entries; only even positions 2,4,6,8,10 are live recipient targets.',
        ],
    }
    payload = {'schema': 'EAL/evaluation-task-manifest/1', 'provenance': provenance,
               'conditions': {str(key): value for key, value in CONDITIONS.items()}, 'cases': cases}
    (ROOT / 'task-manifest.json').write_text(json.dumps(payload, indent=2) + '\n')
    corpus = {**payload, 'schema': 'EAL/model-transfer-task-corpus/1'}
    (ROOT / 'task-corpus.json').write_text(json.dumps(corpus, indent=2) + '\n')
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    print(json.dumps({'cases': len(cases), 'timeline_snapshots': len(cases) * 11,
                      'scheduled_positions': len(cases) * 5,
                      'task_manifest_sha256': hashlib.sha256(canonical).hexdigest()}))


if __name__ == '__main__':
    main()
