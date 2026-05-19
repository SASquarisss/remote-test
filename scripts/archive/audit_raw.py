#!/usr/bin/env python3
"""Parse raw CSV and cross-validate sample records."""
import csv

raw_path = "/root/.hermes/hermes-agent/remote-test/data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv"

with open(raw_path, 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    print(f"Raw CSV columns ({len(header)}):")
    for i, col in enumerate(header):
        print(f"  {i}: '{col}'")
    
    target_ids = ['2292', '298', '412', '604', '12931', '476', '6379']
    found = 0
    for row in reader:
        if row and row[0].strip('"\n\r ') in target_ids:
            rid = row[0].strip('"\n\r ')
            print(f"\n--- Raw Record ID={rid} ---")
            print(f"  case_type (col3): {row[3] if len(row)>3 else '?'}")
            print(f"  storage_no (col4): {row[4] if len(row)>4 else '?'}")
            print(f"  court_name (col5): {row[5] if len(row)>5 else '?'}")
            print(f"  trial_procedure (col7): {row[7] if len(row)>7 else '?'}")
            print(f"  trial_year (col8): {row[8] if len(row)>8 else '?'}")
            print(f"  web_name (col1): {row[1] if len(row)>1 else '?'}")
            found += 1
    print(f"\nTotal sample records found: {found}")
