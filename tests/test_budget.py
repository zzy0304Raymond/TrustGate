import unittest
from trustgate.budget import Budget, BudgetExceeded

class BudgetTests(unittest.TestCase):
    def test_success_releases_unused_reservation(self):
        b = Budget(0.1, 0.05); b.reserve(); b.reconcile(0.01)
        self.assertAlmostEqual(b.reported, 0.01); self.assertEqual(b.pending, 0)
        b.reserve(); b.reconcile(0.02)
        self.assertAlmostEqual(b.reported, 0.03)

    def test_cannot_start_without_sufficient_reserve(self):
        b = Budget(0.06, 0.05); b.reserve(); b.reconcile(0.03)
        with self.assertRaises(BudgetExceeded): b.reserve()

    def test_unknown_charge_halts_and_preserves_reserve(self):
        b = Budget(1); b.reserve(); b.unknown()
        self.assertEqual(b.uncertain, 0.05)
        with self.assertRaises(BudgetExceeded): b.reserve()

    def test_missing_or_invalid_cost_halts(self):
        for cost in (None, float('nan'), -1, True):
            b = Budget(1); b.reserve()
            with self.assertRaises(BudgetExceeded): b.reconcile(cost)
            self.assertTrue(b.halted)

    def test_excessive_cost_is_recorded_then_halts(self):
        b = Budget(1); b.reserve()
        with self.assertRaises(BudgetExceeded): b.reconcile(0.06)
        self.assertEqual(b.reported, 0.06)
        self.assertTrue(b.halted)
