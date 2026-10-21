"""Check paired weighting and sensitivity exclusions on deliberately unequal task groups."""
import unittest
from scripts.formal.analyze_overhead import paired, METRICS, RECOVERED


def row(task, repeat, condition, value, case_id='', error=None, platform='Vanda'):
    return dict(task=task, slot_id=task+'-output-1', repeat=repeat, condition=condition,
                surface='output', platform_group=platform, case_id=case_id, error_type=error,
                **{m: value for m in METRICS})


class OverheadTests(unittest.TestCase):
    def test_tasks_have_equal_weight_despite_different_repeat_counts(self):
        rows = [row('a', 1, 'none', 2), row('a', 1, 'trustgate', 12)]
        for repeat in (1, 2, 3):
            rows += [row('b', repeat, 'none', 2), row('b', repeat, 'trustgate', 2)]
        result = paired(rows, 'output', 'none')[0]
        self.assertEqual(result['paired_tasks'], 2)
        self.assertEqual(result['paired_records'], 4)
        self.assertEqual(result['task_weighted_difference'], 5)

    def test_excluding_recovered_trial_removes_its_whole_pair(self):
        rows = [row('a', 1, 'none', 1, RECOVERED), row('a', 1, 'trustgate', 20),
                row('b', 1, 'none', 1), row('b', 1, 'trustgate', 3)]
        result = paired(rows, 'output', 'none', exclude_recovered=True)[0]
        self.assertEqual((result['paired_tasks'], result['paired_records']), (1, 1))
        self.assertEqual(result['task_weighted_difference'], 2)

    def test_infrastructure_error_and_other_platform_do_not_enter_pair(self):
        rows = [row('a', 1, 'none', 1), row('a', 1, 'trustgate', 9, error='TimeoutError'),
                row('b', 1, 'none', 1, platform='Mac'), row('b', 1, 'trustgate', 4, platform='Mac')]
        self.assertEqual(paired(rows, 'output', 'none', scope='Vanda')[0]['paired_records'], 0)
        self.assertEqual(paired(rows, 'output', 'none')[0]['paired_records'], 1)


if __name__ == '__main__':
    unittest.main()
