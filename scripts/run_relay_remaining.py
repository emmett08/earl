#!/usr/bin/env python3
"""Run explicitly selected missing blocks without changing the frozen EAL runtime.

The study manifest selects complete blocks from the canonical schedule. The
selection adapter is confined to this serial invocation; its source hash and
the manifest are embedded in the protocol captured by freeze_relay.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tarfile

from eal import relay
from eal.experiment import _code_identity
from run_relay_completion import phase_exposure


ROOT = Path(__file__).resolve().parents[1]


def select_schedule(schedule: list[dict], blocks: list[str]) -> list[dict]:
    if not blocks or len(blocks) != len(set(blocks)):
        raise ValueError('Selected blocks must be nonempty and unique')
    available = {row['block_id'] for row in schedule}
    if not set(blocks) <= available:
        raise ValueError('A selected block is absent from the canonical schedule')
    return [row for row in schedule if row['block_id'] in blocks]


@contextmanager
def selected_schedule(blocks):
    original = relay.make_schedule

    def selected(plan, task_ids):
        return select_schedule(original(plan, task_ids), blocks)

    relay.make_schedule = selected
    try:
        yield
    finally:
        relay.make_schedule = original


def read_bound_json(path: Path, expected_sha256: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Retained input changed: ' + str(path))
    return json.loads(raw)


def preflight(manifest_path: Path) -> tuple[dict, Path, float]:
    manifest = json.loads(manifest_path.read_text())
    if manifest['schema'] != 'EAL/remaining-block-plan/1':
        raise ValueError('Unsupported selection manifest')
    selected = manifest['selected_blocks']
    previous = read_bound_json(ROOT / manifest['prior_analysis'], manifest['prior_analysis_sha256'])
    if set(selected) != set(previous['missing_blocks']):
        raise ValueError('Selection must contain exactly the previously missing blocks')
    archive = ROOT / manifest['canonical_archive']
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest['canonical_archive_sha256']:
        raise ValueError('Canonical archive changed')
    with tarfile.open(archive) as tf:
        reference = json.load(tf.extractfile(next(m for m in tf.getmembers()
                                                  if Path(m.name).name == 'freeze.json')))
    if _code_identity()['source_digest'] != reference['runtime']['source_digest']:
        raise ValueError('Model-facing EAL source changed')
    expected = select_schedule(reference['schedule'], selected)
    if len(expected) != manifest['scheduled_endpoints']:
        raise ValueError('Incorrect selected endpoint count')
    path = ROOT / manifest['relay_plan']
    read_bound_json(path, manifest['relay_plan_sha256'])
    plan = relay.load_relay_plan(path)
    for field in ('conditions', 'budget', 'per_mcp_call_usd', 'max_handoff_bytes',
                  'repetitions', 'order_seed', 'split'):
        if plan[field] != reference['plan'][field]:
            raise ValueError('Treatment or schedule configuration changed: ' + field)
    if plan['concurrency'] != 1:
        raise ValueError('Selection adapter requires serial execution')
    ledger = read_bound_json(ROOT / manifest['budget_ledger'], manifest['budget_ledger_sha256'])
    exposure = phase_exposure(ledger, 0, plan['max_campaign_model_cost_usd'])
    protocol = json.loads((path.parent / plan['protocol']).read_text())
    if protocol['execution']['continuation_manifest'] != manifest:
        raise ValueError('Protocol does not bind this selection manifest')
    if protocol['execution']['continuation_launcher_sha256'] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError('Selection launcher differs from the frozen protocol')
    with selected_schedule(selected):
        frozen = relay.freeze_relay(path)
    if frozen['schedule'] != expected:
        raise ValueError('Selected schedule differs from canonical identities and ordering')
    for field in ('suite_digest', 'provider_configurations', 'scorer'):
        if frozen[field] != reference[field]:
            raise ValueError('Frozen task or provider contract changed: ' + field)
    return manifest, path, exposure


async def run(manifest_path: Path, output: Path, freeze_only: bool):
    manifest, path, exposure = preflight(manifest_path)
    if not freeze_only and not os.environ.get('OPENAI_API_KEY'):
        raise ValueError('Supply OPENAI_API_KEY in the environment')
    print(json.dumps({'selected_blocks': manifest['selected_blocks'],
                      'scheduled_endpoints': manifest['scheduled_endpoints'],
                      'cumulative_planning_exposure_usd': exposure}), flush=True)
    with selected_schedule(manifest['selected_blocks']):
        result = await relay.run_relay(path, output, freeze_only=freeze_only,
            progress=lambda value: print(json.dumps(value), flush=True))
    relay._write(output / 'selection-manifest.json', manifest)
    relay._write(output / 'selection-execution.json', {
        'schema': 'EAL/remaining-block-execution/1',
        'recorded_at': datetime.now(timezone.utc).isoformat(),
        'launcher_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        'cumulative_planning_exposure_usd': exposure,
        'status': result['status'], 'freeze_digest': result['freeze_digest'],
    })
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--freeze-only', action='store_true')
    args = parser.parse_args()
    result = asyncio.run(run(args.manifest.resolve(), args.output.resolve(), args.freeze_only))
    print(json.dumps({k: result[k] for k in ('status', 'scheduled_trials', 'freeze_digest')}), flush=True)
    raise SystemExit(0 if result['status'] in {'completed', 'frozen'} else 2)
