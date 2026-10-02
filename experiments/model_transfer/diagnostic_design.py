"""Bounded plans and reproducible one-component diagnostic assignments."""
from __future__ import annotations

from dataclasses import dataclass
import itertools
import math
from pathlib import Path
import random

from experiments.transfer_study.workspace import read_json
from .task_manifest import cases_for_plan


@dataclass(frozen=True)
class DiagnosticFactor:
    parameter: str
    levels: tuple


FACTORS = {
    'reasoner': DiagnosticFactor('reasoner', ('facts', 'eal', 'conventional')),
    'projection': DiagnosticFactor('context_style', ('compact', 'full')),
    'notes': DiagnosticFactor('include_notes', (False, True)),
    'format': DiagnosticFactor('response_mode', ('prose', 'json_prompted', 'json_schema')),
    'reuse': DiagnosticFactor('reuse', ('compatible', 'fresh')),
}
BASELINE = {'reasoner': 'workflow', 'context_style': 'compact', 'include_notes': False,
            'response_mode': 'prose', 'reuse': 'compatible'}


def diagnostic_baseline(plan: dict) -> dict:
    return {**BASELINE, **plan.get('diagnostic_baseline', {})}


def recipient_positions(plan: dict) -> tuple[int, ...]:
    """Explicit snapshot positions; each recipient remains a fresh donor clone."""
    return tuple(plan.get('recipient_positions', [1]))


def diagnostic_levels(plan: dict, factor: str) -> tuple:
    return tuple(plan['response_modes']) if factor == 'format' else FACTORS[factor].levels


def load_diagnostic_plan(path: Path) -> dict:
    plan = read_json(path)
    if plan.get('schema') != 'EAL/model-transfer-diagnostic-plan/2':
        raise ValueError('Invalid diagnostic plan')
    from .execution import validate_execution
    validate_execution(plan)
    budget = plan.get('budget_usd')
    if type(budget) not in (int, float) or not math.isfinite(budget) or not 0 < budget <= 2:
        raise ValueError('The shared diagnostic API budget must be in (0, 2] USD')
    for field, maximum in (('max_calls_per_session', 3), ('max_output_tokens', 4096),
                           ('max_request_bytes', 32768), ('request_timeout_seconds', 90),
                           ('repetitions', 32)):
        if type(plan.get(field)) is not int or not 1 <= plan[field] <= maximum:
            raise ValueError(f'Invalid {field}')
    if type(plan.get('seed')) is not int:
        raise ValueError('An integer seed is required')
    if plan.get('response_mode') != 'prose' or type(plan.get('recipient_sessions')) is not int or plan['recipient_sessions'] != 1:
        raise ValueError('Diagnostics use one recipient session per clone and a prose donor response')
    positions = recipient_positions(plan)
    if (not positions or len(set(positions)) != len(positions) or
            any(type(position) is not int or not 1 <= position <= 10 for position in positions)):
        raise ValueError('Select distinct recipient snapshot positions from 1 through 10')
    override = plan.get('diagnostic_baseline', {})
    if not isinstance(override, dict) or not set(override) <= set(BASELINE):
        raise ValueError('Invalid diagnostic baseline override')
    baseline = diagnostic_baseline(plan)
    if type(baseline['include_notes']) is not bool:
        raise ValueError('Diagnostic include_notes must be Boolean')
    for factor in FACTORS.values():
        value = baseline[factor.parameter]
        if value not in factor.levels and not (factor.parameter == 'reasoner' and value == 'workflow'):
            raise ValueError('Invalid diagnostic baseline level')
    if type(plan.get('donor_native_tools', True)) is not bool:
        raise ValueError('The donor native-tool mask must be Boolean')
    models = plan.get('models')
    if not isinstance(models, dict) or not models or len(models) > 4:
        raise ValueError('Configure one to four model profiles')
    for name, model in models.items():
        if (not isinstance(name, str) or not isinstance(model, dict) or
                not isinstance(model.get('version'), str) or not model['version']):
            raise ValueError('Named pinned model profiles are required')
        if 'reasoning_effort' not in model:
            raise ValueError('Declare reasoning_effort, using null when no provider setting is required')
        effort = model['reasoning_effort']
        if effort is not None and (not isinstance(effort, str) or not effort):
            raise ValueError('Reasoning effort must be absent or a nonempty provider value')
        if type(model.get('supports_structured_output', False)) is not bool:
            raise ValueError('Schema-output support must be a Boolean capability declaration')
        for field in ('input_per_million', 'output_per_million'):
            rate = model.get(field)
            if type(rate) not in (int, float) or not math.isfinite(rate) or not 0 < rate <= 10:
                raise ValueError('Positive finite model prices are required')
    for field, permitted in (('recipients', set(models)), ('cases', {c.identifier for c in cases_for_plan(plan)})):
        values = plan.get(field)
        if (not isinstance(values, list) or not values or
                any(not isinstance(v, str) for v in values) or
                len(set(values)) != len(values) or not set(values) <= permitted):
            raise ValueError(f'Invalid {field}')
    if plan.get('donor') not in models:
        raise ValueError('Select a configured donor profile')
    if baseline['response_mode'] == 'json_schema' and any(
            not models[name].get('supports_structured_output', False) for name in plan['recipients']):
        raise ValueError('Schema baseline requires declared structured-output support')
    masks = plan.get('native_tools')
    if (not isinstance(masks, list) or not masks or any(type(v) is not bool for v in masks)
            or len(set(masks)) != len(masks)):
        raise ValueError('Specify distinct Boolean native-tool masks')
    contrasts = plan.get('contrasts')
    if not isinstance(contrasts, dict) or not contrasts or not set(contrasts) <= set(FACTORS):
        raise ValueError('Select declared diagnostic factors')
    if 'format' in contrasts:
        modes = plan.get('response_modes')
        if (not isinstance(modes, list) or len(modes) < 2 or
                any(not isinstance(mode, str) for mode in modes) or
                len(set(modes)) != len(modes) or not set(modes) <= set(FACTORS['format'].levels)):
            raise ValueError('Select at least two distinct response modes for the format contrast')
        if 'json_schema' in modes and any(not models[name].get('supports_structured_output', False)
                                          for name in plan['recipients']):
            raise ValueError('Schema contrasts require declared support; use prompted JSON for other providers')
    for selected in contrasts.values():
        if (not isinstance(selected, list) or not selected or
                any(not isinstance(c, str) for c in selected) or
                len(set(selected)) != len(selected) or not set(selected) <= set(plan['cases'])):
            raise ValueError('Each factor must select distinct planned cases')
    if set().union(*(set(v) for v in contrasts.values())) != set(plan['cases']):
        raise ValueError('Every case must participate in a diagnostic contrast')
    if len(DiagnosticSchedule(plan).allocations()) > 256:
        raise ValueError('Diagnostic plans are limited to 256 donor blocks')
    if plan.get('evidence_restoration'):
        from .restoration import validate_restoration_plan
        validate_restoration_plan(plan)
    return plan


