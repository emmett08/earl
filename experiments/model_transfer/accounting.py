"""Reconcile session receipts with the durable request ledger."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


def valid_attempt(value: object) -> bool:
    return type(value) is int and value >= 0


@dataclass(frozen=True)
class AttemptAccounting:
    calls: list[dict]
    errors: list[dict]
    expected_attempts: int | None
    session_coverage_complete: bool

    @property
    def complete(self) -> bool:
        return not self.errors


class AttemptReconciler:
    """Count a zero only when a persisted session explicitly records no attempts.

    The ledger is inspected globally so an attempt assigned to a different
    session or recorded twice cannot satisfy a receipt. Whole-run summaries
    retain unassigned records, including reservations made before a crash.
    """

    def reconcile(self, sessions: list[dict], calls: list[dict], ids: set[str], *,
                  include_unassigned: bool = False) -> AttemptAccounting:
        errors: list[dict] = []
        by_session, by_attempt = defaultdict(list), defaultdict(list)
        for session in sessions:
            by_session[session.get('session_id')].append(session)
        for call in calls:
            if valid_attempt(call.get('attempt')):
                by_attempt[call['attempt']].append(call)
        coverage = set(by_session) == ids and all(len(rows) == 1 for rows in by_session.values())
        receipts: dict[str, list[int]] = {}
        for sid in sorted(ids):
            rows = by_session.get(sid, [])
            if len(rows) != 1:
                errors.append({'kind': 'missing_or_duplicate_session_result', 'session_id': sid})
                continue
            receipt = rows[0].get('api_attempt_ids')
            if (not isinstance(receipt, list) or any(not valid_attempt(item) for item in receipt) or
                    len(receipt) != len(set(receipt))):
                errors.append({'kind': 'missing_or_invalid_attempt_receipt', 'session_id': sid})
                continue
            session = rows[0]
            if not receipt and ('provider_status' in session or session.get('raw_answer') or
                                session.get('response_texts') or session.get('answer') is not None or
                                session.get('status') == 'submitted'):
                errors.append({'kind': 'zero_attempt_receipt_contradicts_response', 'session_id': sid})
                continue
            receipts[sid] = receipt
            for attempt in receipt:
                records = by_attempt.get(attempt, [])
                if len(records) != 1 or records[0].get('session_id') != sid:
                    errors.append({'kind': 'missing_duplicate_or_misattributed_attempt',
                                   'session_id': sid, 'attempt': attempt})
        for sid in by_session.keys() - ids:
            errors.append({'kind': 'unassigned_session_result', 'session_id': sid})
        selected = calls if include_unassigned else [call for call in calls if call.get('session_id') in ids]
        for call in selected:
            sid, attempt = call.get('session_id'), call.get('attempt')
            if sid not in ids:
                errors.append({'kind': 'unassigned_attempt', 'session_id': sid, 'attempt': attempt})
            elif not valid_attempt(attempt):
                errors.append({'kind': 'invalid_attempt_identity', 'session_id': sid})
            elif attempt not in receipts.get(sid, []):
                errors.append({'kind': 'attempt_without_session_receipt', 'session_id': sid, 'attempt': attempt})
        expected = sum(map(len, receipts.values())) if coverage and len(receipts) == len(ids) else None
        return AttemptAccounting(selected, errors, expected, coverage)
