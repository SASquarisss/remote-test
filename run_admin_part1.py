#!/usr/bin/env python3
"""PART 1: rows 3-19 (17 rows)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.expanduser('~/.hermes/.env'))

if not os.environ.get('DEEPSEEK_API_KEY'):
    print("ERROR: DEEPSEEK_API_KEY not set", flush=True)
    sys.exit(1)

print(f"DEEPSEEK_API_KEY set: {os.environ['DEEPSEEK_API_KEY'][:8]}...", flush=True)

from extraction.llm_extractors.guiding_case_extractor_v3 import main

sys.argv = [
    'guiding_case_extractor_v3.py',
    '--input', 'data/raw/admin_cases_only.csv',
    '--output', 'data_lake/extracted_v2.2_admin_full_part1.jsonl',
    '--limit', '17',
    '--start', '3',
    '--workers', '3',
    '--prompt-path', 'ontology/prompts/auto_v5_admin.txt',
]
main()
