#!/usr/bin/env python3
"""行政案例提取 wrapper，移动后仍按仓库根目录解析相对路径。"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(os.path.expanduser('~/.hermes/.env'))

if not os.environ.get('DEEPSEEK_API_KEY'):
    print("ERROR: DEEPSEEK_API_KEY not set", flush=True)
    sys.exit(1)

import argparse
from extraction.llm_extractors.guiding_case_extractor_v3 import main


parser = argparse.ArgumentParser()
parser.add_argument('--input', default='data/raw/admin_cases_only.csv')
parser.add_argument('--output', default='data_lake/extracted_v2.2_admin_full.jsonl')
parser.add_argument('--limit', type=int, default=37)
parser.add_argument('--start', type=int, default=0)
parser.add_argument('--workers', type=int, default=3)
parser.add_argument('--prompt-path', default='ontology/prompts/auto_v5_admin.txt')
args = parser.parse_args()

sys.argv = [
    'guiding_case_extractor_v3.py',
    '--input', args.input,
    '--output', args.output,
    '--limit', str(args.limit),
    '--start', str(args.start),
    '--workers', str(args.workers),
    '--prompt-path', args.prompt_path,
    '--meta-producer', 'scripts/admin_batches/run_admin_extraction.py',
    '--meta-batch-label', 'admin_full',
]
main()
