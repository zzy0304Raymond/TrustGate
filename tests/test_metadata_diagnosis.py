"""Ensure partial public evidence is not promoted to full-request verification."""
import copy
import csv
import json
import unittest
from unittest.mock import patch

from scripts.formal import analyze_metadata_diagnosis as diagnosis


class PublicEvidenceScopeTests(unittest.TestCase):
    def evidence(self, person, case_id):
        path = diagnosis.ROOT / f'review-data/person-{person:02}/{case_id}/evidence.json'
        with (diagnosis.ROOT / f'experiments/deliveries/person-{person:02}/results.csv').open() as stream:
            row = next(r for r in csv.DictReader(stream) if r['case_id'] == case_id)
        plan = json.loads((diagnosis.ROOT / 'assignments/formal/plan.json').read_text())
        return path, plan['config']['formal_attacks'][row['attack_case_id']], row

    def test_first_request_description_does_not_prove_later_requests(self):
        path, attack, row = self.evidence(4, 'b4cde1d7545d383cd4db')
        result = diagnosis.public_detail(path, attack, row)
        self.assertEqual(result['request_evidence'], 'public_full_description_first_request')
        self.assertEqual(result['requests_with_payload_evidence'], 1)
        self.assertGreater(result['requests_available'], 1)

    def test_marker_projection_is_not_a_full_payload_check(self):
        path, attack, row = self.evidence(5, '53c10b651eeb19f9abc2')
        result = diagnosis.public_detail(path, attack, row)
        self.assertEqual(result['request_evidence'], 'public_marker_flags_all_requests')
        self.assertEqual(result['recomputed_attack_success'], '')

    def test_missing_marker_fails_exposure_assertion(self):
        path, attack, row = self.evidence(5, '53c10b651eeb19f9abc2')
        data = copy.deepcopy(diagnosis.load(path))
        data['requests'][0]['tg_inject_marker_in_tools'] = False
        with patch.object(diagnosis, 'load', return_value=data):
            with self.assertRaises(AssertionError):
                diagnosis.public_detail(path, attack, row)

    def test_truncated_description_cannot_pass_full_payload_check(self):
        path, attack, row = self.evidence(4, 'b4cde1d7545d383cd4db')
        data = copy.deepcopy(diagnosis.load(path))
        data['attack']['attacked_description_as_sent'] = 'truncated'
        with patch.object(diagnosis, 'load', return_value=data):
            with self.assertRaises(AssertionError):
                diagnosis.public_detail(path, attack, row)


if __name__ == '__main__':
    unittest.main()
