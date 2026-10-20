"""Offline recovery tests: no credentials, downloads or network calls."""
import asyncio
import contextlib
import copy
import io
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('person03_resume', ROOT / 'tasks/03/resume.py')
resume = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resume)
from trustgate.planning import read_plan


class FakeExperiment:
    calls = []
    unknown = False
    stop = False
    model_mismatch = False

    def __init__(self, cfg, out, suite, detector, key):
        self.cfg, self.out, self.rows = cfg, out, []

    async def start(self, stack):
        pass

    def completion(self, messages, tools, folder, step):
        self.calls.append(step)
        cost = None if self.unknown else .0001
        model = 'wrong-model' if self.model_mismatch else self.cfg['model']
        request = dict(model=self.cfg['model'], provider={'order': [self.cfg['provider']],
            'allow_fallbacks': False, 'require_parameters': True},
            temperature=self.cfg['temperature'], max_tokens=self.cfg['max_output_tokens'])
        answer = dict(usage={'cost': cost}, model=model, provider=self.cfg['provider'])
        resume.durable(folder / 'request_01.json', request)
        resume.durable(folder / 'response_01.json', answer)
        return {}, answer

    async def run_case(self, case, index):
        folder = self.out / ('%03d_fixture' % index)
        folder.mkdir()
        self.completion([], [], folder, index)
        row = dict(case, index=index, status='completed', native_utility=True,
            attacker_success=False, safe_completion=True, api_calls=1, cost_usd=.0001,
            seconds=1, error=None, result_dir=str(folder))
        self.rows.append(row)
        resume.durable(self.out / 'results.json', self.rows)
        if self.stop:
            resume.STOP = True
        return row


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.plan = read_plan(ROOT / 'assignments/formal/plan.json')
        base = ROOT / 'runs/recovery-tests'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'old/shard-02'
        self.source.mkdir(parents=True)
        self.platform = dict(execution_backend='local-linux-v1', system='Linux', release='fixture',
            python='3.10.20', pbs_job_id=None, packages=self.plan['packages'],
            adapter_sha256=resume.runtime.adapter_hashes(), detector_sha256=self.plan['detector_sha256'])
        manifest = dict(run_id='fixture', shard_index=2, plan_sha256=self.plan['plan_sha256'],
            source_sha256=self.plan['source_sha256'], packages=self.plan['packages'],
            platform=self.platform)
        cfg = self.plan['config']
        fake = FakeExperiment(cfg, self.source, None, None, '')
        FakeExperiment.calls = []
        FakeExperiment.unknown = FakeExperiment.stop = FakeExperiment.model_mismatch = False
        resume.STOP = False
        for i, case in enumerate(self.plan['shards'][2]['cases'][:18], 1):
            asyncio.run(fake.run_case(case, i))
        # A valid model failure remains part of the preserved prefix.
        fake.rows[0].update(status='model_call_budget', native_utility=False)
        resume.durable(self.source / 'results.json', fake.rows)
        budget = resume.Budget(2).snapshot()
        budget['reported_cost_usd'] = sum(r['cost_usd'] for r in fake.rows)
        for n, value in [('manifest.json', manifest), ('plan.json', self.plan), ('budget.json', budget)]:
            resume.durable(self.source / n, value)
        self.rows = copy.deepcopy(fake.rows)
        self.checkpoint = dict(status='paused_by_user', plan_sha256=self.plan['plan_sha256'],
            source_sha256=self.plan['source_sha256'], adapter_sha256=resume.runtime.adapter_hashes(),
            results_sha256=resume.runtime.sha(self.source / 'results.json'), budget=budget,
            completed_count=18, remaining_count=318, interrupted_case_requests=0,
            completed_case_ids=[r['case_id'] for r in fake.rows],
            remaining_case_ids=[c['case_id'] for c in self.plan['shards'][2]['cases'][18:]])
        resume.durable(self.source / 'PAUSE_CHECKPOINT.json', self.checkpoint)
        self.bound = resume.build_bound(self.plan, self.source, 'fixture-resume')
        FakeExperiment.calls = []
        self.addCleanup(setattr, resume, 'STOP', False)

    def execute(self):
        with patch.object(resume.runtime, 'environment', return_value=copy.deepcopy(self.platform)), contextlib.redirect_stdout(io.StringIO()):
            return asyncio.run(resume.execute(self.plan, self.bound, self.root / 'new',
                'fixture-key', FakeExperiment, None, None))

    def test_complete_retains_failures_carries_budget_and_exports_original_format(self):
        folder = self.execute()
        self.assertEqual(FakeExperiment.calls, list(range(19, 337)))
        rows = resume.read(folder / 'results.json')
        self.assertEqual(rows[:18], self.rows)
        self.assertEqual(resume.read(self.source / 'results.json'), self.rows)
        summary = resume.read(folder / 'worker_summary.json')
        self.assertTrue(summary['complete'])
        self.assertEqual(summary['newly_recorded'], 318)
        self.assertAlmostEqual(summary['budget']['reported_cost_usd'], .0336)
        dest = self.root / 'person-03'
        resume.export(ROOT / 'assignments/formal/plan.json', folder, dest)
        self.assertTrue(resume.audit(self.plan, dest, resume.runtime.sha(resume.__file__))['passed'])
        with self.assertRaises(ValueError):
            resume.audit(self.plan, dest, 'unreviewed')
        with self.assertRaises(FileExistsError):
            self.execute()
        self.assertEqual(len(FakeExperiment.calls), 318)

    def test_result_or_budget_tamper_rejected_before_calls(self):
        for name in ('results.json', 'budget.json'):
            path = self.source / name
            original = path.read_bytes()
            path.write_bytes(original + b' ' if name == 'results.json' else b'{}')
            with self.assertRaises((ValueError, KeyError)):
                self.execute()
            path.write_bytes(original)
        self.assertEqual(FakeExperiment.calls, [])

    def test_unrecorded_request_refuses_resume(self):
        folder = self.source / '019_interrupted'
        folder.mkdir()
        (folder / 'request_01.json').write_text('{}')
        with self.assertRaises(ValueError):
            self.execute()
        self.assertEqual(FakeExperiment.calls, [])

    def test_unknown_charge_stops_and_is_not_retried(self):
        FakeExperiment.unknown = True
        with self.assertRaises(RuntimeError):
            self.execute()
        summary = resume.read(self.root / 'new/fixture-resume/shard-02/worker_summary.json')
        self.assertFalse(summary['complete'])
        self.assertEqual(summary['budget']['uncertain_reserved_usd'], .05)
        self.assertEqual(FakeExperiment.calls, [19])
        with self.assertRaises(FileExistsError):
            self.execute()

    def test_model_mismatch_keeps_charge_and_stops(self):
        FakeExperiment.model_mismatch = True
        with self.assertRaises(RuntimeError):
            self.execute()
        summary = resume.read(self.root / 'new/fixture-resume/shard-02/worker_summary.json')
        self.assertFalse(summary['complete'])
        self.assertAlmostEqual(summary['budget']['reported_cost_usd'], .0019)
        self.assertEqual(FakeExperiment.calls, [19])

    def test_graceful_pause_has_durable_valid_checkpoint(self):
        FakeExperiment.stop = True
        folder = self.execute()
        summary = resume.read(folder / 'worker_summary.json')
        self.assertTrue(summary['paused'])
        self.assertFalse(summary['complete'])
        self.assertEqual(summary['recorded'], 19)
        self.assertEqual(FakeExperiment.calls, [19])
        next_bound = resume.build_bound(self.plan, folder, 'fixture-resume-02')
        self.assertEqual(len(next_bound['remaining_case_ids']), 317)
        with self.assertRaises(ValueError):
            resume.export(ROOT / 'assignments/formal/plan.json', folder, self.root / 'invalid')

    def test_changed_selection_or_code_pin_rejected(self):
        for field, value in [('remaining_case_ids', []), ('recovery_entrypoint_sha256', 'wrong')]:
            changed = copy.deepcopy(self.bound)
            changed[field] = value
            changed['recovery_sha256'] = resume.digest({k:v for k,v in changed.items() if k != 'recovery_sha256'})
            with self.assertRaises(ValueError):
                resume.verify_bound(self.plan, changed)

    def test_reservation_includes_previous_cost(self):
        # Retain a consistent high-cost prefix, then ensure reservation stops before API access.
        for row in self.rows:
            row['cost_usd'] = 1.98/18
            response = Path(row['result_dir']) / 'response_01.json'
            value = resume.read(response)
            value['usage']['cost'] = row['cost_usd']
            resume.durable(response, value)
        resume.durable(self.source / 'results.json', self.rows)
        budget = copy.deepcopy(self.checkpoint['budget'])
        budget['reported_cost_usd'] = sum(r['cost_usd'] for r in self.rows)
        resume.durable(self.source / 'budget.json', budget)
        self.checkpoint.update(budget=budget, results_sha256=resume.runtime.sha(self.source / 'results.json'))
        resume.durable(self.source / 'PAUSE_CHECKPOINT.json', self.checkpoint)
        self.bound = resume.build_bound(self.plan, self.source, 'fixture-resume')
        with self.assertRaises(RuntimeError):
            self.execute()
        self.assertEqual(FakeExperiment.calls, [])

    def make_recorded_timeout(self):
        last = self.rows[-1]
        last.update(status='error', error={'type':'TimeoutError','message':'offline fixture'})
        folder = Path(last['result_dir'])
        (folder / 'request_02.json').write_bytes((folder / 'request_01.json').read_bytes())
        resume.durable(self.source / 'results.json', self.rows)
        budget = copy.deepcopy(self.checkpoint['budget'])
        budget.update(uncertain_reserved_usd=.05, halted=True)
        resume.durable(self.source / 'budget.json', budget)
        resume.durable(self.source / 'worker_summary.json', dict(recorded=18, complete=False,
            fatal_error={'type':'TimeoutError'}, budget=budget))
        resume.durable(self.source / 'recovery.json', self.bound)
        (self.source / 'recovery_source.py').write_bytes(Path(resume.__file__).read_bytes())
        manifest = resume.read(self.source / 'manifest.json')
        manifest['recovery_sha256'] = self.bound['recovery_sha256']
        resume.durable(self.source / 'manifest.json', manifest)
        (self.source / 'PAUSE_CHECKPOINT.json').unlink()

    def test_timeout_requires_explicit_manifest_authorization(self):
        self.make_recorded_timeout()
        with self.assertRaises(ValueError):
            resume.build_bound(self.plan, self.source, 'next')

    def test_authorized_timeout_kept_budget_reserved_and_final_export_blocked(self):
        self.make_recorded_timeout()
        self.bound = resume.build_bound(self.plan, self.source, 'next', allow_recorded_timeout=True)
        self.assertAlmostEqual(self.bound['remaining_budget_usd'], 2-.0018-.05)
        self.assertEqual(len(self.bound['unresolved_requests']), 1)
        folder = self.execute()
        summary = resume.read(folder / 'worker_summary.json')
        self.assertTrue(summary['complete'])
        self.assertFalse(summary['delivery_ready'])
        self.assertFalse(summary['cost_reconciled'])
        self.assertEqual(summary['budget']['uncertain_reserved_usd'], .05)
        self.assertEqual(FakeExperiment.calls, list(range(19,337)))
        self.assertEqual(resume.read(folder / 'results.json')[:18], self.rows)
        with self.assertRaises(ValueError):
            resume.export(ROOT / 'assignments/formal/plan.json', folder, self.root / 'blocked')

    def test_unmatched_request_reservation_cannot_be_erased(self):
        self.make_recorded_timeout()
        budget = resume.read(self.source / 'budget.json')
        budget['uncertain_reserved_usd'] = 0
        resume.durable(self.source / 'budget.json', budget)
        summary = resume.read(self.source / 'worker_summary.json')
        summary['budget'] = budget
        resume.durable(self.source / 'worker_summary.json', summary)
        with self.assertRaises(ValueError):
            resume.build_bound(self.plan, self.source, 'next', allow_recorded_timeout=True)

    def test_new_unknown_cost_still_stops_despite_prior_authorization(self):
        self.make_recorded_timeout()
        self.bound = resume.build_bound(self.plan, self.source, 'next', allow_recorded_timeout=True)
        FakeExperiment.unknown = True
        with self.assertRaises(RuntimeError):
            self.execute()
        summary = resume.read(self.root / 'new/next/shard-02/worker_summary.json')
        self.assertFalse(summary['complete'])
        self.assertAlmostEqual(summary['budget']['uncertain_reserved_usd'], .10)
        self.assertEqual(FakeExperiment.calls, [19])


if __name__ == '__main__':
    unittest.main()
