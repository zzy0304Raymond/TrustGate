"""Five concurrent runner instances with mocked LLM/MCP, never live API calls."""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from trustgate.planning import ROOT, build_plan
from trustgate.runner import run_shard
from trustgate.merge import merge_results
sys.path.insert(0, str(ROOT/'experiments/mvp'))
import run_matrix_v2

class RunnerIsolationTests(unittest.TestCase):
    def test_five_shards_keep_independent_state_and_accounting(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            plan = build_plan(json.loads((ROOT/'configs/mvp/pilot.json').read_text()))
            plan_path = root/'plan.json'; plan_path.write_text(json.dumps(plan))
            detector = root/'detector'; detector.mkdir(); (detector/'model.safetensors').touch()
            state_paths = set()
            async def start(self, stack):
                state_paths.add(str(self.state))
                await asyncio.sleep(0)
            def completion(self, messages, tools, folder, step):
                return {'content':'fixture'}, {'usage':{'cost':0.001}}
            async def run_case(self, case, index):
                trial = self.out/('fixture-%03d' % index); trial.mkdir()
                self.completion([], [], trial, 1)
                row = dict(case, index=index, status='completed', error=None, native_utility=True,
                           attacker_success=False if case['surface']!='benign' else None,
                           safe_completion=case['surface']!='benign', seconds=0, api_calls=1,
                           cost_usd=0.001, result_dir=str(trial))
                self.rows.append(row)
                (self.out/'results.json').write_text(json.dumps(self.rows))
                await asyncio.sleep(0)
                return row
            async def scenario():
                return await asyncio.gather(*(run_shard(plan_path, i, 'fixture-only', root, detector) for i in range(5)))
            with patch.dict(os.environ, {'OPENROUTER_API_KEY':'test-no-network-credential',
                                         'PBS_JOBID':'offline-fixture-not-a-real-job'}), \
                 patch('trustgate.runner.require_compute'), \
                 patch('trustgate.runner.sys.flags') as flags, \
                 patch.object(run_matrix_v2.Experiment, 'start', start), \
                 patch.object(run_matrix_v2.Experiment, 'completion', completion), \
                 patch.object(run_matrix_v2.Experiment, 'run_case', run_case), \
                 patch.object(run_matrix_v2, 'Detector', return_value=object()):
                flags.hash_randomization = 0
                paths = asyncio.run(scenario())
            self.assertEqual(len(set(paths)), 5)
            self.assertEqual(len(state_paths), 5)
            merged = merge_results(plan_path, root/'fixture-only')
            self.assertTrue(merged['complete'])
            self.assertTrue(merged['cost_accounting_complete'])
            self.assertEqual(merged['recorded'], 81)
            self.assertAlmostEqual(merged['reported_cost_usd'], 0.081)
