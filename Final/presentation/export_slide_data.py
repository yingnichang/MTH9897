"""Snapshot demo CSV outputs for the presentation, using only Python's standard library.

Usage: python export_slide_data.py --outputs /path/to/output/demo
Run the notebook in demo mode first. Real empirical outputs require a revised deck narrative.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--outputs', type=Path, default=HERE.parent / 'output' / 'demo')
args = parser.parse_args()
source = args.outputs
manifest = json.loads((source / 'synthetic_demo_manifest.json').read_text(encoding='utf-8'))
if manifest['mode'] != 'demo':
    raise ValueError('This presentation describes a synthetic demonstration. Revise the narrative for empirical data.')

def read_csv(name):
    with (source / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

summary = {}
for row in read_csv('synthetic_demo_performance.csv'):
    name = row.pop('')
    summary[name] = {k: float(v) if v else None for k, v in row.items()}
costs = [{k: float(v) for k, v in row.items()} for row in read_csv('synthetic_demo_cost_sensitivity.csv')]
monthly = read_csv('synthetic_demo_monthly_returns.csv')
names = ['Conservative', 'Low volatility only', 'Universe equal weight', 'Market']
wealth = {name: 1.0 for name in names}
annual = [{'year': str(int(monthly[0]['date'][:4])-1), **wealth}]
for row in monthly:
    for name in names:
        wealth[name] *= 1+float(row[name])
    if row['date'][5:7] == '12':
        annual.append({'year': row['date'][:4], **wealth})
snapshot = {'manifest': manifest, 'performance': summary, 'costs': costs, 'annual_wealth': annual,
    'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in source.glob('synthetic_demo_*.csv')}}
(HERE / 'slide_data.json').write_text(json.dumps(snapshot, indent=2), encoding='utf-8')
print('Wrote', HERE / 'slide_data.json')
