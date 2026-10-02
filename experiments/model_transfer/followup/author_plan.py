"""Freeze the follow-up material/protocol into an additive diagnostic plan."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parent


def main():
    manifest = json.loads((ROOT / 'task-manifest.json').read_text())
    protocol = json.loads((ROOT / 'protocol.json').read_text())
    base = json.loads((ROOT.parent / 'diagnostic-plan.json').read_text())
    identifiers = [case['identifier'] for case in manifest['cases']]
    plan = {**base,
        'purpose': 'Specified fresh finite synthetic evidence-loss/restoration feasibility pilot; no principal-study power, superiority or external validity claim.',
        'seed': 20261002, 'budget_usd': 2.0, 'max_calls_per_session': 2,
        'max_output_tokens': 1024, 'request_timeout_seconds': 90,
        'response_modes': ['json_prompted'],
        'models': {'plain': base['models']['plain']},
        'pricing_checked_at': '2026-10-02',
        'sources': ['https://developers.openai.com/api/docs/models/gpt-4.1-nano'],
        'model_availability': 'The official page lists the pinned snapshot as deprecated and gives current rates; live account availability is not established until a successful actual provider request. Never silently substitute a model snapshot.',
        'donor': 'plain', 'recipients': ['plain'], 'native_tools': [False],
        'donor_native_tools': False, 'repetitions': 1, 'recipient_sessions': 1,
        'recipient_positions': [2, 4, 6, 8, 10],
        'diagnostic_baseline': {'response_mode': 'json_prompted'},
        'cases': identifiers, 'contrasts': {'reasoner': identifiers},
        'workers': 2, 'protocol_version': protocol['version'],
        'study_id': 'eal-evidence-restoration-followup-20261002',
        'study_role': 'feasibility_pilot', 'pilot_run_ids': [],
        'task_manifest': manifest,
        'task_manifest_sha256': hashlib.sha256(json.dumps(manifest, sort_keys=True,
            separators=(',', ':'), allow_nan=False).encode()).hexdigest(),
        'study_protocol': protocol,
        'evidence_restoration': {
            'conditions': ['complete','critical_gap','restored_positive','restored_negative','noncritical_gap'],
            'primary': 'whole_answer_communicated_decision_and_explanatory_consistency',
            'canonical_decision': 'separate_machine_readable_endpoint',
            'reference_calibration': 'Apparatus checks, not live model accuracy',
            'allocation': 'Eight common donors, fifteen independently cloned recipients per donor: five positions crossed with three reasoner contexts.',
            'material_review': 'experiments/model_transfer/followup/review/independent-reference-review.json',
            'substantive_success': 'For a named reasoner, all 40 whole answers must communicate the correct decision with internal explanatory consistency. Factual grounding and explanation accuracy against task evidence are unassessed. Ambiguous, unresolved and missing outputs cannot establish success.',
            'limits': ['Eight source tasks are deliberately AI-authored in the same orchestration; no independent human task validation.', 'No cause effect estimate because causes covary with task-domain wording.', 'No model-class, population accuracy, principal-study power, superiority or cost-savings claim.'],
        },
    }
    (ROOT / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps({'blocks': 8, 'donors': 8, 'recipients': 120,
                      'sessions': 128, 'maximum_calls': 256,
                      'task_manifest_sha256': plan['task_manifest_sha256']}))


if __name__ == '__main__':
    main()
