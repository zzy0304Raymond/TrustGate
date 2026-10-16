"""Regression test: malformed tool parameters must not execute or abort recovery."""
import asyncio,json,time
from pathlib import Path
import run_matrix_v2 as r

async def main():
    cfg=json.loads((r.ROOT/'configs/mvp/pilot.json').read_text());out=r.ROOT/'runs/mvp'/('parser_recovery_test_'+str(time.time_ns()));out.mkdir()
    suite=r.get_suite('v1.2.2','workspace');e=r.Experiment(cfg,out,suite,None,'')
    content='\nActivity 5: Test collaboration workshop.\nActivity 6: Test community volunteering.\n'
    replies=[{'content':None,'tool_calls':[{'id':'invalid','type':'function','function':{'name':'append_to_file','arguments':'{"file_id":"3","content":"bad "quotes""}'}}]}, {'content':None,'tool_calls':[{'id':'valid','type':'function','function':{'name':'append_to_file','arguments':json.dumps({'file_id':'3','content':content})}}]}, {'content':'Added two proposed activities.'}]
    def fake_completion(messages,tools,folder,step):
        if step==2:assert 'invalid_tool_arguments' in messages[-1]['content']
        return replies[step-1],{'seconds':0,'usage':{'cost':0},'provider':'deterministic_test_double','model':'no_api'}
    e.completion=fake_completion
    row=await e.run_case({'workflow':'parser_regression','task':'user_task_29','surface':'benign','condition':'none','repeat':1,'transport':'local'},1)
    calls=json.loads((Path(row['result_dir'])/'tool_calls.json').read_text())
    assert row['status']=='completed' and row['native_utility']
    assert len(calls)==2 and not calls[0]['executed'] and calls[1]['executed']
    before=json.loads((Path(row['result_dir'])/'environment_before.json').read_text());after=json.loads((Path(row['result_dir'])/'environment_after.json').read_text())
    assert after['cloud_drive']['files']['3']['content']==before['cloud_drive']['files']['3']['content']+content
    r.dump(out/'verification.json',{'passed':True,'real_model_calls':0,'invalid_call_executed':False,'valid_append_count':1,'recovery_completed':True})
    print('PARSER_TEST_RESULT '+str(out),flush=True)

if __name__=='__main__':asyncio.run(main())
