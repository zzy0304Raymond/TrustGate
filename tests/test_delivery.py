import copy
import json
import tempfile
import unittest
from pathlib import Path
from trustgate.planning import ROOT,read_plan
from trustgate.delivery import export_delivery

class DeliveryTests(unittest.TestCase):
    def test_private_fields_never_export_and_duplicates_rejected(self):
        plan=read_plan(ROOT/'assignments/formal/plan.json');shard=plan['shards'][0]
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);worker=root/'worker';worker.mkdir()
            (worker/'manifest.json').write_text(json.dumps({'plan_sha256':plan['plan_sha256'],'source_sha256':plan['source_sha256'],'shard_index':0,'packages':{}}))
            (worker/'worker_summary.json').write_text(json.dumps({'complete':True,'fatal_error':None,'budget':{},'wall_seconds':1}))
            rows=[dict(c,final_answer='PRIVATE_MARKER',result_dir='/private/path',error={'type':'ToolError','message':'PRIVATE_MARKER'}) for c in shard['cases']]
            (worker/'results.json').write_text(json.dumps(rows))
            result=export_delivery(ROOT/'assignments/formal/plan.json',worker,root/'public')
            self.assertEqual(result['recorded'],336)
            public=''.join(p.read_text() for p in (root/'public').iterdir())
            self.assertNotIn('PRIVATE_MARKER',public);self.assertNotIn('/private/path',public)
            rows[-1]=copy.deepcopy(rows[0]);(worker/'results.json').write_text(json.dumps(rows))
            with self.assertRaises(ValueError):export_delivery(ROOT/'assignments/formal/plan.json',worker,root/'invalid')
