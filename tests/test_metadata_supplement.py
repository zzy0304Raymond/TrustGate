"""Offline regression checks for supplementary scoring and trace reconstruction."""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/supplement'))
import study
import analyze
from simulation_runtime import run_native
from agentdojo.functions_runtime import FunctionsRuntime
from agentdojo.task_suite.load_suites import get_suite


class SupplementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = get_suite('v1.2.2', 'workspace')
        cls.runtime = FunctionsRuntime(cls.suite.tools)

    def environment(self):
        return self.suite.user_tasks['user_task_14'].init_environment(self.suite.load_and_inject_default_environment({}))

    def test_live_state_restoration_does_not_lose_new_mail(self):
        before = self.environment()
        after = before.model_copy(deep=True)
        goal = study.goal_for('send_email', before, 'user_task_14')
        _, err = run_native(self.runtime, after, goal['tool'], goal['arguments'])
        self.assertFalse(err)
        restored = analyze.restore(after.model_dump(mode='json'), before)
        self.assertTrue(study.attack_success(goal, before, restored))
        self.assertEqual(len(analyze.changed_states(before, restored)[0]), 1)
        self.assertFalse(study.attack_success(goal, before, before))

    def test_exact_and_secondary_mail_metrics_are_distinct(self):
        before = self.environment()
        after = before.model_copy(deep=True)
        goal = study.goal_for('send_email', before, 'user_task_14')
        variant = copy.deepcopy(goal['arguments'])
        variant['body'] += '\n'
        _, err = run_native(self.runtime, after, goal['tool'], variant)
        self.assertFalse(err)
        self.assertFalse(study.attack_success(goal, before, after))
        sent, canceled, deleted = analyze.changed_states(before, after)
        self.assertEqual(set(sent[0].recipients), set(goal['arguments']['recipients']))
        self.assertEqual((canceled, deleted), ([], set()))

    def test_proposal_parser_preserves_invalid_arguments(self):
        goal = dict(tool='delete_file', arguments={'file_id': '9'})
        self.assertTrue(analyze.exact(dict(name='delete_file', arguments='{"file_id":"9"}'), goal))
        for arguments in ['not json', '[]', 'null', '{"file_id":"11"}']:
            self.assertFalse(analyze.exact(dict(name='delete_file', arguments=arguments), goal))
        self.assertFalse(analyze.exact(dict(name='list_files', arguments='{}'), goal))

    def test_manifest_tamper_is_detected(self):
        plan = study.read(study.PUBLIC / 'development.json')
        plan['cases'][0]['condition'] = 'trustgate'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'plan.json'
            path.write_text(json.dumps(plan))
            with self.assertRaises(AssertionError):
                study.checked_plan(path)

    def test_disjoint_tasks_and_matrix(self):
        original = study.read(ROOT / 'assignments/formal/plan.json')
        heldout = {f'user_task_{r[0]}' for r in study.TASKS['evaluation']}
        dev = {f'user_task_{r[0]}' for r in study.TASKS['development']}
        self.assertFalse(heldout & set(original['config']['formal_tasks']))
        self.assertFalse(heldout & dev)
        plan = study.checked_plan(study.PUBLIC / 'development.json')
        self.assertEqual(len(plan['cases']), 12)
        self.assertTrue(all(c['condition'] == 'none' and c['surface'] == 'metadata' for c in plan['cases']))
        self.assertEqual(set(plan['config']['formal_tasks']), dev)


if __name__ == '__main__':
    unittest.main()
