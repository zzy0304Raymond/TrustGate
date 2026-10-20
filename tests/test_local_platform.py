"""Portable adapter contract tests; fake model only, no benchmark/model downloads."""
import asyncio
import contextlib
import csv
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'scripts/platforms/local'
sys.path.insert(0, str(LOCAL))
import runtime


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


launcher = module('local_launcher', LOCAL / 'run.py')
delivery = module('local_delivery', LOCAL / 'delivery.py')
key_check = module('local_key_check', LOCAL / 'api_check.py')
pilot = module('local_pilot', LOCAL / 'pilot.py')
from trustgate.planning import read_plan
from trustgate.delivery import PUBLIC_FIELDS, export_delivery


class FakeExperiment:
    fail_at = None

    def __init__(self, cfg, out, suite, detector, key):
        self.rows, self.out = [], out

    async def start(self, stack):
        pass

    def completion(self, *args):
        return {}, {'usage': {'cost': 0.0001}}

    async def run_case(self, case, index):
        self.completion([], [], self.out, index)
        row = dict(case, status='completed', native_utility=True, attacker_success=False,
                   safe_completion=True, seconds=1.0, api_calls=1, cost_usd=0.0001,
                   error={'type': 'HTTPError', 'message': 'fixture'} if index == self.fail_at else None)
        self.rows.append(row)
        runtime.write_json(self.out / 'results.json', self.rows)
        return row


class LocalPlatformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = read_plan(ROOT / 'assignments/formal/plan.json')

    def setUp(self):
        temporary_root = ROOT / 'runs/local-adapter-tests'
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temporary_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def provenance(self):
        return dict(execution_backend='local-linux-v1', system='Linux', release='fixture-only',
                    python='3.10.20', pbs_job_id=None, adapter_sha256=runtime.adapter_hashes(),
                    packages=self.plan['packages'])

    def execute(self, experiment=FakeExperiment, run_id='fixture'):
        # Windows scanners can hold replaced files during these very fast fixtures.
        # This suite checks runner/accounting contracts, not Linux atomic-rename IO.
        def fixture_write(path, value):
            Path(path).write_text(json.dumps(value), encoding='utf-8')
        if os.name != 'nt':
            fixture_write = runtime.write_json
        with patch.object(launcher, 'environment', self.provenance), \
             patch.object(launcher, 'write_json', fixture_write), \
             patch.object(runtime, 'write_json', fixture_write), \
             patch('trustgate.formal_manifest.detector_hashes', return_value=self.plan['detector_sha256']):
            try:
                return asyncio.run(launcher.execute(self.plan, self.root, run_id, self.root,
                                                    'fixture-not-a-credential', experiment, None, None))
            except RuntimeError as exc:
                summary = self.root / run_id / 'shard-02/worker_summary.json'
                raise RuntimeError(str(exc) + '\n' + summary.read_text(encoding='utf-8')) from exc

    def test_local_rejects_windows_python_and_pbs(self):
        with patch.object(runtime.platform, 'system', return_value='Windows'):
            with self.assertRaises(RuntimeError): runtime.require_local()
        with patch.object(runtime.platform, 'system', return_value='Linux'), \
             patch.object(runtime.platform, 'python_version', return_value='3.10.20'), \
             patch.dict(os.environ, {'PBS_JOBID': 'real-pbs-fixture'}):
            with self.assertRaises(RuntimeError): runtime.require_local()

    def test_explicit_launch_required(self):
        result = subprocess.run([sys.executable, str(LOCAL / 'run.py'), '--detector-dir', str(self.root)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Choose exactly one', result.stderr)

    def test_paid_pilot_is_bounded_and_excludes_formal_tasks(self):
        development = read_plan(ROOT / 'configs/development/readiness-plan.json')
        bounded = pilot.build_plan(development, self.plan)
        self.assertEqual(bounded['planned_cases'], 4)
        self.assertEqual(bounded['budget_usd'], 0.20)
        self.assertEqual(bounded['shards'][2]['budget_usd'], 0.20)
        self.assertEqual(sum(len(s['cases']) for s in bounded['shards']), 4)
        self.assertTrue(all(c['split'] == 'development' and c['task'] not in self.plan['config']['formal_tasks']
                            for c in bounded['shards'][2]['cases']))

    def test_key_probe_reads_metadata_without_generation_or_secret_output(self):
        requests = []
        def opener(request, timeout):
            requests.append(request)
            return io.StringIO(json.dumps({'data': {'limit_remaining': None}}))
        report = key_check.probe('fixture-not-a-real-key', opener)
        self.assertEqual(requests[0].full_url, 'https://openrouter.ai/api/v1/key')
        self.assertEqual(requests[0].get_method(), 'GET')
        self.assertEqual(report['model_generation_requests'], 0)
        self.assertNotIn('fixture-not-a-real-key', json.dumps(report))

    def test_key_probe_rejects_exhausted_or_missing_metadata(self):
        for data in ({}, {'limit_remaining': 0}, {'limit_remaining': -1}):
            with self.assertRaises(RuntimeError):
                key_check.probe('fixture-not-a-real-key', lambda *args, **kwargs: io.StringIO(json.dumps({'data': data})))

    def test_mcp_start_uses_original_servers_without_pbs(self):
        params_seen = []
        class Base:
            def completion(self): pass
            def run_case(self): pass
        class Parameters:
            def __init__(self, **kwargs): params_seen.append(kwargs)
        @contextlib.asynccontextmanager
        async def stdio(params, errlog):
            yield ('read', 'write')
        class Session:
            def __init__(self, *streams): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def initialize(self):
                return types.SimpleNamespace(model_dump=lambda **kwargs: {'fixture': True})
        fake_engine = types.ModuleType('trustgate.formal_engine')
        fake_engine.FormalExperiment = Base
        fake_mcp = types.ModuleType('mcp')
        fake_mcp.ClientSession, fake_mcp.StdioServerParameters = Session, Parameters
        fake_stdio = types.ModuleType('mcp.client.stdio')
        fake_stdio.stdio_client = stdio
        with patch.dict(sys.modules, {'trustgate.formal_engine': fake_engine,
                                     'mcp': fake_mcp, 'mcp.client.stdio': fake_stdio}):
            local = launcher.experiment_class()
            self.assertIs(local.completion, Base.completion)
            self.assertIs(local.run_case, Base.run_case)
            instance = local()
            instance.out, instance.control, instance.clients = self.root, self.root / 'control.json', {}
            async def scenario():
                async with contextlib.AsyncExitStack() as stack:
                    await instance.start(stack)
            asyncio.run(scenario())
        self.assertEqual(set(instance.clients), {'calendar', 'mail', 'drive'})
        for params in params_seen:
            self.assertNotIn('PBS_JOBID', params['env'])
            self.assertEqual(params['command'], sys.executable)
            self.assertEqual(params['args'][0], str(ROOT / 'experiments/mvp/mcp_workspace_server.py'))

    def test_source_verification_rejects_new_or_changed_files(self):
        (self.root / 'trustgate').mkdir()
        (self.root / 'experiments/mvp').mkdir(parents=True)
        source = self.root / 'trustgate/a.py'
        source.write_bytes(b'pass\n')
        plan = {'source_sha256': {'trustgate/a.py': runtime.sha(source)}}
        with patch.object(runtime, 'ROOT', self.root):
            self.assertEqual(runtime.source_check(plan), plan['source_sha256'])
            source.write_bytes(b'pass\r\n')
            with self.assertRaises(RuntimeError): runtime.source_check(plan)

    def test_frozen_git_sources_still_match_published_manifest(self):
        import hashlib
        for path, expected in self.plan['source_sha256'].items():
            data = subprocess.check_output(['git', 'show', 'HEAD:' + path], cwd=ROOT)
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected, path)

    def test_full_person3_runner_and_original_export(self):
        worker = self.execute()
        summary = json.loads((worker / 'worker_summary.json').read_text())
        self.assertTrue(summary['complete'])
        self.assertEqual(summary['recorded'], 336)
        self.assertAlmostEqual(summary['budget']['reported_cost_usd'], 0.0336)
        destination = self.root / 'person-03'
        delivery.export_local(ROOT / 'assignments/formal/plan.json', worker, destination)
        self.assertNotIn(b'\r\n', (destination / 'results.csv').read_bytes())
        self.assertNotIn(b'\r\n', (destination / 'receipt.json').read_bytes())
        (destination / 'ENVIRONMENT.md').write_text('Synthetic offline fixture only.')
        self.assertTrue(delivery.validate(self.plan, destination, runtime.adapter_hashes())['checked'])
        with self.assertRaises(FileExistsError): self.execute()

    def test_failure_kept_and_original_export_refuses_incomplete(self):
        class Broken(FakeExperiment): fail_at = 2
        with self.assertRaises(RuntimeError): self.execute(Broken)
        worker = self.root / 'fixture/shard-02'
        summary = json.loads((worker / 'worker_summary.json').read_text())
        self.assertFalse(summary['complete'])
        self.assertEqual(summary['recorded'], 2)
        with self.assertRaises(ValueError):
            export_delivery(ROOT / 'assignments/formal/plan.json', worker, self.root / 'invalid')

    def test_unknown_charge_stops_without_retry(self):
        class UnknownCost(FakeExperiment):
            def completion(self, *args):
                return {}, {'usage': {'cost': None}}
        with self.assertRaises(RuntimeError): self.execute(UnknownCost)
        summary = json.loads((self.root / 'fixture/shard-02/worker_summary.json').read_text())
        self.assertFalse(summary['complete'])
        self.assertEqual(summary['recorded'], 0)
        self.assertTrue(summary['budget']['halted'])
        self.assertEqual(summary['budget']['uncertain_reserved_usd'], 0.05)

    def fixture_delivery(self, shard):
        folder = self.root / ('person-%02d' % (shard['index'] + 1))
        folder.mkdir()
        rows = []
        for case in shard['cases']:
            row = {k: 0 for k in PUBLIC_FIELDS}
            row.update(case, status='completed', native_utility=True, attacker_success=False,
                       safe_completion=True, seconds=1, api_calls=1, cost_usd=0, error_type=None)
            rows.append(row)
        with (folder / 'results.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=[*PUBLIC_FIELDS, 'error_type'], extrasaction='ignore')
            writer.writeheader(); writer.writerows(rows)
        from trustgate.budget import Budget
        receipt = dict(plan_sha256=self.plan['plan_sha256'], source_sha256=self.plan['source_sha256'],
                       packages=self.plan['packages'], shard_index=shard['index'], person=shard['index'] + 1,
                       recorded=336, complete=True, budget=Budget(2).snapshot())
        runtime.write_json(folder / 'receipt.json', receipt)
        (folder / 'ENVIRONMENT.md').write_text('Synthetic fixture, not an actual PBS run.')
        return folder

    def test_audit_rejects_incomplete_foreign_identity_packages_and_cost(self):
        folder = self.fixture_delivery(self.plan['shards'][2])
        self.assertTrue(delivery.validate(self.plan, folder)['checked'])
        receipt_path = folder / 'receipt.json'
        original = json.loads(receipt_path.read_text())
        for mutation in ({'complete': False}, {'recorded': 335}, {'shard_index': 1, 'person': 2},
                         {'packages': {}}, {'budget': {}}):
            runtime.write_json(receipt_path, dict(original, **mutation))
            with self.assertRaises(ValueError): delivery.validate(self.plan, folder)
        runtime.write_json(receipt_path, original)
        text = (folder / 'results.csv').read_text()
        (folder / 'results.csv').write_text(text.replace('completed', 'completed', 1).replace('W', 'BAD', 1))
        with self.assertRaises(ValueError): delivery.validate(self.plan, folder)

    def test_local_sidecar_requires_review_and_binds_csv(self):
        worker = self.execute()
        folder = self.root / 'person-03'
        delivery.export_local(ROOT / 'assignments/formal/plan.json', worker, folder)
        (folder / 'ENVIRONMENT.md').write_text('Synthetic fixture.')
        with self.assertRaises(ValueError): delivery.validate(self.plan, folder)
        with self.assertRaises(ValueError): delivery.validate(self.plan, folder, {})
        with (folder / 'results.csv').open('a') as stream: stream.write('\n')
        with self.assertRaises(ValueError): delivery.validate(self.plan, folder, runtime.adapter_hashes())

    def test_original_five_delivery_summary_accepts_format(self):
        for shard in self.plan['shards']:
            if shard['index'] != 2:
                self.fixture_delivery(shard)
        worker = self.execute()
        local_folder = self.root / 'person-03'
        delivery.export_local(ROOT / 'assignments/formal/plan.json', worker, local_folder)
        (local_folder / 'ENVIRONMENT.md').write_text('Synthetic fixture.')
        self.assertTrue(delivery.validate(self.plan, local_folder, runtime.adapter_hashes())['checked'])
        output = self.root / 'summary.json'
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/formal/summarize.py'),
            '--plan', str(ROOT / 'assignments/formal/plan.json'), '--deliveries', str(self.root),
            '--output', str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(output.read_text())
        self.assertTrue(summary['complete'])
        self.assertEqual(summary['recorded'], 1680)


if __name__ == '__main__': unittest.main()
