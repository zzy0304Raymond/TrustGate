"""Offline tests. No model requests, credentials or scheduler allocations are used."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import person2 as local


class LocalAdapterTests(unittest.TestCase):
    def test_real_local_environment_rejects_pbs_impersonation(self):
        with patch.dict(os.environ, {'PBS_JOBID': 'unit-test-only'}):
            with self.assertRaisesRegex(RuntimeError, 'impersonate'):
                local.local_environment()

    def test_existing_claim_stops_before_credentials_or_network(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / 'offline-check.json').write_text(json.dumps({'passed': True, 'local_execution_sha256': 'fixture'}))
            (root / 'claim-fixture.json').write_text('{}')
            with patch.object(local, 'STATE', root), patch.object(local, 'verify_prepared', return_value={'local_execution_sha256': 'fixture'}), \
                 patch.object(local, 'get_key') as key:
                with self.assertRaisesRegex(RuntimeError, 'already claimed'):
                    asyncio.run(local.run('local-person2-fixture'))
                key.assert_not_called()

    def test_network_failure_retains_reservation_and_never_retries(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            state = root / 'local-state'
            state.mkdir()
            (state / 'offline-check.json').write_text(json.dumps({'passed': True, 'local_execution_sha256': 'fixture'}))
            async def start(experiment, stack):
                pass
            async def run_case(experiment, case, index):
                try:
                    experiment.completion([], [], root, 1)
                except TimeoutError:
                    row = {**case, 'error': {'type': 'TimeoutError', 'message': 'fixture'}}
                experiment.rows.append(row)
                return row
            with patch.object(local, 'ROOT', root), patch.object(local, 'STATE', state), \
                 patch.object(local, 'verify_prepared', return_value={'local_execution_sha256': 'fixture'}), \
                 patch.object(local, 'get_key', return_value='offline-fixture-only'), \
                 patch.object(local, 'Detector', return_value=None), \
                 patch.object(local.LocalExperiment, 'start', start), \
                 patch.object(local.LocalExperiment, 'run_case', run_case), \
                 patch.object(local.LocalExperiment, 'completion', side_effect=TimeoutError('fixture')) as request:
                with self.assertRaisesRegex(RuntimeError, 'Run stopped'):
                    asyncio.run(local.run('local-person2-fixture'))
                self.assertEqual(request.call_count, 1)
            folder = root / 'runs/studies/local-person2-fixture/shard-01'
            summary = json.loads((folder / 'worker_summary.json').read_text())
            self.assertFalse(summary['complete'])
            self.assertEqual(summary['recorded'], 1)
            self.assertTrue(summary['budget']['halted'])
            self.assertEqual(summary['budget']['uncertain_reserved_usd'], 0.05)
            self.assertTrue((state / 'claim-fixture.json').exists())

    def test_local_export_redacts_traces_and_cannot_masquerade_as_upstream_receipt(self):
        plan = local.read_plan(local.PLAN)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            worker = root / 'worker'
            worker.mkdir()
            manifest = {'execution_mode': 'local', 'local_execution_sha256': 'fixture'}
            (worker / 'local-manifest.json').write_text(json.dumps(manifest))
            (worker / 'worker_summary.json').write_text(json.dumps({'complete': True, 'fatal_error': None}))
            rows = [dict(c, final_answer='PRIVATE_MARKER', result_dir='/private/path', error=None)
                    for c in plan['shards'][1]['cases']]
            (worker / 'results.json').write_text(json.dumps(rows))
            with patch.object(local, 'verify_prepared', return_value=manifest):
                result = local.export_local(worker, root / 'public')
                self.assertEqual(result['recorded'], 336)
                public = ''.join(p.read_text() for p in (root / 'public').iterdir())
                self.assertNotIn('PRIVATE_MARKER', public)
                self.assertNotIn('/private/path', public)
                self.assertFalse((root / 'public/receipt.json').exists())
                rows[-1] = rows[0]
                (worker / 'results.json').write_text(json.dumps(rows))
                with self.assertRaisesRegex(RuntimeError, 'Duplicate/missing'):
                    local.export_local(worker, root / 'bad')


if __name__ == '__main__':
    # Upstream's isolation fixture mocks the compute guard but assumes a PBS variable.
    # Supply it inside that mocked unit test only, never in the real local runner.
    sys.path.insert(0, str(local.ROOT / 'tests'))
    from test_runner_isolation import RunnerIsolationTests
    original = RunnerIsolationTests.test_five_shards_keep_independent_state_and_accounting
    def mocked_scheduler_fixture(self):
        with patch.dict(os.environ, {'PBS_JOBID': 'unit-test-mocked-scheduler'}):
            original(self)
    with patch.object(RunnerIsolationTests, 'test_five_shards_keep_independent_state_and_accounting', mocked_scheduler_fixture):
        suite = unittest.defaultTestLoader.discover(str(local.ROOT / 'tests'))
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(LocalAdapterTests))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
