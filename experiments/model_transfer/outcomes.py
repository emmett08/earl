"""Summarise task decisions without converting unassessed answers into failures."""
DIAGNOSTICS = ('decision_and_basis_match', 'grounded_match', 'internally_consistent',
               'false_definitive', 'abstention_when_reference_decisive', 'no_answer')


class OutcomeSummary:
    def summarise(self, sessions: list[dict], planned: int) -> dict:
        def counts(key):
            values = [s.get('score', {}).get(key) for s in sessions]
            yes, no = values.count(True), values.count(False)
            unknown = planned - yes - no
            return {'true': yes, 'false': no, 'unknown': unknown,
                    'rate_bounds': [yes / planned, (yes + unknown) / planned] if planned else None}
        task = counts('task_match')
        return {'planned': planned, 'observed': len(sessions), 'unobserved': planned - len(sessions),
                'task_match': task['true'], 'task_scored': planned - task['unknown'],
                'task_unknown': task['unknown'], 'task_rate_bounds': task['rate_bounds'],
                'pending_annotation': sum(s.get('annotation', {}).get('status') in ('pending', 'ambiguous') for s in sessions),
                'diagnostics': {key: counts(key) for key in DIAGNOSTICS},
                'format_failures': sum(s.get('format_valid') is False for s in sessions),
                'format_assessed': sum(s.get('format_valid') is not None for s in sessions),
                'file_failures': sum(s.get('file_result', {}).get('status') == 'rejected' for s in sessions)}
