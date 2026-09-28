"""Exercise concurrency, crash recovery and immutable execution boundaries."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import signal
import threading
import time
from zipfile import ZipFile, ZipInfo

import pytest

from experiments.model_transfer.artifacts import extract_archive
from experiments.model_transfer.design import load_plan
from experiments.model_transfer.diagnostic_design import load_diagnostic_plan
from experiments.model_transfer.diagnostics import DiagnosticPilot
from experiments.model_transfer.execution import ExecutionControl, ExecutionStopped
from experiments.model_transfer.journal import AttemptJournal
from experiments.model_transfer.provider import BudgetedClient
from experiments.model_transfer.records import SequenceRecords
from experiments.model_transfer.resources import ResourceSummary
from experiments.model_transfer.run_state import RunState, digest
from experiments.model_transfer.runner import Pilot
from experiments.transfer_study.workspace import read_json, write_json


def plan(workers=1):
    value = load_plan(Path('experiments/model_transfer/plan.json'))
    value.update(cases=['fresh_positive'], repetitions=1, recipient_sessions=2,
                 workers=workers, time_limit_seconds=7200)
    return value


class Replies:
    def __init__(self, pause=0):
        self.pause, self.count, self.active, self.peak = pause, 0, 0, 0
        self.lock = threading.Lock()

    def send(self, payload, timeout):
        with self.lock:
            self.count += 1
            self.active += 1
            self.peak = max(self.peak, self.active)
        if self.pause:
            time.sleep(self.pause)
        with self.lock:
            self.active -= 1
        return {'model': payload['model'], 'status': 'completed',
                'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Ready.'}]}],
                'usage': {'input_tokens': 80, 'output_tokens': 30}}


def test_concurrent_pairs_keep_session_order_and_exact_receipts(tmp_path):
    transport = Replies(.01)
    p = plan(4)
    report = Pilot(p, tmp_path, transport).run()
    calls = AttemptJournal(tmp_path).read()
    rows = SequenceRecords(tmp_path).load()
    assert report['execution_status'] == 'complete'
    assert 2 <= transport.peak <= 4
    assert len(calls) == transport.count == 48
    assert [c['attempt'] for c in calls] == list(range(48))
    for start in range(0, len(rows), 2):
        first, second = rows[start:start + 2]
        assert first['pair_id'] == second['pair_id']
        left = [s['api_attempt_ids'][0] for s in first['sessions']]
        right = [s['api_attempt_ids'][0] for s in second['sessions']]
        assert left == sorted(left) and right == sorted(right)
        assert max(left) < min(right)
    before = (tmp_path / 'calls.jsonl').read_bytes()
    repeated = Pilot(p, tmp_path, transport, resume=True).run()
    assert repeated['execution_status'] == 'complete' and transport.count == 48
    assert (tmp_path / 'calls.jsonl').read_bytes() == before
    assert len(read_json(tmp_path / 'segments.json')) == 2


def test_atomic_budget_reserves_all_inflight_requests(tmp_path):
    p = plan(4)
    p['budget_usd'] = .003
    entered, release = threading.Event(), threading.Event()
    class Held(Replies):
        def send(self, payload, timeout):
            entered.set()
            assert release.wait(3)
            return super().send(payload, timeout)
    transport = Held()
    client = BudgetedClient(tmp_path, p, transport)
    with ThreadPoolExecutor(max_workers=4) as pool:
        first = pool.submit(client.request, p['models']['plain'], [], [], 'first')
        try:
            assert entered.wait(3)
            rest = [pool.submit(client.request, p['models']['plain'], [], [], str(i)) for i in range(3)]
            for future in rest:
                with pytest.raises(ExecutionStopped, match='budget'):
                    future.result()
            assert len(AttemptJournal(tmp_path).read()) == 1
        finally:
            release.set()
        first.result()
    assert transport.count == 1 and client._spent < p['budget_usd']


def test_resume_keeps_failed_session_and_cumulative_reservations(tmp_path):
    p = plan()
    class Interrupted(Replies):
        def send(self, payload, timeout):
            if self.count == 1:
                self.count += 1
                raise ExecutionStopped('operator pause')
            return super().send(payload, timeout)
    first = Pilot(p, tmp_path, Interrupted()).run()
    assert first['execution_status'] == 'partial'
    rows = SequenceRecords(tmp_path).load()
    retained = deepcopy(rows[0]['sessions'])
    journal = (tmp_path / 'calls.jsonl').read_bytes()
    old_id = read_json(tmp_path / 'provenance.json')['run_id']
    old_calls = AttemptJournal(tmp_path).read()
    transport = Replies()
    report = Pilot(p, tmp_path, transport, resume=True).run()
    assert report['execution_status'] == 'complete'
    assert SequenceRecords(tmp_path).load()[0]['sessions'][:2] == retained
    assert transport.count == 46
    assert (tmp_path / 'calls.jsonl').read_bytes().startswith(journal)
    assert AttemptJournal(tmp_path).read()[:2] == old_calls
    assert report['charged_or_reserved_usd'] >= sum(c['charged_or_reserved_usd'] for c in old_calls)
    assert read_json(tmp_path / 'provenance.json')['run_id'] == old_id
    assert (tmp_path / 'segments/0001/report.json').is_file()


def test_hard_interruption_does_not_replay_uncertain_request(tmp_path):
    p = plan()
    class Killed(Replies):
        def send(self, payload, timeout):
            raise SystemExit('simulated process termination')
    with pytest.raises(SystemExit):
        Pilot(p, tmp_path, Killed()).run()
    # Model an actual kill after the durable started record, before any finally block.
    event = json.loads((tmp_path / 'calls.jsonl').read_text().splitlines()[0])
    (tmp_path / 'calls.jsonl').write_text(json.dumps(event) + '\n' + '{"event":"fin')
    rows = SequenceRecords(tmp_path).load()
    project = tmp_path / 'sequences' / rows[0]['sequence_id']
    (project / 'session-0.json').unlink()
    transport = Replies()
    Pilot(p, tmp_path, transport, resume=True).run()
    calls = AttemptJournal(tmp_path).read()
    recovered = SequenceRecords(tmp_path).load()[0]['sessions'][0]
    assert calls[0]['status'] == 'started' and calls[0]['cost_estimate_usd'] is None
    assert recovered['status'] == 'interrupted' and recovered['recovery']['replayed_requests'] == 0
    assert recovered['recovery']['uncertain_attempts'] == [0]
    assert transport.count == 47 and len(calls) == 48
    assert len(list(tmp_path.glob('calls-torn-tail-*.bin'))) == 1
    resource = ResourceSummary().summarise([recovered], calls, session_ids={recovered['session_id']})
    assert not resource['accounting_complete'] and not resource['session_coverage_complete']
    assert resource['timed_sessions'] == 0 and not resource['collection_counts_complete']


def test_resume_rejects_changed_identity_and_concurrent_owner(tmp_path):
    p = plan()
    with RunState(tmp_path, p).locked():
        with pytest.raises(ValueError, match='Another process'):
            with RunState(tmp_path, p, resume=True).locked():
                pass
    for key, value in [('workers', 4), ('budget_usd', 1.9), ('seed', 123)]:
        with pytest.raises(ValueError, match='same plan'):
            with RunState(tmp_path, {**p, key: value}, resume=True).locked():
                pass
    contract = read_json(tmp_path / 'execution-contract.json')
    contract['implementation_sha256'] = 'different-code'
    write_json(tmp_path / 'execution-contract.json', contract)
    with pytest.raises(ValueError, match='implementation'):
        Pilot(p, tmp_path, Replies(), resume=True).run()


def test_hard_killed_segment_keeps_full_time_lease(tmp_path):
    p = plan()
    state = RunState(tmp_path, p)
    with state.locked():
        write_json(tmp_path / 'segments.json', [{'allowance_seconds': 7000, 'status': 'running'}])
        with state.segment(6000) as allowance:
            assert allowance == 200
    assert read_json(tmp_path / 'segments.json')[0]['status'] == 'running'


def test_resuming_preserves_and_retires_derived_annotations(tmp_path):
    p = plan()
    with RunState(tmp_path, p).locked():
        write_json(tmp_path / 'annotated-rows.json', [{'old': 'label'}])
        write_json(tmp_path / 'annotation-bundle/items.json', {'items': []})
        write_json(tmp_path / 'evaluation-plan.json', {'old': 'allocation'})
    state = RunState(tmp_path, p, resume=True)
    with state.locked(), state.segment(6000):
        assert not (tmp_path / 'annotated-rows.json').exists()
        assert not (tmp_path / 'evaluation-plan.json').exists()
        assert read_json(tmp_path / 'segments/0000/annotated-rows.json') == [{'old': 'label'}]
        assert (tmp_path / 'segments/0000/annotation-bundle/items.json').exists()


def test_retrying_preparation_keeps_prior_unknown_duration():
    from experiments.model_transfer.diagnostic_preparation import PreparationTimer
    record = {'status': 'started', 'elapsed_seconds': None}
    with PreparationTimer(lambda: None, clock=iter([10, 12]).__next__).measure(record):
        pass
    assert record['status'] == 'complete' and record['elapsed_seconds'] is None
    assert record['last_attempt_seconds'] == 2
    assert record['previous_attempts'] == [{'status': 'started', 'elapsed_seconds': None}]


@pytest.mark.parametrize('response', [None, [], 'malformed'])
def test_recovery_can_read_a_retained_non_object_provider_failure(response):
    from experiments.model_transfer.session import SessionRunner
    assert SessionRunner._response_text(response) == ''


def test_deadline_caps_transport_timeout_and_signals_stop_new_requests(tmp_path):
    p = plan()
    clock = iter([0, 1]).__next__
    control = ExecutionControl(3, clock=clock)
    class Timed(Replies):
        def send(self, payload, timeout):
            assert timeout == 2
            return super().send(payload, timeout)
    client = BudgetedClient(tmp_path, p, Timed(), control=control)
    client.request(p['models']['plain'], [], [], 'first')
    before = signal.getsignal(signal.SIGTERM)
    with control.signals():
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        with pytest.raises(ExecutionStopped, match='Cancellation'):
            client.request(p['models']['plain'], [], [], 'second')
    assert signal.getsignal(signal.SIGTERM) == before
    assert len(client.records) == 1


def test_diagnostic_deadline_and_resume_keep_donor_state(tmp_path):
    p = load_diagnostic_plan(Path('experiments/model_transfer/diagnostic-plan.json'))
    p.update(workers=1, time_limit_seconds=2)
    transport = Replies()
    report = DiagnosticPilot(p, tmp_path, transport, clock=iter([0, 2]).__next__).run()
    assert report['execution_status'] == 'partial' and transport.count == 0
    assert all(row['status'] != 'complete' for row in SequenceRecords(tmp_path).load())
    # A long fresh allowance is a different plan, not a permissible resume amendment.
    with pytest.raises(ValueError, match='same plan'):
        DiagnosticPilot({**p, 'time_limit_seconds': 7200}, tmp_path, transport, resume=True).run()


def test_diagnostic_resume_preserves_donor_and_observed_variants(tmp_path):
    p = load_diagnostic_plan(Path('experiments/model_transfer/diagnostic-plan.json'))
    p['workers'] = 1
    class Pause(Replies):
        def send(self, payload, timeout):
            if self.count == 2:
                raise ExecutionStopped('operator pause')
            return super().send(payload, timeout)
    report = DiagnosticPilot(p, tmp_path, Pause()).run()
    assert report['execution_status'] == 'partial'
    previous = SequenceRecords(tmp_path).load()[0]
    journal = (tmp_path / 'calls.jsonl').read_bytes()
    transport = Replies()
    report = DiagnosticPilot(p, tmp_path, transport, resume=True).run()
    assert report['execution_status'] == 'complete'
    current = SequenceRecords(tmp_path).load()[0]
    assert current['donor_result'] == previous['donor_result']
    assert current['donor_snapshot'] == previous['donor_snapshot']
    for variant, retained in zip(current['variants'], previous['variants']):
        if 'result' in retained:
            assert variant == retained
    assert (tmp_path / 'calls.jsonl').read_bytes().startswith(journal)
    assert transport.count == report['api_attempts'] - 3


@pytest.mark.parametrize('mode', ['json_prompted', 'json_schema'])
def test_contradictory_json_is_never_automatically_correct(mode):
    from experiments.model_transfer.answers import response_format
    from experiments.model_transfer.cases import CASES
    from experiments.model_transfer.scoring import ReferenceScorer
    text = json.dumps({'decision': 'ready', 'basis': 'criterion_met', 'reading': 180,
        'observed_at': '2026-09-28T10:00:00Z', 'explanation': 'The service is not ready.', 'files': []})
    parsed = response_format(mode).parse(text)
    assert parsed['format_valid'] and parsed['annotation']['status'] == 'pending'
    assert ReferenceScorer().score(CASES[0], 0, parsed)['task_match'] is None


@pytest.mark.parametrize('loader,filename', [(load_plan, 'plan.json'), (load_diagnostic_plan, 'diagnostic-plan.json')])
@pytest.mark.parametrize('key,value', [('time_limit_seconds', -1), ('time_limit_seconds', 0),
                                      ('time_limit_seconds', True), ('workers', 0), ('workers', 9)])
def test_execution_limits_are_validated_before_collection(tmp_path, loader, filename, key, value):
    p = read_json(Path('experiments/model_transfer') / filename)
    p[key] = value
    path = tmp_path / 'bad.json'
    write_json(path, p)
    with pytest.raises(ValueError, match=key):
        loader(path)


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'a/../../outside', 'a\\outside'])
def test_artefact_restore_rejects_path_escape_before_extracting(tmp_path, name):
    archive = tmp_path / 'input.zip'
    with ZipFile(archive, 'w') as bundle:
        bundle.writestr('plan.json', '{}')
        bundle.writestr(name, 'bad')
    with pytest.raises(ValueError, match='Unsafe'):
        extract_archive(archive, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_artefact_rejects_symlinks_and_requires_plan(tmp_path):
    archive = tmp_path / 'input.zip'
    with ZipFile(archive, 'w') as bundle:
        entry = ZipInfo('link')
        entry.external_attr = 0o120777 << 16
        bundle.writestr(entry, '/tmp')
    with pytest.raises(ValueError, match='Unsafe'):
        extract_archive(archive, tmp_path / 'out')
    with ZipFile(archive, 'w') as bundle:
        bundle.writestr('plan.json', '{}')
        bundle.writestr('sequences/a/notes.md', 'retained')
    extract_archive(archive, tmp_path / 'out')
    assert (tmp_path / 'out/sequences/a/notes.md').read_text() == 'retained'


def test_pinned_scientific_validator_sources_are_unchanged():
    root = Path('tools/investigation-validator')
    for filename, expected in read_json(root / 'provenance.json')['files'].items():
        assert hashlib.sha256((root / filename).read_bytes()).hexdigest() == expected


def test_concurrent_feasibility_uses_batch_maxima_and_conservative_reservations():
    from experiments.model_transfer.trajectory_simulation import TrajectorySimulator
    from test_model_transfer_information_design import pilot, scenario
    trajectories = pilot(repetitions=1, horizon=2)
    serial, one = TrajectorySimulator(trajectories, 2, 100, workers=1).simulate(['task'], 1, scenario(0), random.Random(17))
    concurrent, four = TrajectorySimulator(trajectories, 2, 100, workers=4).simulate(['task'], 1, scenario(0), random.Random(17))
    assert concurrent == serial
    assert four['charged_usd'] == pytest.approx(one['charged_usd'])
    assert four['elapsed_seconds'] == pytest.approx(one['elapsed_seconds'] / 4)
    bounded, limit = TrajectorySimulator(trajectories, .003, 100, workers=4).simulate(['task'], 1, scenario(0), random.Random(17))
    assert limit['budget_stopped'] and limit['charged_usd'] == 0
    assert all(o.ordinary_tokens is None and o.quality_lower == -1 for o in bounded)
