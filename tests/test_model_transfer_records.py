"""Recover interrupted collection without dropping planned observations."""
import copy
import json

import pytest

from experiments.model_transfer.records import SequenceRecords
from experiments.transfer_study.workspace import read_json


def planned_rows():
    return [{'sequence_id': 'pair.' + arm, 'pair_id': 'pair', 'case': 'fresh_positive',
             'donor': 'plain', 'receiver': 'plain', 'native_tools': False, 'repeat': 0,
             'arm': arm, 'status': 'not_run', 'sessions': []} for arm in ('ordinary', 'eal')]


def test_interrupted_checkpoint_retains_latest_session_and_other_planned_arm(tmp_path):
    rows = planned_rows()
    store = SequenceRecords(tmp_path)
    store.begin(rows)
    rows[0].update(status='started', sessions=[{'session': 0, 'score': {'task_match': True}}])
    store.record(rows[0])
    assert read_json(tmp_path / 'rows.json')[0]['sessions'] == []
    assert SequenceRecords(tmp_path).load() == rows
    assert SequenceRecords(tmp_path).load()[1]['status'] == 'not_run'
    # A torn next write has no effect on the previous atomic checkpoint.
    (store.directory / 'interrupted.json.tmp').write_text('{')
    assert store.load() == rows
    store.finish(rows)
    assert store.text() == (tmp_path / 'rows.json').read_text()
    assert store.load() == rows


def test_checkpoint_cannot_reassign_a_sequence_or_overwrite_a_run(tmp_path):
    rows = planned_rows()
    store = SequenceRecords(tmp_path)
    store.begin(rows)
    invalid = copy.deepcopy(rows[0])
    invalid['arm'] = 'eal'
    store.record(invalid)
    with pytest.raises(ValueError, match='assigned treatment'):
        store.load()
    with pytest.raises(ValueError, match='new run'):
        store.begin(rows)


def test_completed_and_diagnostic_rows_keep_exact_annotation_digest_input(tmp_path):
    raw = json.dumps([{'donor_result': None, 'variants': []}]) + '\n'
    (tmp_path / 'rows.json').write_text(raw)
    assert SequenceRecords(tmp_path).text() == raw


def test_elapsed_deadline_stops_without_a_request_and_keeps_planned_rows(tmp_path):
    from pathlib import Path
    from experiments.model_transfer.design import load_plan
    from experiments.model_transfer.runner import Pilot

    class NoRequests:
        def send(self, payload, timeout):
            raise AssertionError('Deadline must stop before contacting the transport')

    plan = load_plan(Path('experiments/model_transfer/plan.json'))
    plan.update(cases=['fresh_positive'], repetitions=1, recipient_sessions=2, workers=1, time_limit_seconds=7200)
    clock = iter([0, 7200]).__next__
    report = Pilot(plan, tmp_path, NoRequests(), clock=clock).run()
    assert report['execution_status'] == 'partial'
    assert report['api_attempts'] == 0
    rows = SequenceRecords(tmp_path).load()
    assert len(rows) == 16 and all(not row['sessions'] for row in rows)
    assert sum(row['status'] == 'stopped' for row in rows) == 1
    assert 'elapsed-time limit' in report['stop_reason']
