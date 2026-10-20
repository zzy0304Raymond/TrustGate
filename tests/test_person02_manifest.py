"""Dataset metadata must identify the exact delivery bytes and experiment plan."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('person02_delivery', ROOT / 'tasks/02/prepare_delivery.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class DatasetManifestTests(unittest.TestCase):
    def test_only_matching_manifest_and_unchanged_delivery_are_valid(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            folder = base / 'delivery'
            folder.mkdir()
            data = folder / 'receipt.json'
            data.write_text('{"recorded":336}')
            report = base / 'manifest.json'
            self.assertFalse(delivery.validated_delivery(folder, report, 'plan'))
            proof = dict(schema_version=1, plan_sha256='plan',
                shards=[dict(person=2, recorded=336,
                    delivery_sha256={'receipt.json': delivery.sha(data)})])
            report.write_text(json.dumps(proof))
            self.assertTrue(delivery.validated_delivery(folder, report, 'plan'))
            self.assertFalse(delivery.validated_delivery(folder, report, 'other-plan'))
            data.write_text('{"recorded":335}')
            with self.assertRaises(ValueError):
                delivery.validated_delivery(folder, report, 'plan')

    def test_missing_person_metadata_cannot_validate_delivery(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            report = base / 'manifest.json'
            report.write_text(json.dumps(dict(schema_version=1, plan_sha256='plan', shards=[])))
            self.assertFalse(delivery.validated_delivery(base, report, 'plan'))
