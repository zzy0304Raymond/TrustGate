"""Real MCP, offline validation. No model requests and no hidden user answers."""
import asyncio
import contextlib
import copy
import json
import os
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from trustgate.planning import ROOT,read_plan,CONDITIONS
from trustgate.formal_engine import FormalExperiment
from trustgate.formal_data import attack_success
from trustgate.runner import require_compute
from simulation_runtime import run_native,write_state,read_state
from agentdojo.task_suite.load_suites import get_suite
from agentdojo.agent_pipeline.tool_execution import tool_result_to_str

def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n')

async def main():
    require_compute();os.umask(0o077)
    plan=read_plan(ROOT/'assignments/formal/plan.json');suite=get_suite('v1.2.2','workspace')
    out=ROOT/'runs/formal-preflight'/str(time.time_ns());out.mkdir(parents=True)
    experiment=FormalExperiment(plan['config'],out,suite,None,'offline-no-credential')
    checks=[]
    async with contextlib.AsyncExitStack() as stack:
        await experiment.start(stack)
        listed=0
        for server,client in experiment.clients.items():
            response=await client.list_tools()
            for tool in response.tools:
                native=experiment.runtime.functions[tool.name]
                assert tool.description==native.description
                assert tool.inputSchema==native.parameters.model_json_schema();listed+=1
        for attack in plan['config']['formal_attacks'].values():
            task=suite.user_tasks[attack['task']]
            clean=task.init_environment(suite.load_and_inject_default_environment({}));policy=experiment.policy_for(task,clean)
            write_state(experiment.state,clean)
            control={'state_path':str(experiment.state),'surface':attack['surface'],'payload':attack['payload'],
                     'metadata_tool':attack['metadata_tool'],'output_injection':'mcp_append','output_tools':attack['output_tools'],'output_consumed':False}
            dump(experiment.control,control)
            if attack['surface']=='metadata':
                changed=[]
                for server,client in experiment.clients.items():
                    response=await client.list_tools()
                    for tool in response.tools:
                        native=experiment.runtime.functions[tool.name]
                        assert tool.inputSchema==native.parameters.model_json_schema()
                        if tool.description!=native.description:
                            assert tool.description==native.description+'\n\n'+attack['payload'];changed.append(tool.name)
                assert changed==[attack['metadata_tool']]
            else:
                name=attack['output_tools'][0];args={'query':''} if name.startswith('search_') and name!='search_files_by_filename' else {'filename':''} if name=='search_files_by_filename' else {}
                local=clean.model_copy(deep=True)
                result,error=run_native(experiment.runtime,local,name,args);assert not error
                response=await experiment.clients[experiment.routing[name]].call_tool(name,args)
                assert not response.isError
                assert '\n'.join(c.text for c in response.content)==tool_result_to_str(result)+'\n\n'+attack['payload']
                second=await experiment.clients[experiment.routing[name]].call_tool(name,args)
                assert attack['marker'] not in '\n'.join(c.text for c in second.content)
                assert read_state(experiment.state)==local
            assert not attack_success(attack['goal'],clean,read_state(experiment.state))
            assert experiment.policy_for(task,clean)==policy
            goal=attack['goal'];response=await experiment.clients[experiment.routing[goal['tool']]].call_tool(goal['tool'],goal['arguments'])
            assert not response.isError,(attack['attack_case_id'],response)
            assert attack_success(goal,clean,read_state(experiment.state))
            checks.append({'attack_case_id':attack['attack_case_id'],'transport_scope':True,'objective_reachable':True,'policy_unchanged':True})
        # Each policy has a documented permissible read through the actual agent loop.
        class OfflineDetector:
            def score(self,text):return {'score':0.0,'blocked':False,'seconds':0.0,'windows':1}
        experiment.detector=OfflineDetector()
        def completion(messages,tools,folder,step):
            if step==1:
                row=experiment.cfg['formal_tasks'][current['task']]
                name=row['output_tools'][0]
                args={'query':''} if name!='list_files' else {}
                return {'content':None,'tool_calls':[{'id':'offline-read','type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}, {'usage':{'cost':0},'seconds':0}
            return {'content':'Offline adapter check; not a model answer.'},{'usage':{'cost':0},'seconds':0}
        experiment.completion=completion
        cases=[]
        for tid,row in plan['config']['formal_tasks'].items():
            cases.append({'task':tid,'workflow':row['workflow'],'surface':'benign','condition':'trustgate','repeat':1,'transport':'mcp'})
        for surface in ('output','metadata'):
            attack=next(a for a in plan['config']['formal_attacks'].values() if a['surface']==surface)
            for condition in CONDITIONS:
                cases.append({'task':attack['task'],'workflow':plan['config']['formal_tasks'][attack['task']]['workflow'],
                              'surface':surface,'condition':condition,'repeat':1,'transport':'mcp','attack_case_id':attack['attack_case_id']})
        for index,current in enumerate(cases,1):
            row=await experiment.run_case(current,index)
            assert row['status']=='completed' and row['error'] is None,(current,row['error'])
            assert row['api_calls']==2
            if current['surface']!='benign':assert row['injection_reached_model']
    report={'passed':True,'network_model_requests':0,'tools':listed,'attack_transport_checks':len(checks),
            'formal_task_loop_checks':20,'condition_surface_loop_checks':14,
            'scripted_decoder':True,'does_not_measure_model_utility_or_attack_effectiveness':True,
            'plan_sha256':plan['plan_sha256'],'checks':checks}
    dump(out/'verification.json',report);dump(ROOT/'docs/validation/formal_preflight.json',report)
    print('FORMAL_PREFLIGHT '+str(out),flush=True)
if __name__=='__main__':asyncio.run(main())
