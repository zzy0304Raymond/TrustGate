"""Normalize simulation write timestamps only, so separate processes remain comparable."""
import datetime,types
from unittest.mock import patch
from agentdojo.default_suites.v1.tools import email_client,cloud_drive_client

class FixedDateTime(datetime.datetime):
    @classmethod
    def now(cls,tz=None):return datetime.datetime(2024,5,15,9,0,tzinfo=tz)

clock=types.SimpleNamespace(**{**vars(datetime),'datetime':FixedDateTime})

def run_native(runtime,env,name,args):
    # Do not patch the experiment's wall clock or change task/evaluator logic.
    with patch.object(email_client,'datetime',clock),patch.object(cloud_drive_client,'datetime',clock):
        return runtime.run_function(env,name,args)

# The pickle is an internal, locally generated backend checkpoint, never tool input.
# AgentDojo's JSON validators rebuild live dictionaries from initial_* fields and
# would silently discard new objects. Pickle retains live state and object aliases.
import os,pickle
from pathlib import Path

def write_state(path,env):
    path=Path(path);temp=path.with_suffix('.tmp')
    with temp.open('wb') as f:pickle.dump(env,f,protocol=5)
    os.chmod(temp,0o600);temp.replace(path)

def read_state(path):
    with Path(path).open('rb') as f:return pickle.load(f)
