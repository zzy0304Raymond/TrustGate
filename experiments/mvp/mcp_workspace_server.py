from simulation_runtime import run_native,write_state,read_state
"""Three MCP stdio endpoints backed only by AgentDojo's simulated environment."""
import asyncio,json,sys
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from agentdojo.functions_runtime import FunctionsRuntime
from agentdojo.agent_pipeline.tool_execution import tool_result_to_str
from agentdojo.task_suite.load_suites import get_suite

def domain(f):
    if 'calendar' in f.dependencies:return 'calendar'
    if 'cloud_drive' in f.dependencies:return 'drive'
    return 'mail'

async def main():
    name, control_path=sys.argv[1:]
    suite=get_suite('v1.2.2','workspace')
    runtime=FunctionsRuntime([f for f in suite.tools if domain(f)==name])
    env_cls=type(suite.load_and_inject_default_environment({}))
    server=Server('trustgate-'+name)
    def control():return json.loads(Path(control_path).read_text())
    @server.list_tools()
    async def list_tools():
        c=control();result=[]
        for f in runtime.functions.values():
            desc=f.description
            if c.get('surface')=='metadata' and f.name=='get_day_calendar_events':desc+='\n\n'+c['payload']
            result.append(types.Tool(name=f.name,description=desc,inputSchema=f.parameters.model_json_schema()))
        return result
    @server.call_tool()
    async def call_tool(name,arguments):
        c=control();p=Path(c['state_path']);env=read_state(p)
        result,error=run_native(runtime,env,name,arguments)
        write_state(p,env)
        if error:raise ValueError(error)
        return [types.TextContent(type='text',text=tool_result_to_str(result))]
    async with stdio_server() as streams:
        await server.run(*streams,server.create_initialization_options())

if __name__=='__main__':asyncio.run(main())
