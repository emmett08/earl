"""Check diagnostic treatment delivery independently of answer quality."""
from __future__ import annotations

import hashlib
import json
import sqlite3

from .diagnostic_design import BASELINE, FACTORS
from .project import Project


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


class ProjectSnapshot:
    """Fingerprint logical observations separately from mutable SQLite layout."""

    @staticmethod
    def capture(project: Project) -> dict:
        files = {p.relative_to(project.workspace).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(project.workspace.iterdir()) if p.is_file()}
        database = project.workspace / '.eal' / 'runs.sqlite3'
        with sqlite3.connect(database) as connection:
            observations = [json.loads(payload) for (payload,) in connection.execute(
                "SELECT payload FROM records WHERE kind = 'observation' ORDER BY id")]
        return {'files_sha256': files, 'observations_sha256': _digest(observations),
                'observation_count': len(observations),
                'collector_state_sha256': hashlib.sha256(project.state.read_bytes()).hexdigest()}


def _task_facts(value: object) -> object:
    """Omit only generated record identifiers; retain task content and dates."""
    if isinstance(value, dict):
        return {key: _task_facts(item) for key, item in value.items()
                if key not in {'assessment_id', 'observation_id', 'observation_ids'}}
    if isinstance(value, list):
        return [_task_facts(item) for item in value]
    return value


class ManipulationCheck:
    """Check treatment delivery without conditioning on a favourable answer."""

    def check(self, factor: str, variants: list[dict], donor_snapshot: dict, *,
              levels: tuple | None = None, calls: list[dict] | None = None) -> dict:
        failures = []
        specification = FACTORS[factor]
        levels = specification.levels if levels is None else levels
        if len(variants) != len(levels) or {v['level'] for v in variants} != set(levels):
            failures.append('planned_levels_missing')
        for variant in variants:
            level = variant['level']
            expected = {**BASELINE, specification.parameter: level}
            if variant['options'] != expected:
                failures.append('more_than_one_configured_factor_changed')
            if variant.get('input_snapshot') != donor_snapshot:
                failures.append('initial_state_differs')
            if not variant.get('shared_state_unchanged', False):
                failures.append('donor_or_current_evidence_changed')
            result = variant.get('result')
            if not result:
                failures.append('recipient_not_observed')
                continue
            if any(result.get(key) != value for key, value in expected.items()):
                failures.append('configured_component_not_delivered')
            if result.get('native_tools') != variant['native_tools']:
                failures.append('native_tool_mask_changed')
            if not isinstance(result.get('task_context'), dict):
                failures.append('task_context_not_recorded')
            if calls is not None:
                requests = [call['request'] for call in calls if call['session_id'] == variant['session_id']]
                if not requests:
                    failures.append('recipient_request_not_delivered')
                for request in requests:
                    schema = request.get('text', {}).get('format', {}).get('type') == 'json_schema'
                    if schema != (expected['response_mode'] == 'json_schema'):
                        failures.append('response_constraint_not_delivered')
                    if bool(request.get('tools')) != variant['native_tools']:
                        failures.append('native_tool_mask_changed')
        results = [variant['result'] for variant in variants if variant.get('result')]
        facts = [_task_facts(result.get('task_context')) for result in results]
        if facts and any(item != facts[0] for item in facts[1:]):
            failures.append('current_task_information_differs')
        if factor in ('projection', 'notes') and len(results) == len(levels):
            if results[0].get('initial_messages') == results[1].get('initial_messages'):
                failures.append('prompt_manipulation_not_delivered')
        if factor == 'format' and len(results) == len(levels):
            by_mode = {result['response_mode']: result for result in results}
            if ({'json_prompted', 'json_schema'} <= set(by_mode) and
                    by_mode['json_prompted'].get('initial_messages') != by_mode['json_schema'].get('initial_messages')):
                failures.append('schema_contrast_prompt_changed')
        if factor == 'reuse' and len(results) == len(levels):
            for result in results:
                assessments = [event.get('assessment') for event in result.get('events', [])
                               if event.get('kind') == 'eal_assess' and event.get('assessment')]
                key = 'reused_count' if result['reuse'] == 'compatible' else 'collected_count'
                if not assessments or sum(assessment.get(key, 0) for assessment in assessments) < 1:
                    failures.append('acquisition_manipulation_not_delivered')
        return {'status': 'passed' if not failures else 'invalid',
                'failures': sorted(set(failures)),
                'task_information_sha256': [_digest(item) for item in facts],
                'normalised_record_fields': ['assessment_id', 'observation_id', 'observation_ids']}

