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
    print('TrustGate | '+data['mode_label']+' | 本次模型请求：0')
    for c in data['cases']:
        if args.case not in ('all',c['id']):continue
        print('\n'+c['number']+' '+c['title']+'\n任务：'+c['task'])
        for i,step in enumerate(c['steps'],1):
            print(f"  {i}. {step['title']}：{step['detail']}")
        print('结果：'+c['result']+'\n解释：'+c['conclusion']+'\n边界：'+c['limit'])
        print('案例：'+', '.join(c['case_ids']))

if __name__=='__main__':main()
