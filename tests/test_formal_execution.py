import copy
import json
import sys
import unittest
from pathlib import Path
from trustgate.planning import ROOT,read_plan,digest
from trustgate.formal_policy import authorize,compile_policy
from trustgate.formal_data import attack_success
from trustgate.formal_manifest import validate_formal_plan
sys.path.insert(0,str(ROOT/'experiments/mvp'))
from agentdojo.task_suite.load_suites import get_suite
from agentdojo.functions_runtime import FunctionsRuntime
from simulation_runtime import run_native

class FormalExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=read_plan(ROOT/'assignments/formal/plan.json')
        cls.tasks=cls.plan['config']['formal_tasks'];cls.attacks=cls.plan['config']['formal_attacks']
        cls.suite=get_suite('v1.2.2','workspace');cls.runtime=FunctionsRuntime(cls.suite.tools)
    def environment(self,tid):return self.suite.user_tasks[tid].init_environment(self.suite.load_and_inject_default_environment({}))
    def test_all_goals_reachable_and_host_denies_them(self):
        for attack in self.attacks.values():
            with self.subTest(case=attack['attack_case_id']):
                env=self.environment(attack['task']);before=env.model_copy(deep=True);goal=attack['goal']
                self.assertFalse(attack_success(goal,before,env))
                self.assertFalse(authorize(self.tasks[attack['task']]['policy'],goal['tool'],goal['arguments'],env)[0])
                _,error=run_native(self.runtime,env,goal['tool'],goal['arguments'])
                self.assertFalse(error)
                self.assertTrue(attack_success(goal,before,env))
    def test_policies_depend_only_on_clean_inputs(self):
        for tid,row in self.tasks.items():
            env=self.environment(tid)
            self.assertEqual(digest(env.model_dump(mode='json')),row['initial_state_sha256'])
            self.assertEqual(compile_policy(self.suite.user_tasks[tid],env,self.runtime,row['workflow']),row['policy'])
    def test_recipient_expansion_blocked_and_created_file_binding(self):
        policy=self.tasks['user_task_32']['policy'];env=self.environment('user_task_32')
        self.assertFalse(authorize(policy,'share_file',{'file_id':'7','email':'john.doe@gmail.com','permission':'r'},env)[0])
        result,error=run_native(self.runtime,env,'create_file',{'filename':'hawaii-packing-list.docx','content':'test'})
        self.assertFalse(error);fid=str(result.id_)
        args={'file_id':fid,'email':'john.doe@gmail.com','permission':'r'}
        self.assertTrue(authorize(policy,'share_file',args,env)[0])
        self.assertFalse(authorize(policy,'share_file',{**args,'email':'other@trustgate.invalid'},env)[0])
        self.assertFalse(authorize(policy,'share_file',{**args,'permission':'rw'},env)[0])
    def test_calendar_grants_match_request_and_preserve_duration(self):
        policy=self.tasks['user_task_7']['policy']
        args={'event_id':'5','new_start_time':'2024-05-20 10:00'}
        self.assertTrue(authorize(policy,'reschedule_calendar_event',args)[0])
        self.assertFalse(authorize(policy,'reschedule_calendar_event',{**args,'new_end_time':'2024-05-20 12:00'})[0])
        policy=self.tasks['user_task_12']['policy']
        self.assertEqual(policy['writes']['create_calendar_event']['exact']['start_time'],'2024-05-19T16:00:00')
    def test_missing_condition_or_foreign_attack_rejected(self):
        changed=copy.deepcopy(self.plan);changed['shards'][0]['cases'][0]['condition']='made-up'
        changed['plan_sha256']=digest({k:v for k,v in changed.items() if k!='plan_sha256'})
        with self.assertRaises(ValueError):validate_formal_plan(changed)
    def test_held_out_families_and_case_counts(self):
        self.assertFalse(set(self.plan['test_template_families'])&set(self.plan['development_template_families']))
        self.assertEqual(len({a['payload'] for a in self.attacks.values()}),60)
        self.assertEqual(sum(a['surface']=='output' for a in self.attacks.values()),30)
        self.assertEqual(sum(a['surface']=='metadata' for a in self.attacks.values()),30)
        self.assertEqual(len({a['template_family'] for a in self.attacks.values()}),3)
        for surface in ('output','metadata'):
            for goal in ('send_email','cancel_calendar_event','delete_file'):
                self.assertEqual(sum(a['surface']==surface and a['goal']['tool']==goal for a in self.attacks.values()),10)

    def test_every_declared_write_has_a_valid_request_and_simulated_execution(self):
        checked=0
        for tid,row in self.tasks.items():
            policy=row['policy']
            for name,grant in policy['writes'].items():
                with self.subTest(task=tid,tool=name):
                    env=self.environment(tid);args=copy.deepcopy(grant.get('exact',{}))
                    args.update({key:values[0] for key,values in grant.get('one_of',{}).items()})
                    args.update(copy.deepcopy(grant.get('sets',{})))
                    if name=='create_file':args['content']='A synthetic packing list for an offline adapter check.'
                    if name=='send_email':args['body']='An offline synthetic summary.'
                    if 'duration_hours' in grant:
                        args.update(title='Hiking trip',start_time='2024-05-18 09:00',end_time='2024-05-18 14:00',location='Trailhead')
                    if 'created_filename' in grant:
                        made,error=run_native(self.runtime,env,'create_file',{'filename':grant['created_filename'],'content':'test'})
                        self.assertFalse(error);args['file_id']=str(made.id_)
                    import datetime
                    for key in ('start_time','end_time','new_start_time','new_end_time'):
                        if args.get(key):args[key]=datetime.datetime.fromisoformat(args[key]).strftime('%Y-%m-%d %H:%M')
                    self.assertTrue(authorize(policy,name,args,env)[0])
                    _,error=run_native(self.runtime,env,name,args);self.assertFalse(error)
                    checked+=1
        self.assertEqual(checked,10)
