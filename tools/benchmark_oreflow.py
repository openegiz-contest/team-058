#!/usr/bin/env python3
"""Reproducible, holdout simulation experiments. NOT physical mine validation."""
from pathlib import Path
import sys,json,csv,statistics,datetime
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'team/oreflow'))
from engine import MineRun,compare,paired_benchmark

def main():
    dst=ROOT/'team/oreflow/reports';dst.mkdir(exist_ok=True,parents=True)
    reports={}
    for s in ('normal','shovel_outage','road_closure','fleet_reduction'):
        reports[s]=paired_benchmark(strategy='smart',scenario=s,seeds=range(21,32),fleet=50)
    seed42={}
    for strategy in ('nearest','balanced','smart'):
        run=MineRun(strategy=strategy,seed=42).simulate()
        seed42[strategy]=run.metrics()
    report={'input':'Official OpenMines North Pit JSON; MIT license',
            'status':'simulated dispatch evaluations; not real-world ML performance',
            'engine':'Independent OreFlow discrete-event approximation, not OpenMines engine',
            'policy':{'dump_weight':.05,'queue_weight':.8,'site_weight':-.2,
                      'method':'grid tuning using seeds 11-14, validation seeds 15-18, final held-out seeds 21-31'},
            'duration_min':240,'single_seed_comparison':seed42,'heldout_seed_experiments':reports}
    (dst/'benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
    with (dst/'benchmark.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['scenario','seed','baseline_t','candidate_t','change_pct','baseline_queue_min','candidate_queue_min'])
        for scenario,record in reports.items():
            for v in record['runs']:
                writer.writerow([scenario,v['seed'],v['baseline_t'],v['candidate_t'],v['change_pct'],v['baseline_queue'],v['candidate_queue']])
    with (dst/'sample_haul_trips.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['truck','end_min','tonnes','load_site','dump_site']);writer.writeheader()
        writer.writerows(MineRun(strategy='smart',seed=42).simulate().trips)
    print('Seed 42 normal run:',seed42)
    for k,v in reports.items():
        print(k,'heldout mean gain',v['mean_change_pct'],'%', 'all seeds improve:',v['all_seeds_better'])
    print('Wrote',dst)
if __name__=='__main__':main()
