"""Run the ordered experiment workflow, preserving the independent coding step.

This orchestration lives outside the measured implementation. Adding a workflow
does not change the collector identity of an otherwise compatible retained run.
Only ``collect`` invokes the live runner; all other phases are offline.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

from experiments.model_transfer.annotations import AnnotationExchange
from experiments.model_transfer.artifacts import restore
from experiments.model_transfer.design import load_plan
from experiments.model_transfer.diagnostics import load_diagnostic_plan
from experiments.model_transfer.journal import AttemptJournal
from experiments.model_transfer.records import SequenceRecords
from experiments.model_transfer.run_state import RunState, digest
from experiments.model_transfer.workflow import PLANS, repository_file
from experiments.transfer_study.workspace import read_json, utc_now, write_json

BASE = Path('experiments/model_transfer/runs')
LIVE = BASE / 'live'
PREPARED = BASE / 'prepared'
PREFLIGHT = BASE / 'preflight'
SCHEMA = 'EAL/experiment-pipeline/1'
OPERATIONS = {'start', 'resume', 'finish', 'evaluate', 'rehearse'}
TIME_STOP = 'Experiment elapsed-time limit reached; resume the retained run'


def command(module: str, *args) -> None:
    subprocess.run([sys.executable, '-m', 'experiments.model_transfer.' + module,
                    *map(str, args)], check=True)


def validated_plan(path: Path) -> dict:
    loader = (load_diagnostic_plan if read_json(path).get('schema') ==
              'EAL/model-transfer-diagnostic-plan/2' else load_plan)
    return loader(path)


def output(**values) -> None:
    if target := os.environ.get('GITHUB_OUTPUT'):
        with Path(target).open('a', encoding='utf-8') as stream:
            for key, value in values.items():
                stream.write(f'{key}={str(value).lower() if isinstance(value, bool) else value}\n')


def status(root: Path, phase: str, state: str, *, can_collect=False, **details) -> dict:
    value = {'schema': SCHEMA, 'phase': phase, 'state': state,
             'can_collect': can_collect, 'recorded_at': utc_now().isoformat(), **details}
    write_json(root / 'pipeline-status.json', value)
    output(artifact_path=root, can_collect=can_collect, state=state)
    print(f'{phase}: {state}', flush=True)
    return value


def restore_run(destination: Path) -> dict:
    artifact = os.environ.get('SOURCE_ARTIFACT_ID', '').strip()
    if not artifact:
        raise ValueError('Supply the latest retained artefact ID')
    receipt = restore(os.environ['GITHUB_REPOSITORY'], artifact, destination)
    write_json(destination / 'restore-receipt.json', receipt)
    return receipt


def collection_state(root: Path, *, explicit_resume=False) -> dict:
    """Continue automatically only after an ordinary segment deadline.

    Manual resume also admits an interrupted segment or a corrected provider
    problem. Neither route replenishes time or money or replays failed requests.
    """
    plan = validated_plan(root / 'plan.json')
    report = read_json(root / 'report.json') if (root / 'report.json').exists() else {}
    segments = read_json(root / 'segments.json') if (root / 'segments.json').exists() else []
    used = sum(s.get('elapsed_seconds', s['allowance_seconds']) for s in segments)
    spent = sum(c['charged_or_reserved_usd'] for c in AttemptJournal(root).read())
    remaining = max(0, plan.get('time_limit_seconds', 7200) - used)
    reason = (report.get('stop_reason') or report.get('reason') or '').removeprefix('ExecutionStopped: ')
    details = {'remaining_seconds': remaining, 'charged_or_reserved_usd': spent,
               'budget_usd': plan['budget_usd'], 'stop_reason': reason,
               'execution_status': report.get('execution_status', 'interrupted')}
    if report.get('execution_status') == 'complete':
        state, proceed = 'collection_complete', False
    elif remaining <= 0:
        state, proceed = 'time_exhausted', False
    elif spent >= plan['budget_usd'] or reason.startswith('API budget exhausted'):
        state, proceed = 'budget_exhausted', False
    elif reason == TIME_STOP or explicit_resume:
        state, proceed = 'continue_collection', True
    else:
        state, proceed = 'collection_blocked', False
    return {'state': state, 'can_collect': proceed, **details}


def selected_plan() -> Path:
    selection = os.environ.get('TRANSFER_PLAN', 'comparison')
    if selection == 'custom':
        return repository_file(os.environ.get('PLAN_PATH', ''))
    if selection not in PLANS:
        raise ValueError('Unknown plan selection')
    return Path(__file__).resolve().parents[1] / 'experiments/model_transfer' / PLANS[selection]


def prepare(operation: str) -> None:
    if operation == 'resume':
        restore_run(LIVE)
        plan = validated_plan(LIVE / 'plan.json')
        with RunState(LIVE, plan, resume=True).locked():
            pass
        status(LIVE, 'prepare', **collection_state(LIVE, explicit_resume=True))
        return
    if operation not in {'start', 'evaluate', 'rehearse'}:
        raise ValueError('Preparation supports start, resume, evaluate or rehearse')
    receipt = None
    if operation == 'evaluate':
        receipt = restore_run(BASE / 'source')
        path = BASE / 'source/evaluation-plan.json'
        if not path.is_file():
            raise ValueError('Planning did not produce a supported evaluation-plan.json')
        plan = validated_plan(path)
        if plan.get('study_role') != 'evaluation':
            raise ValueError('evaluate requires a prospectively allocated evaluation plan')
    else:
        if os.environ.get('SOURCE_ARTIFACT_ID', '').strip():
            raise ValueError('A fresh start/rehearsal needs no artefact; select resume or evaluate')
        plan = validated_plan(selected_plan())
        if operation == 'start' and plan.get('study_role') == 'evaluation':
            raise ValueError('Use evaluate with the planning artefact for a fresh evaluation')
    workers = int(os.environ.get('EXPERIMENT_WORKERS', '0'))
    if not 0 <= workers <= 8:
        raise ValueError('Workers must be 0 (plan default) or 1–8')
    if workers:
        if plan.get('study_role') == 'evaluation' and workers != plan.get('workers', 1):
            raise ValueError('Evaluation must retain its prospectively allocated worker count')
        plan = {**plan, 'workers': workers}
    PREPARED.mkdir(parents=True, exist_ok=False)
    write_json(PREPARED / 'plan.json', plan)
    if receipt:
        write_json(PREPARED / 'source-plan-receipt.json', receipt)
    command('runner', '--plan', PREPARED / 'plan.json', '--output', PREFLIGHT / 'calibration', '--calibrate-only')
    command('rehearse', '--plan', PREPARED / 'plan.json', '--output', PREFLIGHT / 'rehearsal')
    calibration = read_json(PREFLIGHT / 'calibration/calibration.json')
    rehearsal = read_json(PREFLIGHT / 'rehearsal/rehearsal.json')
    if calibration['status'] != 'passed' or rehearsal['status'] != 'passed':
        raise ValueError('Calibration and rehearsal must both pass before collection')
    write_json(PREPARED / 'preflight.json', {
        'schema': SCHEMA, 'plan_sha256': digest(plan), 'calibration': calibration,
        'rehearsal': rehearsal, 'execution_kind': 'scripted',
        'revision': os.environ.get('GITHUB_SHA'), 'operation': operation})
    status(PREPARED, 'prepare', 'rehearsal_complete' if operation == 'rehearse' else 'ready_to_collect',
           can_collect=operation != 'rehearse', budget_usd=plan['budget_usd'], workers=plan.get('workers', 1))


def collect() -> None:
    # A rerun could restart from the same ancestor, replaying paid work. Recover
    # by a new manual resume dispatch using the latest cumulative artefact.
    if int(os.environ.get('GITHUB_RUN_ATTEMPT', '1')) != 1:
        raise ValueError('Do not rerun paid jobs. Dispatch resume with the latest retained artefact ID')
    source = BASE / 'source'
    receipt = restore_run(source)
    resume = (source / 'execution-contract.json').exists()
    if resume:
        shutil.move(source, LIVE)
        plan = LIVE / 'plan.json'
        with RunState(LIVE, validated_plan(plan), resume=True).locked():
            pass
        before = collection_state(LIVE, explicit_resume=True)
        if not before['can_collect']:
            status(LIVE, 'collect', **before)
            return
    else:
        plan = source / 'plan.json'
        preflight = read_json(source / 'preflight.json')
        if (preflight.get('plan_sha256') != digest(validated_plan(plan)) or
                preflight.get('calibration', {}).get('status') != 'passed' or
                preflight.get('rehearsal', {}).get('status') != 'passed' or
                preflight.get('operation') not in {'start', 'evaluate'}):
            raise ValueError('A fresh collection requires the matching passed preflight artefact')
    args = ['--plan', plan, '--output', LIVE, '--segment-seconds', '6000']
    if resume:
        args.append('--resume')
    try:
        command('runner', *args)
    finally:
        if LIVE.exists():
            write_json(LIVE / 'restore-receipt.json', receipt)
            if not resume:
                shutil.copy2(source / 'preflight.json', LIVE / 'preflight.json')
                if (source / 'source-plan-receipt.json').exists():
                    shutil.copy2(source / 'source-plan-receipt.json', LIVE / 'source-plan-receipt.json')
    status(LIVE, 'collect', **collection_state(LIVE))


def new_analysis_path(stem: str) -> Path:
    path = LIVE / f'{stem}.json'
    index = 2
    while path.exists():
        path = LIVE / f'{stem}-{index}.json'
        index += 1
    return path


def archive_processing() -> None:
    """Retain earlier offline outputs before recoding or changing allocation inputs."""
    paths = [LIVE / name for name in ('annotated-rows.json', 'completed-labels.json',
             'allocation-config.json', 'information-report.json', 'evaluation-plan.json')]
    paths += list(LIVE.glob('analysis-annotated*.json'))
    paths = [path for path in paths if path.exists()]
    if not paths:
        return
    index = 0
    while (LIVE / 'processing' / f'{index:04d}').exists():
        index += 1
    archive = LIVE / 'processing' / f'{index:04d}'
    archive.mkdir(parents=True)
    for path in paths:
        shutil.move(path, archive / path.name)


def export() -> None:
    restore_run(LIVE)
    if not (LIVE / 'rows.json').exists():
        status(LIVE, 'export', 'collection_blocked', message='No collected rows; inspect the retained failure report')
        return
    bundle = LIVE / 'annotation-bundle'
    if bundle.exists():
        if read_json(bundle / 'mapping.json')['rows_sha256'] != hashlib.sha256(SequenceRecords(LIVE).text().encode()).hexdigest():
            raise ValueError('The existing annotation bundle no longer matches the retained rows')
    else:
        AnnotationExchange().export(LIVE, bundle, include_all=True)
    analysis = new_analysis_path('analysis-collection')
    command('analyse', LIVE, '--output', analysis)
    items = read_json(bundle / 'items.json')['items']
    state = collection_state(LIVE)
    status(LIVE, 'export', 'awaiting_annotations' if items else 'no_answers_to_annotate',
           collection=state, answers_to_annotate=len(items), analysis=analysis.name,
           message='Give the assessor only the separate experiment-annotations artefact; '
                   'after coding, dispatch finish with this full run artefact and the labels path.')


def finish() -> None:
    labels = repository_file(os.environ.get('ANNOTATION_LABELS', ''))
    config_value = os.environ.get('INFORMATION_CONFIG', '').strip()
    config = repository_file(config_value) if config_value else None
    restore_run(LIVE)
    bundle = LIVE / 'annotation-bundle'
    mapping, supplied = read_json(bundle / 'mapping.json'), read_json(labels)
    expected = {item['id'] for item in mapping['items']}
    provided = [item['id'] for item in supplied['items']]
    if set(provided) != expected or len(provided) != len(expected):
        raise ValueError('Finish requires one code for every exported answer; ambiguous codes remain unresolved')
    archive_processing()
    rows = LIVE / 'annotated-rows.json'
    AnnotationExchange().import_labels(LIVE, bundle, labels, rows)
    shutil.copy2(labels, LIVE / 'completed-labels.json')
    analysis = new_analysis_path('analysis-annotated')
    command('analyse', LIVE, '--rows', rows, '--output', analysis)
    analysed = read_json(analysis)
    plan = validated_plan(LIVE / 'plan.json')
    diagnostic = plan['schema'] == 'EAL/model-transfer-diagnostic-plan/2'
    planning = 'not_applicable_to_diagnostics' if diagnostic else 'not_applicable_to_evaluation'
    if not diagnostic and plan.get('study_role') == 'pilot':
        if config is None:
            name = 'cadence-information-design.json' if len(plan['cases']) == 18 else 'information-design.json'
            config = Path(__file__).resolve().parents[1] / 'experiments/model_transfer' / name
        shutil.copy2(config, LIVE / 'allocation-config.json')
        args = [LIVE, '--rows', rows, '--config', LIVE / 'allocation-config.json',
                '--output', LIVE / 'information-report.json', '--evaluation-plan', LIVE / 'evaluation-plan.json']
        if read_json(LIVE / 'provenance.json').get('execution_kind') == 'scripted':
            args.append('--allow-scripted')
        command('plan_information', *args)
        planning = read_json(LIVE / 'information-report.json')['status']
    status(LIVE, 'finish', 'processing_complete', analysis=analysis.name,
           analysis_status=analysed['status'], execution_status=analysed['execution_status'], planning=planning,
           evaluation_available=(LIVE / 'evaluation-plan.json').is_file(),
           message='Inspect scientific status and measurement completeness in the analysis. '
                   'A supported evaluation is a separate prospective run, selected explicitly with evaluate.')


def summary() -> None:
    target = os.environ.get('GITHUB_STEP_SUMMARY')
    if not target:
        return
    root = Path(os.environ.get('PIPELINE_ARTIFACT_PATH') or str(LIVE))
    record = read_json(root / 'pipeline-status.json') if (root / 'pipeline-status.json').exists() else {}
    repository, run = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_RUN_ID']
    with Path(target).open('a', encoding='utf-8') as stream:
        stream.write(f'Experiment: **{record.get("state", "failed; inspect retained artefacts and logs")}**.\n\n')
        for key, label in [('PIPELINE_ARTIFACT_ID', 'Full run artefact'), ('ANNOTATION_ARTIFACT_ID', 'Masked answers for the assessor')]:
            if identifier := os.environ.get(key):
                stream.write(f'{label}: [{identifier}](https://github.com/{repository}/actions/runs/{run}/artifacts/{identifier}).\n\n')
        if record.get('phase') == 'export' and record.get('answers_to_annotate', 0):
            stream.write(f'Answers to code: **{record.get("answers_to_annotate", 0)}**. '
                         'Give the assessor only the masked-answer artefact. Commit their completed JSON labels; '
                         'run **EAL experiment → finish**, supplying the full run artefact ID above and the labels path.\n\n')
        elif record.get('phase') == 'export':
            stream.write('No answer labels are available. Inspect the collection failure and retained resource report.\n\n')
        if record.get('phase') == 'finish':
            stream.write(f'Analysis: **{record.get("analysis_status")}**; collection: **{record.get("execution_status")}**.\n\n')
            stream.write(f'Allocation planning: **{record.get("planning")}**. '
                         'If an evaluation plan exists, choose **evaluate** with this artefact to start a separate bounded run.\n\n')
        state = record.get('collection', record)
        if 'remaining_seconds' in state:
            stream.write(f'Collection state: **{state["state"]}**. '
                         f'Charged/reserved: **USD {state["charged_or_reserved_usd"]:.6f}** of '
                         f'**USD {state["budget_usd"]:.2f}**; '
                         f'remaining collection allowance: **{state["remaining_seconds"]:.0f} seconds**.\n\n')
        if state.get('stop_reason'):
            stream.write(f'Stopping reason: {state["stop_reason"]}.\n\n')
        stream.write('All collection segments share the frozen spending and elapsed-time limits. '
                     'Resume an interrupted run using its latest full artefact; do not use Re-run jobs. '
                     'Workflow completion does not establish a scientific result.\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'collect', 'export', 'finish', 'summary'])
    args = parser.parse_args()
    if args.phase == 'summary':
        summary()
        return
    operation = os.environ.get('PIPELINE_OPERATION', 'start')
    if operation not in OPERATIONS:
        raise ValueError('Unknown pipeline operation')
    root = PREPARED if args.phase == 'prepare' and operation != 'resume' else LIVE
    output(artifact_path=root, can_collect=False)
    try:
        if args.phase == 'prepare':
            prepare(operation)
        else:
            {'collect': collect, 'export': export, 'finish': finish}[args.phase]()
    except Exception as exc:
        if root.exists():
            status(root, args.phase, 'failed', error=f'{type(exc).__name__}: {exc}')
        raise


if __name__ == '__main__':
    main()
