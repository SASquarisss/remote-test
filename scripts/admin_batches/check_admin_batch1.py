#!/usr/bin/env python3
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

all_recs = {}
for rel_path in ['data_lake/extracted_v2.2_admin_batch1_first10.jsonl', 'data_lake/extracted_v2.2_admin_batch1_remaining.jsonl']:
    path = REPO_ROOT / rel_path
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    all_recs[r['row_id']] = r
    except Exception as e:
        print(f"skip {path}: {e}")

ids_order = ['2292','3358','3906','699','3369','5412','3228','5319']
sorted_recs = [all_recs[rid] for rid in ids_order if rid in all_recs]

with (REPO_ROOT / 'data_lake/extracted_v2.2_admin_full.jsonl').open('w', encoding='utf-8') as f:
    for r in sorted_recs:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')

ok = [r for r in sorted_recs if r['output']]
print(f'总记录: {len(sorted_recs)}')
print(f'成功: {len(ok)}')
scores = [r['eval']['score'] for r in ok]
avg = sum(scores)/len(scores) if scores else 0
print(f'平均分: {avg:.1f}')
for r in ok:
    rid = r['row_id']
    out = r['output']
    cc = (out.get('court_cases') or [{}])[0]
    cs = out.get('case_summary') or {}
    drt = cc.get('dispute_resolution_type', '')
    prov = len(out.get('legal_provisions') or [])
    claim = cs.get('claim_amount', '') or '--'
    if len(claim) > 20:
        claim = claim[:20]
    party = cc.get('party_count')
    print(f'  {rid}: score={r["eval"]["score"]:.0f} drt={drt} provisions={prov} claim={claim} party={party}')
