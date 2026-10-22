import copy
import unittest
from trustgate.formal_allocation import build_allocation, validate_allocation
from trustgate.planning import digest

class FormalAllocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.plan=build_allocation()

    def test_1680_trials_exactly_once(self):
        trials=[t for p in self.plan['people'] for t in p['trials']]
        self.assertEqual(len(trials),1680)
        self.assertEqual(len({t['case_id'] for t in trials}),1680)
        self.assertEqual(sum(t['surface']=='benign' for t in trials),420)
        self.assertEqual(sum(t['surface']=='output' for t in trials),630)
        self.assertEqual(sum(t['surface']=='metadata' for t in trials),630)

    def test_each_person_has_all_conditions_and_repeats(self):
        for p in self.plan['people']:
            for slot in p['case_slots']:
                runs=[t for t in p['trials'] if t['slot_id']==slot['slot_id']]
                self.assertEqual(len(runs),21)
                self.assertEqual({t['condition'] for t in runs},set(self.plan['conditions']))
                self.assertEqual({t['repeat'] for t in runs},{1,2,3})

    def test_time_balanced_and_forecast_preserved(self):
        times=[p['estimated_seconds'] for p in self.plan['people']]
        self.assertLess(max(times)/min(times),1.05)
        self.assertAlmostEqual(sum(times),57017.93495046571,places=6)

    def test_development_tasks_excluded_and_not_ready(self):
        tasks={task for p in self.plan['people'] for task in p['tasks']}
        self.assertFalse(tasks & {'user_task_1','user_task_14','user_task_26','user_task_6','user_task_29','user_task_15'})
        self.assertFalse(self.plan['ready_to_run'])
        changed=copy.deepcopy(self.plan);changed['ready_to_run']=True
        changed['plan_sha256']=digest({k:v for k,v in changed.items() if k!='plan_sha256'})
        with self.assertRaises(ValueError):validate_allocation(changed)

    def test_formal_allocation_cannot_enter_pilot_runner(self):
        from trustgate.planning import validate_plan
        with self.assertRaisesRegex(ValueError, 'Formal experiment'):
            validate_plan(self.plan)
