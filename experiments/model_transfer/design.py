"""Validate the bounded pilot plan and allocate matched, balanced sequences."""
from __future__ import annotations

import itertools
import math
from pathlib import Path
import random

from experiments.transfer_study.workspace import read_json
from .cases import CASES
from .conditions import CONDITIONS


def load_plan(path: Path) -> dict:
    plan = read_json(path)
    if plan.get('schema') != 'EAL/model-transfer-plan/2':
        raise ValueError('Invalid model transfer plan')
    budget = plan.get('budget_usd')
    if type(budget) not in (int, float) or not math.isfinite(budget) or not 0 < budget <= 2:
        raise ValueError('This pilot permits an API budget in (0, 2] USD')
    for field, maximum in (('max_calls_per_session', 3), ('max_output_tokens', 4096),
                           ('max_request_bytes', 32768), ('request_timeout_seconds', 90),
                           ('repetitions', 3), ('recipient_sessions', 3)):
        if type(plan.get(field)) is not int or not 1 <= plan[field] <= maximum:
            raise ValueError(f'Invalid {field}')
    if type(plan.get('seed')) is not int or type(plan.get('structured_output')) is not bool:
        raise ValueError('Seed and structured_output must be explicitly configured')
    for key, allowed in (('cases', {case.identifier for case in CASES}), ('arms', set(CONDITIONS))):
        values = plan.get(key)
        if (not isinstance(values, list) or not values or any(not isinstance(v, str) for v in values)
                or len(values) != len(set(values)) or not set(values) <= allowed):
            raise ValueError(f'Invalid {key}')
    if not {'ordinary', 'eal'} <= set(plan['arms']):
        raise ValueError('Retain the ordinary comparator and EAL treatment')
    if set(plan['models']) != {'plain', 'reasoning'}:
        raise ValueError('Configure the plain and reasoning model families')
    for name, model in plan['models'].items():
        if not isinstance(model.get('version'), str) or not model['version']:
            raise ValueError('Pinned model version is required')
        if model.get('reasoning_effort') != (None if name == 'plain' else 'low'):
            raise ValueError('Use no reasoning parameter for plain, low for reasoning')
        for key in ('input_per_million', 'output_per_million'):
            rate = model.get(key)
            if type(rate) not in (int, float) or not math.isfinite(rate) or not 0 < rate <= 10:
                raise ValueError('Positive finite price required')
    if plan['models']['plain']['version'] == plan['models']['reasoning']['version']:
        raise ValueError('The family comparison needs distinct model versions')
    if len(AssignmentSchedule(plan).allocations()) > 512:
        raise ValueError('Plan exceeds 512 sequences')
    return plan


class AssignmentSchedule:
    """Cross every case with both donors; shuffle matched blocks and arm order."""

    def __init__(self, plan: dict):
        self.plan = plan

    def allocations(self) -> list[dict]:
        plan = self.plan
        blocks = list(itertools.product(plan['cases'], plan['models'], plan['models'],
                                        (False, True), range(plan['repetitions'])))
        rng = random.Random(plan['seed'])
        rng.shuffle(blocks)
        allocations = []
        for index, (case, donor, receiver, tools, repeat) in enumerate(blocks):
            arms = list(plan['arms'])
            rng.shuffle(arms)
            for arm in arms:
                allocations.append({'case': case, 'donor': donor, 'receiver': receiver,
                                    'native_tools': tools, 'arm': arm, 'repeat': repeat,
                                    'pair_id': f'block-{index:04d}',
                                    'sequence_id': f'block-{index:04d}.{arm}'})
        return allocations
