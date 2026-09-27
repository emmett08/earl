"""Exercise attempt isolation without weakening episode provenance checks."""

from argparse import Namespace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import assemble
import freeze
import host
from workflow_ledger import extract


class AttemptAssemblyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.episodes = self.root / 'episodes'
        self.hosts = self.root / 'hosts'
        self.preflight = self.root / 'preflight'
        self.dispatch = {
            'schema': 'architecture-v3-dispatch-block/1',
            'block': {'id': 'pilot', 'b_class': 'codex_cli',
                      'b_model': 'test-model', 'b_effort': 'medium'},
            'codex_version': '0.154.0', 'source_commit': 'a' * 40,
            'run_id': '123', 'run_attempt': '3',
        }
        self.attempt = self.episodes / 'attempt-3-episode-B-pilot-R-K3'
        self.result = self.hosts / 'attempt-3-host-B-pilot-R-K3'
        self.attempt.mkdir(parents=True)
        self.result.mkdir(parents=True)
        trial = self.attempt / 'trial'
        exposure = self.attempt / 'exposure.json'
        host.prepare(Namespace(source=freeze.BASE, brief=freeze.STUDY / 'features/R-B.md',
                               family='R', feature='B', arm='P0', packet=None,
                               destination=trial, record=exposure))
        self.write(self.result / 'exposure-verification.json',
                   host.verify_exposure(Namespace(trial=trial, record=exposure)))
        (self.result / 'exposure-exit.txt').write_text('0\n')
        host.snapshot(Namespace(trial=trial, record=exposure,
                                destination=self.result / 'source',
                                manifest=self.result / 'code-manifest.json'))
        assessment = subprocess.check_output(
            [sys.executable, str(freeze.STUDY / 'assess.py'), '--candidate',
             str(self.result / 'source'), '--family', 'R', '--stage', 'B'], text=True)
        (self.result / 'assessment.json').write_text(assessment)
        self.invocation = {
            'schema': 'architecture-v3-agent-invocation/1', 'family': 'R',
            'sandbox_backend': 'legacy-landlock', 'sandbox_preflight': 'success',
            'clone': 'R-K3', 'arm': 'P0', 'stage': 'B', 'agent_class': 'codex_cli',
            'requested_model': 'test-model', 'requested_effort': 'medium',
            'source_commit': 'a' * 40, 'run_id': '123', 'run_attempt': '3',
            'cli_version': 'codex-cli 0.154.0', 'started_unix_seconds': 1.0,
            'ended_unix_seconds': 2.0, 'wall_cap_seconds': 1800, 'exit_code': 0,
        }
        self.write(self.attempt / 'invocation.json', self.invocation)
        for name, value in [('agent-start.txt', '1'), ('agent-end.txt', '2'),
                            ('agent-exit.txt', '0')]:
            (self.attempt / name).write_text(value + '\n')
        self.write(self.attempt / 'agent.jsonl', {'type': 'turn.completed', 'usage': {}})
        self.write(self.result / 'ledger.json',
                   extract(self.attempt / 'agent.jsonl', self.attempt / 'invocation.json'))

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value) + '\n')

    def episode(self):
        return assemble.episode('B', 'R', 'R-K3', 'P0', 'pilot',
                                self.episodes, self.hosts, self.preflight, self.dispatch)

    def test_current_attempt_ignores_corrupt_older_and_unscoped_artefacts(self):
        for name in ('attempt-2-episode-B-pilot-R-K3', 'episode-B-pilot-R-K3'):
            old = self.episodes / name
            old.mkdir()
            (old / 'exposure.json').write_text('invalid JSON from previous attempt')
        row = self.episode()
        self.assertEqual(row['runner']['run_attempt'], '3')
        self.assertEqual(row['artifact_names']['episode'], self.attempt.name)
        self.assertEqual(row['assessor']['failed'], 5)

    def test_prior_attempt_cannot_fill_a_missing_current_episode(self):
        self.attempt.rename(self.episodes / 'attempt-2-episode-B-pilot-R-K3')
        with self.assertRaises(FileNotFoundError):
            self.episode()

    def test_renamed_old_invocation_is_still_rejected(self):
        self.invocation['run_attempt'] = '2'
        self.write(self.attempt / 'invocation.json', self.invocation)
        with self.assertRaisesRegex(ValueError, 'workflow run differs'):
            self.episode()

    def test_packet_hosts_use_the_same_attempt_for_every_stage(self):
        for arm in ('P1', 'P2'):
            for stage, kind, leaf in [('B', 'host-pre-B', 'state'),
                                      ('C', 'host-B', 'next-state'),
                                      ('D', 'host-C', 'next-state')]:
                result = assemble._packet_state(stage, 'pilot', 'R-K1', arm, '3',
                                                self.hosts, self.preflight)
                self.assertEqual(result.parent.name, f'attempt-3-{kind}-pilot-R-K1')
                self.assertEqual(result.name, leaf)
        self.assertIsNone(assemble._packet_state('B', 'pilot', 'R-K3', 'P0', '3',
                                                self.hosts, self.preflight))

    def test_failed_invocation_remains_an_observation(self):
        self.invocation['exit_code'] = 1
        self.write(self.attempt / 'invocation.json', self.invocation)
        (self.attempt / 'agent-exit.txt').write_text('1\n')
        self.write(self.result / 'ledger.json',
                   extract(self.attempt / 'agent.jsonl', self.attempt / 'invocation.json'))
        self.assertEqual(self.episode()['runner']['exit_code'], 1)

    def test_successful_cli_exit_does_not_replace_sandbox_preflight(self):
        self.invocation['sandbox_preflight'] = 'failure'
        self.write(self.attempt / 'invocation.json', self.invocation)
        with self.assertRaisesRegex(ValueError, 'sandbox preflight'):
            self.episode()

    def test_attempt_cannot_contain_a_path(self):
        for value in ('../2', '0', '', None, 3):
            with self.assertRaises(ValueError):
                assemble.artifact_name('episode-B', 'pilot', 'R-K3', value)


if __name__ == '__main__':
    unittest.main()