class DiagnosticSchedule:
    def __init__(self, plan: dict):
        self.plan = plan

    def allocations(self) -> list[dict]:
        plan = self.plan
        blocks = list(itertools.product(plan['cases'], plan['recipients'], plan['native_tools'],
                                        range(plan['repetitions'])))
        rng = random.Random(plan['seed'])
        rng.shuffle(blocks)
        assignments = []
        cases = {case.identifier: case for case in cases_for_plan(plan)}
        for index, (case, receiver, tools, repeat) in enumerate(blocks):
            block_id = f'diagnostic-{index:04d}'
            variants = []
            for factor, selected in sorted(plan['contrasts'].items()):
                if case not in selected:
                    continue
                specification = FACTORS[factor]
                for position in recipient_positions(plan):
                    for level_index, level in enumerate(diagnostic_levels(plan, factor)):
                        variant = {'factor': factor, 'level': level, 'level_index': level_index,
                                   'options': {**diagnostic_baseline(plan), specification.parameter: level},
                                   'session_id': f'{block_id}.{factor}-{level_index}.session-{position}'}
                        if 'recipient_positions' in plan:
                            variant['recipient_session'] = position
                        if plan.get('evidence_restoration'):
                            from .restoration import condition_metadata
                            variant['evidence_condition'] = condition_metadata(cases[case], position)
                        variants.append(variant)
            rng.shuffle(variants)
            assignment = {'block_id': block_id, 'case': case, 'donor': plan['donor'],
                                'receiver': receiver, 'native_tools': tools, 'repeat': repeat,
                                'donor_session_id': f'{block_id}.donor.session-0', 'variants': variants}
            if plan.get('evidence_restoration'):
                assignment['task_family'] = cases[case].family
            assignments.append(assignment)
        return assignments
