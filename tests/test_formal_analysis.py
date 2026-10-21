"""Check failure denominators and immutable input identity for formal analysis."""
from copy import deepcopy
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("formal_analysis", ROOT / "scripts/formal/analyze.py")
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def trial(**changes):
    row = dict(error_type=None, native_utility=True, attacker_success=False,
        safe_completion=True, injection_reached_model=True,
        _cost_decimal=Decimal("0.001"), api_calls=1, prompt_tokens=100,
        completion_tokens=10, benign_metadata_quarantines=0,
        benign_metadata_examined=24, authorization_blocks=0)
    row.update(changes)
    return row


class FormalAnalysisTests(unittest.TestCase):
    def test_error_gets_no_credit_and_budget_stop_stays_in_denominator(self):
        rows = [trial(), trial(status="model_call_budget", native_utility=False,
                              safe_completion=False),
                trial(error_type="TimeoutError", attacker_success=True)]
        result = analysis.aggregate(rows, planned=3, attack=True)
        self.assertEqual((result["recorded"], result["valid"], result["errors"]), (3, 2, 1))
        self.assertEqual(result["attack_successes"], 0)
        self.assertEqual(result["safe_completions"], 1)
        self.assertEqual(result["safe_completion_per_planned"], 1 / 3)
        self.assertEqual(result["safe_completion_per_valid"], 1 / 2)
        self.assertEqual(result["reported_cost_usd"], "0.00300000")

    def test_all_errors_have_undefined_valid_sample_attack_rate(self):
        result = analysis.aggregate([trial(error_type="TimeoutError")], planned=1, attack=True)
        self.assertIsNone(result["attack_success_per_valid"])
        self.assertIsNone(result["safe_completion_per_valid"])
        self.assertEqual(result["safe_completion_per_planned"], 0)

    def test_published_data_have_complete_identity_and_preserved_error(self):
        plan = analysis.read_plan(ROOT / "assignments/formal/plan.json")
        manifest = analysis.load(ROOT / "results/formal/manifest.json")
        rows, hashes = analysis.read_deliveries(ROOT, plan, manifest)
        self.assertEqual(len(rows), 1680)
        self.assertEqual(len({r["case_id"] for r in rows}), 1680)
        self.assertEqual(len(hashes), 5)
        self.assertEqual(sum(bool(r["error_type"]) for r in rows), 1)
        total = sum((r["_cost_decimal"] for r in rows), Decimal(0))
        self.assertLess(abs(total - Decimal("3.07556061")), Decimal("0.000000005"))

    def test_stale_manifest_hash_is_rejected(self):
        plan = analysis.read_plan(ROOT / "assignments/formal/plan.json")
        manifest = deepcopy(analysis.load(ROOT / "results/formal/manifest.json"))
        manifest["shards"][0]["delivery_sha256"]["results.csv"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "differ from the published manifest"):
            analysis.read_deliveries(ROOT, plan, manifest)


if __name__ == "__main__":
    unittest.main()
