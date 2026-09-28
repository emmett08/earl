"""Combine observed API expenditure with explicitly measured adoption activities."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

CATEGORIES = ('authoring', 'correction', 'maintenance', 'host')
ARMS = ('ordinary', 'eal')


def identity(plan: dict) -> str:
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def new_ledger(plan: dict, run_id: str) -> dict:
    return {'schema': 'EAL/adoption-cost-ledger/1', 'run_id': run_id, 'plan_sha256': identity(plan),
        'currency': 'USD', 'events': [], 'coverage': [
            {'arm': arm, 'category': category, 'through_session': -1, 'evidence': None}
            for arm in ARMS for category in CATEGORIES]}


def validate_ledger(ledger: dict, plan: dict, run_id: str) -> None:
    if (ledger.get('schema') != 'EAL/adoption-cost-ledger/1' or ledger.get('currency') != 'USD'
            or ledger.get('run_id') != run_id or ledger.get('plan_sha256') != identity(plan)):
        raise ValueError('Cost ledger identity, currency or schema differs from the run')
    ids = set()
    horizon = plan['recipient_sessions']
    for event in ledger['events']:
        if not isinstance(event.get('id'), str) or not event['id'] or event['id'] in ids:
            raise ValueError('Cost event identities must be nonempty and unique')
        ids.add(event['id'])
        if event.get('arm') not in ARMS or event.get('category') not in CATEGORIES:
            raise ValueError('Unknown cost arm or category')
        if type(event.get('session')) is not int or not 0 <= event['session'] <= horizon:
            raise ValueError('Cost activity must fall in the observed horizon')
        if not isinstance(event.get('evidence'), str) or not event['evidence'].strip():
            raise ValueError('Cost activities require a measurement record reference')
        if type(event.get('seconds')) not in (int, float) or not math.isfinite(event['seconds']) or event['seconds'] < 0:
            raise ValueError('Measured seconds must be finite and nonnegative')
        rate = event.get('hourly_usd')
        if rate is not None and (type(rate) not in (int, float) or not math.isfinite(rate) or rate < 0):
            raise ValueError('Cost rates must be declared nonnegative USD/hour values or unknown')
    seen = set()
    for coverage in ledger['coverage']:
        key = coverage['arm'], coverage['category']
        if key not in {(a, c) for a in ARMS for c in CATEGORIES} or key in seen:
            raise ValueError('Duplicate or unknown cost coverage')
        seen.add(key)
        through = coverage.get('through_session')
        if type(through) is not int or not -1 <= through <= horizon:
            raise ValueError('Invalid cost coverage horizon')
        if through >= 0 and (not isinstance(coverage.get('evidence'), str) or not coverage['evidence'].strip()):
            raise ValueError('Complete coverage, including zero work, needs an explicit measurement reference')
    if len(seen) != 8:
        raise ValueError('Every arm/category needs an explicit measured or unknown coverage record')


def assess_costs(report: dict, ledger: dict, plan: dict, run_id: str) -> dict:
    validate_ledger(ledger, plan, run_id)
    coverage = {(item['arm'], item['category']): item['through_session'] for item in ledger['coverage']}
    rows = []
    for horizon in range(plan['recipient_sessions'] + 1):
        arms = {}
        for arm in ARMS:
            measured = [item for item in ledger['events'] if item['arm'] == arm and item['session'] <= horizon]
            activities = {}
            for category in CATEGORIES:
                events = [event for event in measured if event['category'] == category]
                complete = coverage[arm, category] >= horizon
                priced = all(event['hourly_usd'] is not None for event in events)
                activities[category] = {'known_seconds': sum(event['seconds'] for event in events),
                    'complete': complete, 'priced': priced,
                    'cost_usd': sum(event['seconds'] * event['hourly_usd'] / 3600 for event in events) if complete and priced else None}
            api = report['cumulative_resources'][arm][horizon]['resources']
            api_cost = api['known_cost_usd'] if api['cost_accounting_complete'] else None
            complete = api_cost is not None and all(item['cost_usd'] is not None for item in activities.values())
            arms[arm] = {'api_cost_usd': api_cost, 'activities': activities,
                         'total_cost_usd': api_cost + sum(item['cost_usd'] for item in activities.values()) if complete else None}
        left, right = arms['ordinary']['total_cost_usd'], arms['eal']['total_cost_usd']
        rows.append({'through_session': horizon, 'arms': arms,
            'saving_usd': left - right if left is not None and right is not None else None})
    crossings = [row['through_session'] for row in rows if row['saving_usd'] is not None and row['saving_usd'] >= 0]
    return {'schema': 'EAL/adoption-cost-result/1', 'status': 'complete' if all(row['saving_usd'] is not None for row in rows) else 'incomplete',
        'currency': 'USD', 'cumulative': rows, 'first_observed_cost_crossing': min(crossings) if crossings else None,
        'quality_decision': report.get('practical_decision', {}).get('status', 'unassessed'),
        'interpretation': 'Study-wide measured activities valued at declared rates, plus reconciled API estimates. '
            'A cost crossing is not a quality-preserving adoption result. Unknown effort or rates remain unknown; no extrapolation.',
        'ledger_sha256': identity(ledger)}


def main() -> None:
    import argparse
    from uuid import uuid4
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('init', 'record', 'cover', 'report'))
    parser.add_argument('run', type=Path)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--arm', choices=ARMS)
    parser.add_argument('--category', choices=CATEGORIES)
    parser.add_argument('--session', type=int)
    parser.add_argument('--seconds', type=float)
    parser.add_argument('--hourly-usd', type=float)
    parser.add_argument('--evidence')
    parser.add_argument('--analysis', type=Path)
    args = parser.parse_args()
    plan = json.loads((args.run / 'plan.json').read_text())
    run_id = json.loads((args.run / 'provenance.json').read_text())['run_id']
    if args.action == 'init':
        if args.ledger.exists():
            raise ValueError('Use a new ledger path')
        ledger = new_ledger(plan, run_id)
    else:
        ledger = json.loads(args.ledger.read_text())
        validate_ledger(ledger, plan, run_id)
    if args.action in ('record', 'cover'):
        if args.arm is None or args.category is None or args.session is None or not args.evidence:
            parser.error('record and cover require arm, category, session and evidence')
        if args.action == 'record':
            ledger['events'].append({'id': str(uuid4()), 'arm': args.arm, 'category': args.category,
                'session': args.session, 'seconds': args.seconds, 'hourly_usd': args.hourly_usd, 'evidence': args.evidence})
        else:
            entry = next(row for row in ledger['coverage'] if (row['arm'], row['category']) == (args.arm, args.category))
            if args.session < entry['through_session']:
                raise ValueError('Coverage cannot silently regress')
            entry.update(through_session=args.session, evidence=args.evidence)
        validate_ledger(ledger, plan, run_id)
    if args.action == 'report':
        if not args.output or args.output.exists():
            raise ValueError('Use a new report output path')
        report = json.loads((args.analysis or args.run / 'report.json').read_text())
        args.output.write_text(json.dumps(assess_costs(report, ledger, plan, run_id), indent=2) + '\n')
    else:
        # Existing ledgers are append-only snapshots: edits create a new version.
        destination = args.ledger if args.action == 'init' else args.output
        if destination is None or destination.exists():
            raise ValueError('Use --output with a new ledger version path')
        destination.write_text(json.dumps(ledger, indent=2) + '\n')


if __name__ == '__main__':
    main()
