"""Print a checked walkthrough of recorded trials; this never calls a model."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.demo.build import verify_bundle
from scripts.demo.export_checks import offline

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=['all','normal','defense','false-positive'],default='all')
    args=parser.parse_args()
    from trustgate.runner import require_compute
    require_compute();sys.addaudithook(offline)
    data=verify_bundle()
    print('TrustGate | '+data['mode_label']+' | Current model request: 0')
    for c in data['cases']:
        if args.case not in ('all',c['id']):continue
        print('\n'+c['number']+' '+c['title']+'\nTask:'+c['task'])
        for i,step in enumerate(c['steps'],1):
            print(f"  {i}. {step['title']}: {step['detail']}")
        print('Result:'+c['result']+'\nExplanation:'+c['conclusion']+'\nBoundary:'+c['limit'])
        print('Case:'+', '.join(c['case_ids']))

if __name__=='__main__':main()
