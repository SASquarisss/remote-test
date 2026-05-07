#!/usr/bin/env python3
"""
数据修复脚本：修复 batch_process.py 引起的数据问题
- 清除 GuidingCase.csv 中 1089/1109 的重复行
- 重建 LegalProvision.csv 和 edges_CITES.csv 的跨批次一致性
"""
import csv
import hashlib
import sys
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict

GOLD_DIR = Path("/root/.hermes/hermes-agent/remote-test/data_lake/gold")


def md5_id(prefix: str, *parts) -> str:
    content = "|".join(str(p) for p in parts)
    return f"{prefix}_{hashlib.md5(content.encode()).hexdigest()[:12]}"


def load_csv(path: Path) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, data: List[Dict]):
    if not data:
        return
    keys = list(data[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(data)
    print(f"  Wrote {len(data)} rows to {path.name}")


def fix_guiding_case_duplicates():
    """清除 GuidingCase.csv 中的重复行"""
    print("\n=== Fix: GuidingCase.csv 重复行清理 ===")
    rows = load_csv(GOLD_DIR / "GuidingCase.csv")
    print(f"  Before: {len(rows)} rows")
    
    seen = set()
    deduped = []
    dupes_removed = 0
    for row in rows:
        rid = row.get("id", "")
        if rid in seen:
            dupes_removed += 1
            print(f"  Removing duplicate: {rid}")
        else:
            seen.add(rid)
            deduped.append(row)
    
    print(f"  Removed {dupes_removed} duplicate rows")
    write_csv(GOLD_DIR / "GuidingCase.csv", deduped)


def fix_cites_duplicates():
    """清除 edges_CITES.csv 中的重复边"""
    print("\n=== Fix: edges_CITES.csv 重复边清理 ===")
    rows = load_csv(GOLD_DIR / "edges_CITES.csv")
    print(f"  Before: {len(rows)} rows")
    
    seen = set()
    deduped = []
    dupes_removed = 0
    for row in rows:
        key = (row.get("case_id", ""), row.get("provision_id", ""))
        if key in seen:
            dupes_removed += 1
            print(f"  Removing duplicate: {key}")
        else:
            seen.add(key)
            deduped.append(row)
    
    print(f"  Removed {dupes_removed} duplicate edges")
    write_csv(GOLD_DIR / "edges_CITES.csv", deduped)


def rebuild_legal_provisions():
    """
    重新构建 LegalProvision.csv：
    从 edges_CITES.csv 中提取所有 provision_id，
    反向推导 provision 的元数据（通过搜索 case 的 related_law）
    """
    print("\n=== Fix: LegalProvision.csv 重建 ===")
    
    # 先尝试从 GuidingCase.csv 反推
    guiding_cases = load_csv(GOLD_DIR / "GuidingCase.csv")
    cites_edges = load_csv(GOLD_DIR / "edges_CITES.csv")
    existing_provisions = load_csv(GOLD_DIR / "LegalProvision.csv")
    
    # 收集所有被引用的 provision_id
    all_cited_provision_ids = set()
    case_to_provision_ids = defaultdict(set)
    for edge in cites_edges:
        pid = edge.get("provision_id", "")
        cid = edge.get("case_id", "")
        if pid and cid:
            all_cited_provision_ids.add(pid)
            case_to_provision_ids[cid].add(pid)
    
    # 已有的 provision
    existing_by_id = {p["id"]: p for p in existing_provisions}
    
    # 找出缺失的 provision
    missing_ids = all_cited_provision_ids - set(existing_by_id.keys())
    print(f"  Total cited provision_ids: {len(all_cited_provision_ids)}")
    print(f"  Existing in LegalProvision.csv: {len(existing_by_id)}")
    print(f"  Missing (orphan in edges): {len(missing_ids)}")
    
    if not missing_ids:
        print("  No missing provisions to restore!")
        return
    
    # 尝试从 case 的 related_law 字段反向推导
    case_by_id = {c["id"]: c for c in guiding_cases}
    
    rebuilt_count = 0
    for missing_pid in sorted(missing_ids):
        # Find which cases reference this provision
        referencing_cases = []
        for cid, pids in case_to_provision_ids.items():
            if missing_pid in pids:
                referencing_cases.append(cid)
        
        if not referencing_cases:
            print(f"  WARNING: {missing_pid} has no referencing case, cannot rebuild")
            continue
        
        # 取第一个引用 case 的 related_law 字段尝试解析
        # 注意：由于 provision_id 是 md5(law_name, article, item) 生成的，
        # 我们无法逆转 hash，只能创建一个占位行
        sample_case = case_by_id.get(referencing_cases[0], {})
        law_text = sample_case.get("related_law", "")
        
        # Parse law name from the _ prefix of provision_id? No, we can't reverse md5.
        # Create a placeholder with minimal info
        existing_by_id[missing_pid] = {
            "id": missing_pid,
            "law_id": f"law_unknown_{missing_pid[-12:]}",
            "article": "",
            "paragraph": "",
            "item": "",
            "content": "",
            "status": "effective",
            "source": f"rebuilt_from_case_{referencing_cases[0]}",
            "desensitize": "false",
            "create_time": "2026-04-21T00:00:00Z",
            "update_time": "2026-04-21T00:00:00Z",
        }
        rebuilt_count += 1
        print(f"  {missing_pid}: rebuilt (placeholder, ref by {referencing_cases[0]})")
    
    print(f"  Rebuilt {rebuilt_count} provisions (with placeholder data)")
    print(f"  WARNING: These have empty article/content — need manual enrichment")
    write_csv(GOLD_DIR / "LegalProvision.csv", list(existing_by_id.values()))


def main():
    print("=" * 60)
    print("Data Repair Script for batch_process.py QA Issues")
    print("=" * 60)
    
    fix_guiding_case_duplicates()
    fix_cites_duplicates()
    rebuild_legal_provisions()
    
    print("\n" + "=" * 60)
    print("Repair complete!")
    print("=" * 60)
    print("\nPost-repair verification:")
    print("  guids = set()")
    print("  with open('data_lake/gold/GuidingCase.csv') as f:")
    print("    for row in csv.DictReader(f): guids.add(row['id'])")
    print(f"  print(f'Unique GuidingCases: {{len(guids)}}')  # Should be 130")


if __name__ == "__main__":
    main()
