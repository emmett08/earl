"""Map manual workflow inputs to explicit collection or offline study stages."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from experiments.transfer_study.workspace import read_json, write_json
from .artifacts import restore

PLANS = {'comparison': 'plan.json', 'diagnostics': 'diagnostic-plan.json',
         'cadence': 'cadence-plan.json', 'cadence-diagnostics': 'cadence-diagnostic-plan.json'}
ACTIONS = {'collect', 'calibrate', 'rehearse', 'export-annotations', 'import-annotations', 'analyse', 'plan'}


def repository_file(value: str) -> Path:
    root = Path.cwd().resolve()
    path = (root / value).resolve()
    if not value or not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Select an existing file inside the checked-out repository')
    return path


def main():
    action = os.environ.get('EXPERIMENT_ACTION', 'collect')
    if action not in ACTIONS:
        raise ValueError('Unknown experiment action')
    seconds = int(os.environ.get('SEGMENT_SECONDS', '6000'))
    if not 1 <= seconds <= 6000:
        raise ValueError('Workflow segments must allow 1–6000 seconds, leaving 20 minutes for finalisation')
    run = Path('experiments/model_transfer/runs/live')
    artifact = os.environ.get('SOURCE_ARTIFACT_ID', '').strip()
    resume = os.environ.get('RESUME_RUN', 'false') == 'true'
    if resume and action != 'collect':
        raise ValueError('resume_run is only valid for collect; offline and calibration stages never collect')
    if artifact and action in {'calibrate', 'rehearse'}:
        raise ValueError('Use a fresh calibration or rehearsal without source_artifact_id')
    source = run.parent / 'source' if artifact and action == 'collect' and not resume else run
    receipt = None
    if artifact:
        receipt = restore(os.environ['GITHUB_REPOSITORY'], artifact, source)
        if source == run:
            write_json(run / 'restore-receipt.json', receipt)
    elif resume or action in {'export-annotations', 'import-annotations', 'analyse', 'plan'}:
        raise ValueError('This action requires source_artifact_id')
    selection = os.environ.get('TRANSFER_PLAN', 'comparison')
    if resume or action not in {'collect', 'calibrate', 'rehearse'}:
        plan = run / 'plan.json'
    elif selection == 'custom':
        if artifact:
            plan = (source / os.environ.get('PLAN_PATH', '')).resolve()
            if not plan.is_relative_to(source.resolve()) or not plan.is_file():
                raise ValueError('Select a JSON plan inside the source artefact')
        else:
            plan = repository_file(os.environ.get('PLAN_PATH', ''))
    elif artifact:
        raise ValueError('A new run from an artefact requires custom and an explicit plan_path')
    elif selection in PLANS:
        plan = Path(__file__).with_name(PLANS[selection])
    else:
        raise ValueError('Unknown plan selection')
    prefix = [sys.executable, '-m', 'experiments.model_transfer.']
    def command(module, *args):
        return subprocess.run([prefix[0], prefix[1], prefix[2] + module, *map(str, args)], check=True)
    if action in {'collect', 'calibrate'}:
        args = ['--plan', plan, '--output', run, '--segment-seconds', os.environ.get('SEGMENT_SECONDS', '6000')]
        if resume:
            args.append('--resume')
        elif action == 'calibrate':
            args.append('--calibrate-only')
        workers = os.environ.get('EXPERIMENT_WORKERS', '').strip()
        if workers and workers != '0' and not resume:
            if read_json(plan).get('study_role') == 'evaluation' and int(workers) != read_json(plan).get('workers', 1):
                raise ValueError('Evaluation must retain the worker count used for prospective allocation')
            args.extend(['--workers', workers])
        command('runner', *args)
    elif action == 'rehearse':
        command('rehearse', '--plan', plan, '--output', run)
    elif action == 'export-annotations':
        command('annotations', 'export', run, '--all', '--output', run / 'annotation-bundle')
    elif action == 'import-annotations':
        labels = repository_file(os.environ.get('ANNOTATION_LABELS', ''))
        command('annotations', 'import', run, run / 'annotation-bundle', labels, '--output', run / 'annotated-rows.json')
    else:
        args = [run]
        if (run / 'annotated-rows.json').exists():
            args.extend(['--rows', run / 'annotated-rows.json'])
        if action == 'analyse':
            command('analyse', *args, '--output', run / f'analysis-{os.environ["GITHUB_RUN_ID"]}.json')
        else:
            config = os.environ.get('INFORMATION_CONFIG', '').strip()
            if config:
                args.extend(['--config', repository_file(config)])
            elif len(read_json(run / 'plan.json')['cases']) == 18:
                args.extend(['--config', Path(__file__).with_name('cadence-information-design.json')])
            command('plan_information', *args, '--output', run / 'information-report.json',
                    '--evaluation-plan', run / 'evaluation-plan.json')
    if receipt and source != run:
        write_json(run / 'source-plan-receipt.json', receipt)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with Path(summary).open('a') as stream:
            stream.write(f'Experiment stage: **{action}**. Retained artefact: `model-transfer-{os.environ["GITHUB_RUN_ID"]}-{os.environ.get("GITHUB_RUN_ATTEMPT", "1")}`.\n\n')
            stream.write('Inspect report/analysis status and measurement completeness before drawing a scientific conclusion.\n')


if __name__ == '__main__':
    main()
