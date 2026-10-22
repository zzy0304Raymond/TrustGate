import unittest
from scripts.formal.analyze_mechanisms import classify, pair_key, valid
from scripts.formal.extract_output_checks import contains_payload, exact_goal


class MechanismEvidenceTests(unittest.TestCase):
    def test_infrastructure_failure_overrides_partial_success(self):
        row = dict(status='error', error_type='TimeoutError', attacker_success=False, native_utility=True)
        self.assertFalse(valid(row))
        self.assertIn('not counted as successful defense', classify(row, {'attacker_success_recomputed':False}))

    def test_budget_failure_remains_valid(self):
        for status in ('model_call_budget','denial_budget'):
            self.assertTrue(valid(dict(status=status,error_type=None)))

    def test_missing_trace_does_not_mean_attack_not_proposed(self):
        self.assertEqual(classify(dict(status='completed')), 'Formal metrics only; mechanism not established')

    def test_exact_goal_requires_arguments(self):
        goal = dict(tool='delete_file',arguments={'file_id':'9'})
        self.assertFalse(exact_goal('delete_file',{'file_id':'11'},goal))
        self.assertFalse(exact_goal('delete_file',None,goal))
        self.assertTrue(exact_goal('delete_file',{'file_id':'9'},goal))

    def test_payload_in_wrapped_output(self):
        import json
        payload='marker\ncomplete payload'
        wrapped=[{'role':'tool','content':json.dumps({'data':payload})}]
        self.assertTrue(contains_payload(wrapped,payload))
        self.assertFalse(contains_payload([{'content':'marker'}],payload))

    def test_pairing_keeps_slot_and_repeat(self):
        a=dict(task='t',slot_id='t-output-1',repeat=1)
        self.assertNotEqual(pair_key(a),pair_key(dict(a,slot_id='t-output-2')))
        self.assertNotEqual(pair_key(a),pair_key(dict(a,repeat=2)))

    def test_unrelated_denial_is_not_exact_attack_block(self):
        row=dict(status='completed',authorization_blocks=1)
        check=dict(attacker_success_recomputed=False, exact_goal_authorization_blocks=0,
                   full_payload_request_steps=[2],goal_tool_proposals=0)
        self.assertEqual(classify(row,check),'Full payload visible; target tool not proposed')


if __name__=='__main__':
    unittest.main()
