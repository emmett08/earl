"""Validate the bounded pilot plan and allocate matched, balanced sequences."""
from __future__ import annotations

import itertools
import math
from pathlib import Path
import random

from experiments.transfer_study.workspace import read_json
from .cases import CASES
from .conditions import CONDITIONS
from .information_config import validate_decision_specification, validate_information_target

MAX_SEQUENCES = 65536


def load_plan(path: Path) -> dict:
    plan = read_json(path)
    if plan.get('schema') != 'EAL/model-transfer-plan/3':
        raise ValueError('Invalid model transfer plan')
    validate_decision_specification(plan.get('practical_decision'))
    validate_information_target(plan.get('information_target'))
    budget = plan.get('budget_usd')
    if type(budget) not in (int, float) or not math.isfinite(budget) or not 0 < budget <= 2:
        raise ValueError('This pilot permits an API budget in (0, 2] USD')
    for field, maximum in (('max_calls_per_session', 3), ('max_output_tokens', 4096),
                           ('max_request_bytes', 32768), ('request_timeout_seconds', 90),
                           ('repetitions', 512), ('recipient_sessions', 10)):
        if type(plan.get(field)) is not int or not 1 <= plan[field] <= maximum:
            raise ValueError(f'Invalid {field}')
    if type(plan.get('seed')) is not int or plan.get('response_mode') != 'prose':
        raise ValueError('Comparison requires an explicit seed and ordinary prose responses')
    if (type(plan.get('time_limit_seconds', 7200)) is not int or
            not 1 <= plan.get('time_limit_seconds', 7200) <= 7200):
        raise ValueError('Declare an elapsed-time limit no longer than 7200 seconds')
    if plan.get('study_role') not in ('pilot', 'evaluation'):
        raise ValueError('Declare whether this is a pilot or an independent evaluation')
    if not isinstance(plan.get('study_id'), str) or not plan['study_id'].strip():
        raise ValueError('Declare a nonempty study_id')
    pilot_ids = plan.get('pilot_run_ids')
    if (not isinstance(pilot_ids, list) or any(not isinstance(value, str) or not value for value in pilot_ids)
            or len(pilot_ids) != len(set(pilot_ids)) or plan['study_id'] in pilot_ids):
        raise ValueError('Invalid pilot_run_ids or reused study identity')
    if plan['study_role'] == 'evaluation' and not pilot_ids:
        raise ValueError('An evaluation must identify its allocation pilot runs')
    for key, allowed in (('cases', {case.identifier for case in CASES}), ('arms', set(CONDITIONS))):
        values = plan.get(key)
        if (not isinstance(values, list) or not values or any(not isinstance(v, str) for v in values)
                or len(values) != len(set(values)) or not set(values) <= allowed):
            raise ValueError(f'Invalid {key}')
    if set(plan['arms']) != {'ordinary', 'eal'}:
        raise ValueError('Retain the ordinary comparator and EAL treatment')
    if set(plan['models']) != {'plain', 'reasoning'}:
        raise ValueError('Configure the plain and reasoning model families')
    for name, model in plan['models'].items():
        if not isinstance(model.get('version'), str) or not model['version']:
            raise ValueError('Pinned model version is required')
        if model.get('reasoning_effort') != (None if name == 'plain' else 'low'):
            raise ValueError('Use no reasoning parameter for plain, low for reasoning')
        if type(model.get('supports_structured_output')) is not bool:
            raise ValueError('Declare provider/model schema-output capability explicitly')
        for key in ('input_per_million', 'output_per_million'):
            rate = model.get(key)
            if type(rate) not in (int, float) or not math.isfinite(rate) or not 0 < rate <= 10:
                raise ValueError('Positive finite price required')
    if plan['models']['plain']['version'] == plan['models']['reasoning']['version']:
        raise ValueError('The family comparison needs distinct model versions')
    if len(AssignmentSchedule(plan).allocations()) > MAX_SEQUENCES:
        raise ValueError(f'Plan exceeds {MAX_SEQUENCES} sequences')
    return plan


class AssignmentSchedule:
    """Cross every case with both donors; shuffle matched blocks and arm order."""

    def __init__(self, plan: dict):
        self.plan = plan

    def allocations(self) -> list[dict]:
        plan = self.plan
        # Serialisation may reorder JSON mappings. Model labels, not insertion
        # order, determine the replayable randomisation input.
        models = sorted(plan['models'])
        blocks = list(itertools.product(plan['cases'], models, models,
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
