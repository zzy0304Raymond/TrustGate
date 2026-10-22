import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path

import release_integrity

ROOT = Path(__file__).resolve().parents[1]


class EnglishReleaseTests(unittest.TestCase):
    def test_every_approved_revision_matches_its_current_bytes(self):
        self.assertGreater(release_integrity.verify_release(), 0)

    def test_modified_translation_does_not_inherit_original_identity(self):
        manifest = json.loads(release_integrity.MANIFEST.read_text())
        record = next(r for r in manifest['files'] if r['path'] == 'trustgate/planning.py')
        data = (ROOT / record['path']).read_bytes()
        self.assertEqual(release_integrity.recorded_digest(hashlib.sha256(data).hexdigest()), record['original_sha256'])
        changed = hashlib.sha256(data + b'\n# unlisted change\n').hexdigest()
        self.assertEqual(release_integrity.recorded_digest(changed), changed)
        self.assertNotEqual(changed, record['original_sha256'])

    def test_formal_measurements_and_frozen_manifests_are_not_translated(self):
        data = json.loads(release_integrity.MANIFEST.read_text())
        required = {'assignments/formal/plan.json', 'assignments/transport_validation/plan.json'}
        required.update(f'experiments/deliveries/person-{i:02}/results.csv' for i in range(1, 6))
        self.assertTrue(required <= set(data['unchanged_measurements']))
        changed = {r['path'] for r in data['files']}
        self.assertFalse(required & changed)

    def test_tracked_text_and_decoded_json_contain_no_han_characters(self):
        han = re.compile('[\u3400-\u9fff\uf900-\ufaff]')
        names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
        for name in filter(None, names):
            path = ROOT / name
            try:
                text = path.read_bytes().decode('utf-8')
            except UnicodeDecodeError:
                continue
            with self.subTest(path=name):
                self.assertIsNone(han.search(text))
                if path.suffix == '.json':
                    decoded = json.dumps(json.loads(text), ensure_ascii=False)
                    self.assertIsNone(han.search(decoded))

    def test_demo_declares_english(self):
        page = (ROOT / 'demos/index.html').read_text()
        self.assertIn('<html lang="en">', page)


if __name__ == '__main__':
    unittest.main()
