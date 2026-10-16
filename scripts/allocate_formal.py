"""Generate and validate the five formal workload assignments; zero API calls."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from trustgate.formal_allocation import ROOT, write_allocation
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,default=ROOT/'assignments/formal')
args=parser.parse_args()
plan=write_allocation(args.output)
print(json.dumps(dict(total_runs=plan['total_runs'],ready_to_run=plan['ready_to_run'],
    serial_hours=plan['estimated_serial_seconds']/3600,
    five_person_hours=plan['estimated_parallel_seconds']/3600,
    people=[dict(person=p['person'],tasks=p['tasks'],runs=p['total_runs'],hours=p['estimated_seconds']/3600) for p in plan['people']]),ensure_ascii=False,indent=2))
