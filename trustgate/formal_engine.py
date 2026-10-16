"""Formal cases share the MVP agent loop, with explicit frozen data and policies."""
import copy
import sys
from .planning import ROOT,digest
sys.path.insert(0,str(ROOT/'experiments/mvp'))
from run_matrix_v2 import Experiment
from simulation_runtime import read_state
from .formal_policy import authorize
from .formal_data import attack_success

class FormalExperiment(Experiment):
    def case_config(self,case):
        attack=self.cfg['formal_attacks'].get(case.get('attack_case_id'))
        return {**self.cfg,**(attack or {}),'output_injection':'mcp_append'}
    def policy_for(self,task,clean):
        frozen=self.cfg['formal_tasks'][task.ID]
        if frozen['prompt']!=task.PROMPT or frozen['initial_state_sha256']!=digest(clean.model_dump(mode='json')):
            raise RuntimeError('Benchmark prompt or initial state changed after freeze')
        return copy.deepcopy(frozen['policy'])
    def authorize_call(self,policy,name,args):
        return authorize(policy,name,args,read_state(self.state))
    def attacker_result(self,case,cfg,output,before,after,stacktrace):
        return attack_success(cfg['goal'],before,after)
