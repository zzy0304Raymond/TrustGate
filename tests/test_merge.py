import json
import tempfile
import unittest
from pathlib import Path
from trustgate.planning import ROOT, build_plan
from trustgate.merge import merge_results

class MergeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan = build_plan(json.loads((ROOT/'configs/mvp/pilot.json').read_text()))
        self.path = self.root/'plan.json'; self.path.write_text(json.dumps(self.plan))
        for shard in self.plan['shards']:
            folder = self.root/('shard-%02d' % shard['index']); folder.mkdir()
            (folder/'manifest.json').write_text(json.dumps(dict(plan_sha256=self.plan['plan_sha256'], shard_index=shard['index'],source_sha256={'fixture':'frozen'})))
            (folder/'worker_summary.json').write_text('{}')
            rows = [dict(c, status='completed', native_utility=True, attacker_success=False if c['surface']!='benign' else None,
                         safe_completion=c['surface']!='benign', seconds=1, api_calls=1, cost_usd=0.001, result_dir='fixture') for c in shard['cases']]
            (folder/'results.json').write_text(json.dumps(rows))

    def test_exact_coverage(self):
        result = merge_results(self.path, self.root)
        self.assertTrue(result['complete']); self.assertEqual(result['recorded'], 81)
        self.assertAlmostEqual(result['reported_cost_usd'], 0.081)

    def test_missing_worker_rejected_or_explicitly_partial(self):
        (self.root/'shard-00/manifest.json').unlink()
        with self.assertRaises(ValueError): merge_results(self.path, self.root)
        result = merge_results(self.path, self.root, allow_partial=True)
        self.assertFalse(result['complete']); self.assertTrue(result['missing_case_ids'])

    def test_duplicate_result_rejected(self):
        path = self.root/'shard-00/results.json'; rows = json.loads(path.read_text())
        rows.append(rows[0]); path.write_text(json.dumps(rows))
        with self.assertRaises(ValueError): merge_results(self.path, self.root)

    def test_identity_mutation_rejected(self):
        path = self.root/'shard-00/results.json'; rows = json.loads(path.read_text())
        rows[0]['task'] = 'user_task_999'; path.write_text(json.dumps(rows))
        with self.assertRaises(ValueError): merge_results(self.path, self.root)

    def test_running_worker_not_complete(self):
        (self.root/'shard-00/worker_summary.json').unlink()
        with self.assertRaises(ValueError): merge_results(self.path, self.root)

    def test_mixed_code_versions_rejected(self):
        path = self.root/'shard-01/manifest.json'; manifest = json.loads(path.read_text())
        manifest['source_sha256'] = {'fixture':'changed'}; path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError): merge_results(self.path, self.root)
