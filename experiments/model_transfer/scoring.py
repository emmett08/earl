"""Independent reference arithmetic and separate answer-quality dimensions."""
from __future__ import annotations

from datetime import datetime

from .cases import Case


def instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


class ReferenceScorer:
    """Use fixture facts and specification arithmetic; never read EAL statuses."""

    def reference(self, case: Case, session: int) -> dict:
        now = instant(case.time(session))
        measurement = case.measurement(session)
        reading = measurement['value'].get('reading')
        observed = instant(measurement['observed_at'])
        if case.assumption_until and now >= instant(case.assumption_until):
            decision, basis = 'undetermined', 'assumption_expired'
        elif case.assumption_until and now < instant(case.assumption_from):
            decision, basis = 'undetermined', 'assumption_not_started'
        elif reading is None:
            decision, basis = 'undetermined', 'measurement_missing'
        elif not 0 <= (now - observed).total_seconds() <= 300:
            decision, basis = 'undetermined', 'stale_measurement'
        else:
            # Deliberately separate from the installed EAL comparison function.
            failure = reading > case.threshold if case.direction == 'at_most' else reading < case.threshold
            decision, basis = ('not_ready', 'criterion_failed') if failure else ('ready', 'criterion_met')
        return {'decision': decision, 'basis': basis, 'reading': reading,
                'observed_at': measurement['observed_at']}

    def score(self, case: Case, session: int, result: dict) -> dict:
        reference = self.reference(case, session)
        answer = result.get('answer') or {}
        if not isinstance(answer, dict):
            answer = {}
        annotation = result.get('annotation') or {}
        status = annotation.get('status')
        decision = answer.get('decision') if isinstance(answer.get('decision'), str) else None
        basis = answer.get('basis') if isinstance(answer.get('basis'), str) else None
        pending = status in ('pending', 'ambiguous')
        no_answer = status == 'empty' or (not pending and decision not in ('ready', 'not_ready', 'undetermined'))
        if pending:
            return {'reference': reference, 'task_match': None, 'decision_match': None,
                    'assessment_status': 'pending_annotation',
                    'decision_and_basis_match': None, 'grounded_match': None,
                    'internally_consistent': None, 'false_definitive': None,
                    'abstention_when_reference_decisive': None, 'no_answer': False}
        decision_match = decision == reference['decision']
        basis_match = decision_match and basis == reference['basis'] if basis is not None else None
        decisive = reference['decision'] != 'undetermined'
        citation_match = True
        if decisive:
            try:
                citation_match = (type(answer.get('reading')) in (int, float) and
                                  answer['reading'] == reference['reading'] and
                                  instant(answer['observed_at']) == instant(reference['observed_at']))
            except (ValueError, TypeError, AttributeError, KeyError):
                citation_match = False
        else:
            if answer.get('reading') is not None:
                citation_match = (type(answer['reading']) in (int, float) and
                                  answer['reading'] == reference['reading'])
            if answer.get('observed_at') is not None:
                try:
                    citation_match = citation_match and instant(answer['observed_at']) == instant(reference['observed_at'])
                except (ValueError, TypeError, AttributeError):
                    citation_match = False
        consistent = ((decision == 'ready' and basis == 'criterion_met') or
                      (decision == 'not_ready' and basis == 'criterion_failed') or
                      (decision == 'undetermined' and basis in {
                          'measurement_missing', 'assumption_expired', 'assumption_not_started',
                          'stale_measurement', 'evidence_unavailable'})) if basis is not None else None
        # Grounding is a secondary measurement. An absent optional citation is
        # unassessed; it is never substituted for primary task correctness.
        citations_supplied = answer.get('reading') is not None and answer.get('observed_at') is not None
        grounded = (basis_match and citation_match
                    if basis is not None and (not decisive or citations_supplied) else None)
        return {'reference': reference, 'task_match': decision_match, 'decision_match': decision_match,
                'assessment_status': 'no_answer' if no_answer else 'assessed',
                'decision_and_basis_match': basis_match,
                'grounded_match': grounded,
                'internally_consistent': consistent,
                'false_definitive': decision in ('ready', 'not_ready') and not decision_match,
                'abstention_when_reference_decisive': decision == 'undetermined' and decisive,
                'no_answer': no_answer}
