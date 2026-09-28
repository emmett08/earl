"""Verify EAL/context sufficiency against independent references before API use."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .cases import CASES
from .project import Project
from .scoring import ReferenceScorer, instant


class ContractCalibration:
    def check(self, plan: dict) -> dict:
        checks = []
        scorer = ReferenceScorer()
        with TemporaryDirectory(prefix='eal-calibration-') as temporary:
            for case in CASES:
                if case.identifier not in plan['cases']:
                    continue
                try:
                    project = Project(Path(temporary) / case.identifier, case, 'eal')
                    for session in range(1 + plan['recipient_sessions']):
                        project.set_session(session)
                        messages = project.context('Assess the current criterion.')
                        context = json.loads(messages[0]['content'].split('\n', 1)[1])
                        reference = scorer.reference(case, session)
                        if reference['basis'] in ('criterion_met', 'criterion_failed'):
                            outputs = context['arguments']['result']['method_result'].get('outputs', {})
                            passed = (context['claim_status'] == 'supported' and
                                      outputs.get('reading') == reference['reading'] and
                                      outputs.get('meets') == (reference['decision'] == 'ready') and
                                      outputs.get('fails') == (reference['decision'] == 'not_ready'))
                        elif reference['basis'].startswith('assumption_'):
                            expected = reference['basis'].removeprefix('assumption_')
                            passed = (context['claim_status'] == 'unsupported' and
                                      context['assumptions']['window'].get('time_status') == expected)
                        else:
                            passed = (context['claim_status'] == 'unsupported' and
                                      context['evidence']['report']['requirements'] == 'unresolved')
                            if reference['basis'] == 'measurement_missing':
                                passed = passed and {'path': 'reading', 'issue': 'missing_field'} in (
                                    context['evidence']['report'].get('predicate_failures', []))
                        passed = passed and context['summary_complete'] is True
                        if reference['basis'] in ('criterion_met', 'criterion_failed'):
                            passed = passed and instant(context['evidence']['report']['observed_at']) == instant(reference['observed_at'])
                        checks.append({'case': case.identifier, 'session': session, 'passed': passed})
                except Exception as exc:
                    checks.append({'case': case.identifier, 'session': None, 'passed': False,
                                   'error': {'type': type(exc).__name__, 'message': str(exc)[:1000]}})
        return {'status': 'passed' if all(c['passed'] for c in checks) else 'failed',
                'checks': checks, 'scope': 'Software and representation calibration, not model performance.'}
