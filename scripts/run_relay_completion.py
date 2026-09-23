#!/usr/bin/env python3
"""Run the two declared completion phases with one cumulative spending check.

Supply OPENAI_API_KEY in the environment. Existing archives are never resumed
or changed. Model-facing inputs and the EAL runtime remain unchanged.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path

from eal.relay import _write, load_relay_plan, run_relay


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'benchmarks/results/2026-09-23-relays-continuation/budget-reconciliation.json'
PLANS = [
    ('numerical', ROOT / 'benchmarks/experiments/eal2-model-relays-completion-numerical.json'),
    ('repair', ROOT / 'benchmarks/experiments/eal2-model-relays-completion-repair.json'),
]


def phase_exposure(ledger: dict, new_known_cost: float, threshold: float) -> float:
    values = [ledger['known_prior_model_cost_usd'], ledger['prior_unknown_reserve_usd'],
              new_known_cost, threshold, ledger['maximum_single_response_allowance_usd']]
    limit = ledger['user_stop_threshold_usd']
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           or v < 0 for v in [*values, limit]) or threshold <= 0 or limit <= 0:
        raise ValueError('Spending inputs must be finite nonnegative amounts with positive limits')
    exposure = sum(values)
    if exposure > limit:
        raise ValueError('Phase exceeds the cumulative spending allowance')
    return exposure


async def complete(output: Path) -> dict:
    if not os.environ.get('OPENAI_API_KEY'):
        raise ValueError('OPENAI_API_KEY must be supplied through the environment')
    ledger = json.loads(LEDGER.read_text())
    plans = [(name, path, load_relay_plan(path)) for name, path in PLANS]
    for name, _, plan in plans:
        if plan['concurrency'] != 1:
            raise ValueError('Completion must remain serial')
        if plan['max_campaign_model_cost_usd'] != ledger[name + '_phase_threshold_usd']:
            raise ValueError('Phase threshold differs from the retained budget record')
    output.mkdir(parents=True, exist_ok=False)
    state = {'schema': 'EAL/continuation-execution/1', 'status': 'running',
             'started_at': datetime.now(timezone.utc).isoformat(), 'budget': ledger,
             'phases': [], 'new_known_model_cost_usd': 0.0}
    _write(output / 'continuation.json', state)
    try:
        for name, path, plan in plans:
            exposure = phase_exposure(ledger, state['new_known_model_cost_usd'],
                                      plan['max_campaign_model_cost_usd'])
            print(json.dumps({'phase': name, 'status': 'starting',
                              'cumulative_planning_exposure_usd': exposure}), flush=True)
            report = await run_relay(path, output / ('relay-continuation-' + name),
                progress=lambda value: print(json.dumps({'phase': name, **value}), flush=True))
            state['phases'].append({'name': name, **{k: report[k] for k in (
                'status', 'freeze_digest', 'scheduled_trials', 'attempted_trials',
                'completed_trials', 'known_unique_model_cost_usd', 'unique_model_cost_usd')}})
            state['new_known_model_cost_usd'] += report['known_unique_model_cost_usd']
            _write(output / 'continuation.json', state)
            if report['unique_model_cost_usd'] is None or report['status'] != 'completed':
                state['status'] = 'incomplete'
                state['stop_reason'] = 'unknown_usage_or_incomplete_phase'
                break
        else:
            state['status'] = 'completed'
    except BaseException as exc:
        state['status'] = 'interrupted'
        state['stop_reason'] = type(exc).__name__
        raise
    finally:
        state['finished_at'] = datetime.now(timezone.utc).isoformat()
        _write(output / 'continuation.json', state)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(complete(args.output_root.resolve()))
    print(json.dumps({'status': result['status'],
                      'new_known_model_cost_usd': result['new_known_model_cost_usd']}), flush=True)
    raise SystemExit(0 if result['status'] == 'completed' else 2)
