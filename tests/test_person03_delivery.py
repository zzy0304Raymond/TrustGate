"""Regression checks for owner-approved cost estimates and immutable measurements."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('person03_final_audit', ROOT / 'tasks/03/audit_delivery.py')
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


@unittest.skipIf(os.name == 'nt', 'Exact frozen runtime bytes are audited in Linux/WSL')
class FinalDeliveryTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'runs/final-delivery-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'person-03'
        shutil.copytree(ROOT / 'experiments/deliveries/person-03', self.folder)

    def mutate_json(self, name, change):
        path = self.folder / name
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value))

    def test_estimates_keep_reported_costs_and_original_failure(self):
        result = audit_module.audit(self.folder, True)
        self.assertTrue(result['passed'])
        self.assertTrue(result['accounting_finalized'])
        self.assertEqual(result['formal_cost_rounded_usd'], .51)
        self.assertTrue(result['retained_timeout'])

    def test_explicit_acceptance_required(self):
        with self.assertRaises(ValueError):
            audit_module.audit(self.folder)

    def test_new_reservation_not_covered_by_final_accounting(self):
        for amount in (.05, .10):
            self.mutate_json('receipt.json', lambda x: x['budget'].update(uncertain_reserved_usd=amount))
            with self.assertRaises(ValueError):
                audit_module.audit(self.folder, True)

    def test_estimate_cannot_be_relabelled_as_provider_invoice(self):
        self.mutate_json('ACCOUNTING.json', lambda x: x.update(estimates_are_provider_invoices=True))
        with self.assertRaises(ValueError):
            audit_module.audit(self.folder, True)

    def test_modified_measurement_rejected(self):
        path = self.folder / 'results.csv'
        text = path.read_text()
        path.write_text(text.replace('TimeoutError', '', 1))
        with self.assertRaises(ValueError):
            audit_module.audit(self.folder, True)

    def test_original_generic_audit_accepts_final_format(self):
        import delivery
        from trustgate.planning import read_plan
        plan = read_plan(ROOT / 'assignments/formal/plan.json')
        self.assertTrue(delivery.validate(plan, self.folder, audit_module.runtime.adapter_hashes())['checked'])


if __name__ == '__main__':
    unittest.main()
