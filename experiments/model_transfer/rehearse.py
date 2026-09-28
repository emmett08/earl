"""Exercise collection, annotation and reconstruction without calling a model."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from experiments.transfer_study.workspace import read_json, write_json
from .annotations import AnnotationExchange
from .calibration import ContractCalibration
from .cases import CASES, FIRST
from .design import load_plan
from .diagnostics import DiagnosticPilot, load_diagnostic_plan
from .provenance import RunIdentity
from .runner import Pilot


class ScriptedTransport:
    """Supply deliberately fixed answers and synthetic usage for pipeline checks."""

    def send(self, payload: dict, timeout: float) -> dict:
        if payload.get('tools') and not any(
                item.get('type') == 'function_call_output' for item in payload['input']):
            output = [{'type': 'function_call', 'name': 'probe', 'arguments': '{}',
                       'call_id': 'scripted-probe'}]
        else:
            answer = {'decision': 'ready', 'basis': 'criterion_met', 'reading': 180,
                      'observed_at': FIRST, 'explanation': 'Scripted pipeline check.', 'files': []}
            asks_json = payload.get('text') or any(
                'JSON' in item.get('content', '') for item in payload['input']
                if isinstance(item.get('content'), str))
            text = json.dumps(answer) if asks_json else 'Ready. This is a scripted pipeline check.'
            output = [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]
        return {'model': payload['model'], 'status': 'completed', 'output': output,
                'usage': {'input_tokens': 80, 'output_tokens': 30,
                          'input_tokens_details': {'cached_tokens': 0},
                          'output_tokens_details': {'reasoning_tokens': 0}}}


class PipelineRehearsal:
    """Preserve raw records while checking the public annotation/analysis path."""

    def run(self, plan_path: Path, root: Path) -> dict:
        diagnostic = read_json(plan_path).get('schema') == 'EAL/model-transfer-diagnostic-plan/1'
        plan = (load_diagnostic_plan if diagnostic else load_plan)(plan_path)
        root.mkdir(parents=True, exist_ok=False)
        write_json(root / 'plan.json', plan)
        write_json(root / 'cases.json', [asdict(case) for case in CASES if case.identifier in plan['cases']])
        write_json(root / 'protocol.json', read_json(Path(__file__).with_name('protocol.json')))
        calibration = ContractCalibration().check(plan)
        write_json(root / 'calibration.json', calibration)
        if calibration['status'] != 'passed':
            raise ValueError('Rehearsal calibration failed')
        transport = ScriptedTransport()
        RunIdentity.record(root, plan, transport)
        report = (DiagnosticPilot if diagnostic else Pilot)(plan, root, transport).run()
        if report['execution_status'] != 'complete':
            raise ValueError('Scripted collection did not complete')
        exchange = AnnotationExchange()
        bundle = root / 'annotation-bundle'
        exchange.export(root, bundle)
        labels = read_json(bundle / 'items.json')
        labels['annotator'] = 'scripted-pipeline-check-not-human-data'
        for item in labels['items']:
            item.update(decision='ready', quote=item['text'],
                        note='Fixed scripted response explicitly states ready; no reference answer consulted.')
        write_json(root / 'scripted-labels.json', labels)
        exchange.import_labels(root, bundle, root / 'scripted-labels.json', root / 'annotated-rows.json')
        subprocess.run([sys.executable, '-m', 'experiments.model_transfer.analyse', str(root),
                        '--rows', str(root / 'annotated-rows.json')], check=True)
        return self.verify(root)

    def verify(self, root: Path) -> dict:
        """Check completed retained stages, including after an interrupted check."""
        report = read_json(root / 'report.json')
        reconstructed = read_json(root / 'analysis.json')
        bundle = root / 'annotation-bundle'
        raw_digest = read_json(bundle / 'mapping.json')['rows_sha256']
        if raw_digest != hashlib.sha256((root / 'rows.json').read_bytes()).hexdigest():
            raise AssertionError('Annotation changed raw rows')
        for key in ('api_attempts', 'known_cost_usd', 'resources'):
            if key in report and report[key] != reconstructed[key]:
                raise AssertionError(f'Reconstruction changed {key}')
        for arm, horizons in report.get('cumulative_resources', {}).items():
            for horizon, measurements in enumerate(horizons):
                # Coding changes recipient correctness, which is included beside
                # resource measurements in this section of the report.
                for key, value in measurements.items():
                    if key != 'recipient_outcomes' and value != reconstructed['cumulative_resources'][arm][horizon][key]:
                        raise AssertionError(f'Reconstruction changed cumulative {arm}/{horizon}/{key}')
        if reconstructed.get('pending_task_annotations', 0):
            raise AssertionError('Scripted decisions remain uncoded')
        result = {'execution_kind': 'scripted', 'status': 'passed',
                  'calibration_checks': len(read_json(root / 'calibration.json')['checks']),
                  'annotated_answers': len(read_json(bundle / 'items.json')['items']),
                  'api_attempts': report['api_attempts'],
                  'raw_rows_unchanged': True, 'resources_reproduced': True,
                  'interpretation': 'Software rehearsal with fixed answers and synthetic provider usage; '
                                    'no empirical model performance or allocation evidence.'}
        for key in ('planned_sequences', 'planned_sessions', 'planned_blocks', 'planned_recipient_sessions'):
            if key in report:
                result[key] = report[key]
        write_json(root / 'rehearsal.json', result)
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=Path(__file__).with_name('plan.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(PipelineRehearsal().run(args.plan, args.output)))


if __name__ == '__main__':
    main()
