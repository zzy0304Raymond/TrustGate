import copy
import json
import unittest
from trustgate.planning import ROOT, build_plan, validate_plan, digest

class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT/'configs/mvp/pilot.json').read_text())
        self.plan = build_plan(self.config)

    def test_all_cases_once(self):
        ids = [c['case_id'] for s in self.plan['shards'] for c in s['cases']]
        self.assertEqual(len(ids), 81)
        self.assertEqual(len(set(ids)), 81)
        self.assertAlmostEqual(sum(s['budget_usd'] for s in self.plan['shards']), 1.0)
        loads = [s['estimated_seconds'] for s in self.plan['shards']]
        self.assertLess(max(loads)/min(loads), 1.3)

    def test_deterministic_without_mutating_input(self):
        original = copy.deepcopy(self.config)
        self.assertEqual(self.plan, build_plan(self.config))
        self.assertEqual(original, self.config)

    def test_modified_manifest_rejected(self):
        self.plan['shards'][0]['cases'][0]['condition'] = 'none'
        self.plan['shards'][0]['budget_usd'] += 1
        with self.assertRaises(ValueError): validate_plan(self.plan)

    def test_rehashed_duplicate_still_rejected(self):
        shard = self.plan['shards'][0]
        shard['cases'][0] = copy.deepcopy(shard['cases'][1])
        self.plan['plan_sha256'] = digest({k:v for k,v in self.plan.items() if k!='plan_sha256'})
        with self.assertRaises(ValueError): validate_plan(self.plan)

    def test_invalid_worker_count(self):
        for n in (0, 6):
            with self.assertRaises(ValueError): build_plan(self.config, workers=n)
