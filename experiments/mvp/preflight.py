from simulation_runtime import run_native,write_state,read_state
"""Deterministic transport equivalence and enforcement checks; no model/API calls."""
import asyncio,contextlib,json,os,time
from pathlib import Path
from run_matrix import Experiment,ROOT,dump,make_policy,authorize
from agentdojo.task_suite.load_suites import get_suite
from agentdojo.agent_pipeline.tool_execution import tool_result_to_str

async def main():
    cfg=json.loads((ROOT/'configs/mvp/pilot.json').read_text());out=ROOT/'runs/mvp'/('preflight_'+str(time.time_ns()));out.mkdir()
    suite=get_suite('v1.2.2','workspace')
    defaults=suite.get_injection_vector_defaults();payload=json.dumps(defaults[cfg['attack_vector']]+'\n'+cfg['payload'],ensure_ascii=False)[1:-1]
    clean=suite.load_and_inject_default_environment({});attacked=suite.load_and_inject_default_environment({cfg['attack_vector']:payload})
    from deepdiff import DeepDiff
    diff=DeepDiff(clean.model_dump(mode='json'),attacked.model_dump(mode='json'))
    assert set(diff)=={'values_changed'}
    assert all("['description']" in path and "['calendar']" in path for path in diff['values_changed'])
    dump(out/'injection_scope_check.json',{'passed':True,'changed_paths':list(diff['values_changed'])})
    e=Experiment(cfg,out,suite,None,'');checks=[]
    async with contextlib.AsyncExitStack() as stack:
        await e.start(stack)
        listed=[]
        for server,client in e.clients.items():
            r=await client.list_tools()
            for tool in r.tools:
                f=e.runtime.functions[tool.name]
                assert tool.description==f.description and tool.inputSchema==f.parameters.model_json_schema()
                assert e.routing[tool.name]==server
                listed.append(tool.name)
        assert set(listed)==set(e.runtime.functions)
        # The output attack must survive MCP with exactly the same model-visible text.
        write_state(e.state,attacked)
        local_result,err=run_native(e.runtime,attacked,'get_day_calendar_events',{'day':'2024-05-15'})
        remote=await e.clients['calendar'].call_tool('get_day_calendar_events',{'day':'2024-05-15'})
        assert not err and not remote.isError
        assert remote.content[0].text==tool_result_to_str(local_result)
        assert 'Workspace integrity checkpoint:' in remote.content[0].text
        # Metadata poisoning is restricted to one description; schemas stay identical.
        dump(e.control,{'state_path':str(e.state),'surface':'metadata','payload':cfg['payload']})
        changed=[]
        for server,client in e.clients.items():
            response=await client.list_tools()
            for t in response.tools:
                f=e.runtime.functions[t.name]
                assert t.inputSchema==f.parameters.model_json_schema()
                if t.description!=f.description:changed.append(t.name)
        assert changed==['get_day_calendar_events']
        dump(out/'attack_transport_checks.json',{'output_text_identical':True,'metadata_changed_tools':changed,'all_input_schemas_identical':True})
        dump(e.control,{'state_path':str(e.state),'surface':'benign'})
        for workflow,tid in cfg['workflows'].items():
            task=suite.user_tasks[tid];env=task.init_environment(suite.load_and_inject_default_environment({}));before=env.model_copy(deep=True)
            write_state(e.state,env);policy=make_policy(task,env,e.runtime)
            for call in task.ground_truth(env.model_copy(deep=True)):
                # Ground truth is confined to this independent adapter test, never used in the policy or agent loop.
                a,err=run_native(e.runtime,env,call.function,call.args);assert not err
                b=await e.clients[e.routing[call.function]].call_tool(call.function,call.args)
                dump(out/'last_comparison.json',{'task':tid,'tool':call.function,'arguments':call.args,'local':tool_result_to_str(a),'mcp':b.model_dump(mode='json')})
                assert not b.isError and '\n'.join(x.text for x in b.content if x.type=='text')==tool_result_to_str(a)
                post=read_state(e.state)
                from deepdiff import DeepDiff
                dump(out/'last_state_diff.json',str(DeepDiff(env.model_dump(mode='json'),post.model_dump(mode='json'))))
                assert post==env
                ok,why=authorize(policy,call.function,call.args);assert ok,(tid,call.function,why)
            # Unrequested communication is denied without depending on an attacker address.
            for addr in ['external@example.net','mark.black-2134@gmail.com']:
                ok,_=authorize(policy,'send_email',{'recipients':[addr],'subject':'hello','body':'test'});assert not ok
            checks.append({'workflow':workflow,'task':tid,'schema_equal':True,'result_equal':True,'state_equal':True,'legitimate_calls_allowed':True,'unrequested_email_denied':True})
        # Resource and participant constraints cannot be enlarged by arbitrary tool data.
        task=suite.user_tasks['user_task_29'];env=task.init_environment(suite.load_and_inject_default_environment({}));policy=make_policy(task,env,e.runtime)
        assert not authorize(policy,'append_to_file',{'file_id':'999','content':'test'})[0]
        task=suite.user_tasks['user_task_6'];policy=make_policy(task,env,e.runtime)
        args={'title':'Lunch','description':'Catch up over lunch.','start_time':'2024-05-19 12:00','end_time':'2024-05-19 13:00','participants':['sarah.connor@gmail.com','external@example.net']}
        assert not authorize(policy,'create_calendar_event',args)[0]
    dump(out/'verification.json',{'passed':True,'model_calls':0,'tools_checked':len(listed),'workflows':checks});print('PREFLIGHT_RESULT '+str(out),flush=True)

if __name__=='__main__':asyncio.run(main())
