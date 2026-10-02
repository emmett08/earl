"""Check authored material against two implementations without model calls.

These checks calibrate the apparatus; none is live participant accuracy.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from experiments.model_transfer.corpus_cases import load_cases
from experiments.model_transfer.corpus_logic import CorpusComputation
from experiments.model_transfer.corpus_reference import CorpusReference
from experiments.model_transfer.task_manifest import manifest_cases


ROOT = Path(__file__).parent
POSITIONS = (2, 4, 6, 8, 10)


def main():
    payload = json.loads((ROOT / 'task-manifest.json').read_text())
    cases = manifest_cases(payload)
    local = load_cases(ROOT / 'task-corpus.json')
    assert len(cases) == len(local) == 8
    assert all(a.rule == b.rule and a.timeline == b.timeline and
               a.expected_decisions == b.expected_decisions for a, b in zip(cases, local))
    rows = []
    for case in cases:
        for position in range(11):
            oracle = CorpusReference().reference(case, position)
            method = CorpusComputation()(case.measurement(position)['value'])
            assert oracle['decision'] == method['decision'] == case.expected_decisions[position]
            states = method['states']
            if position in POSITIONS:
                condition = case.timeline[position]['evidence_condition']
                # Explicit authored design expectations, not inferred from method outcomes.
                expected_states = ({'r0': True, 'r1': True, 'r2': True} if case.rule['type'] == 'all_of'
                                   else {'r0': True, 'r1': True, 'r2': False, 'r3': True})
                if condition == 'critical_gap':
                    expected_states['r0'] = None
                elif condition == 'restored_negative':
                    expected_states['r0'] = False
                elif condition == 'noncritical_gap':
                    if case.rule['type'] == 'all_of':
                        expected_states.update(r0=False, r1=None)
                    else:
                        expected_states['r2'] = None
                assert states == expected_states
                rows.append({'case': case.identifier, 'rule_type': case.rule['type'],
                             'cause': case.timeline[position]['availability_cause'],
                             'position': position, 'condition': condition,
                             'states': states, 'reference_decision': oracle['decision']})
    distribution = Counter(row['reference_decision'] for row in rows)
    unknown_by_condition = Counter(row['condition'] for row in rows
                                   if row['reference_decision'] == 'undetermined')
    assert distribution == {'ready': 20, 'not_ready': 12, 'undetermined': 8}
    assert unknown_by_condition == {'critical_gap': 8}
    summary = {
        'schema': 'EAL/evidence-restoration-material-checks/1',
        'kind': 'synthetic_apparatus_calibration_not_live_model_accuracy',
        'checked_timeline_snapshots': 88, 'matching_authored_oracle_and_method': 88,
        'scheduled_positions': 40, 'scheduled_decisive_references': 32,
        'scheduled_unknown_references': 8, 'unintended_unknown_references': 0,
        'scheduled_requirement_state_checks': 40,
        'scheduled_distribution': dict(distribution),
        'negative_restoration_reference_checks': 8,
        'positive_restoration_reference_checks': 8,
        'noncritical_gap_reference_checks': 8,
        'always_undetermined_reference_accuracy': 8 / 40,
        'always_ready_reference_accuracy': 20 / 40,
        'always_not_ready_reference_accuracy': 12 / 40,
        'budget_calculation': {
            'model_rates_usd_per_million': {'input': 0.1, 'output': 0.4},
            'input_wire_byte_cap': 32768, 'framing_token_reservation': 4096,
            'output_token_cap': 1024, 'sessions': 128, 'calls_per_session_cap': 2,
            'maximum_calls': 256, 'reservation_per_call_usd': 0.004096,
            'maximum_reservation_envelope_usd': 1.048576,
            'two_repeat_envelope_usd': 2.097152,
            'shared_budget_usd': 2.0,
            'qualification': 'Conservative reservation at the configured rates; prices must be checked before execution. Actual costs include failed attempts, use provider usage, and may be lower.',
        },
        'task_manifest_sha256': hashlib.sha256(json.dumps(payload, sort_keys=True,
            separators=(',', ':'), allow_nan=False).encode()).hexdigest(),
        'rows': rows,
        'limits': ['Two software implementations can share a specification error.',
                   'The explicit authored state expectations were written by the material author.',
                   'Separate AI material review remains a different check, not human external validation.',
                   'Neither reference agreement nor fixed-input cost accounting measures model reasoning or study power.'],
    }
    (ROOT / 'material-checks.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({key: value for key, value in summary.items() if key not in ('rows', 'limits')}))


if __name__ == '__main__':
    main()
