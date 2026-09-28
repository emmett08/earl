"""Measure harness throughput with fixed synthetic provider latency, without API use."""
from contextlib import redirect_stdout
import argparse
import io
import json
from pathlib import Path
import platform
import statistics
import tempfile
import threading
import time

from experiments.transfer_study.workspace import write_json
from .design import load_plan
from .records import SequenceRecords
from .rehearse import ScriptedTransport
from .run_state import implementation_digest
from .runner import Pilot


class DelayedTransport(ScriptedTransport):
    def __init__(self, delay):
        self.delay, self.active, self.peak = delay, 0, 0
        self.lock = threading.Lock()

    def send(self, payload, timeout):
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            time.sleep(self.delay)
            return super().send(payload, timeout)
        finally:
            with self.lock:
                self.active -= 1


def benchmark(repetitions=3, delay=.15):
    base = load_plan(Path(__file__).with_name('plan.json'))
    base.update(cases=['fresh_positive'], repetitions=1, recipient_sessions=2)
    samples, reference = [], None
    with tempfile.TemporaryDirectory(prefix='eal-throughput-') as directory:
        for repetition in range(repetitions):
            for workers in ((1, 4) if repetition % 2 == 0 else (4, 1)):
                root = Path(directory) / f'{repetition}-{workers}'
                transport = DelayedTransport(delay)
                start = time.monotonic()
                with redirect_stdout(io.StringIO()):
                    report = Pilot({**base, 'workers': workers}, root, transport).run()
                elapsed = time.monotonic() - start
                rows = SequenceRecords(root).load()
                signature = [(r['sequence_id'], r['status'], [(s['session'], s['status'], s['answer'],
                    s['score'], len(s['api_attempt_ids'])) for s in r['sessions']]) for r in rows]
                resources = (report['api_attempts'], round(report['known_cost_usd'], 12))
                if reference is None:
                    reference = signature, resources
                if (signature, resources) != reference or report['execution_status'] != 'complete':
                    raise AssertionError('Scheduling changed completed units, outcomes, request count or synthetic cost')
                samples.append({'repetition': repetition, 'workers': workers, 'elapsed_seconds': elapsed,
                    'peak_inflight_requests': transport.peak, 'sequences': len(rows),
                    'sessions': sum(len(r['sessions']) for r in rows), 'api_attempts': report['api_attempts'],
                    'synthetic_cost_usd': report['known_cost_usd']})
    medians = {str(w): statistics.median(s['elapsed_seconds'] for s in samples if s['workers'] == w) for w in (1, 4)}
    return {'schema': 'EAL/harness-benchmark/1', 'execution_kind': 'scripted',
        'python': platform.python_version(), 'platform': platform.platform(),
        'implementation_sha256': implementation_digest(), 'delay_per_request_seconds': delay,
        'samples': samples, 'median_elapsed_seconds': medians, 'speedup': medians['1'] / medians['4'],
        'outcome_and_resource_equivalence': True,
        'scope': 'Fixed synthetic provider latency; actual EAL preparation and durable persistence. '
                 'One worker is the serial control in the same implementation. No live latency, rate-limit or quality claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--delay', type=float, default=.15)
    args = parser.parse_args()
    if args.repetitions < 1 or not 0 < args.delay <= 10:
        parser.error('Use positive repetitions and a delay in (0, 10] seconds')
    if args.output.exists():
        parser.error('Use a new benchmark output path')
    result = benchmark(args.repetitions, args.delay)
    write_json(args.output, result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
