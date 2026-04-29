"""
指导性案例 CSV 解析器（第三版 — 利用 id 在行首的特征合并多行字段）
"""
import csv
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple

HEADER = [
    "id", "web_name", "web_url", "case_type", "storage_no", "court_name",
    "key_words", "trial_procedure", "trial_year", "case_level",
    "basic_facts", "judgment_reason", "judgment_essence",
    "related_info", "related_law", "related_judgment_body",
    "create_time", "update_time", "md5_value", "judgment_mean", "dt"
]
EXPECTED_COLS = len(HEADER)


def robust_parse_tsv(path: Path) -> List[Dict]:
    """
    利用行首是否为数字 id 来判断新记录开始。
    非数字开头的行 = 前一行的延续（basic_facts / judgment_reason 中的换行符）。
    """
    raw_lines: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw_lines.append(line.rstrip("\n\r"))

    # 合并多行
    merged: List[str] = []
    current = ""
    for line in raw_lines:
        # 如果行首是纯数字（可选空白），则是新记录开始
        stripped = line.lstrip()
        if stripped and stripped.split(None, 1)[0].isdigit():
            if current:
                merged.append(current)
            current = line
        else:
            # 行首不是数字，是前一行的继续
            current += "\n" + line
    if current:
        merged.append(current)

    # 按 \t 分割每行
    rows: List[Dict] = []
    for line in merged:
        parts = line.split("\t")
        if len(parts) < EXPECTED_COLS:
            # 字段数不足，补空
            parts += [""] * (EXPECTED_COLS - len(parts))
        elif len(parts) > EXPECTED_COLS:
            # 字段数超出，多余的合并到最后一个字段
            parts = parts[:EXPECTED_COLS - 1] + ["\t".join(parts[EXPECTED_COLS - 1:])]
        rows.append(dict(zip(HEADER, parts)))

    return rows


def parse_date(raw: str) -> str:
    raw = raw.strip()
    if not raw or raw in ("\\N", ""):
        return ""
    raw = raw.replace("/", "-").replace(".", "-")
    parts = raw.split("-")
    if len(parts) == 3:
        y, m, d = parts
        try:
            return f"{int(y)}-{int(m):02d}-{int(d):02d}"
        except ValueError:
            return ""
    return ""


def extract_case_category(case_type: str) -> Tuple[str, str]:
    case_type = (case_type or "").strip()
    if "-" in case_type:
        return case_type.split("-", 1)
    return case_type, ""


def normalize_court_name(name: str) -> str:
    name = (name or "").strip()
    return name or "未知法院"


def parse_related_law(raw: str) -> List[Dict]:
    raw = raw or ""
    if raw in ("\\N", ""):
        return []
    laws = []
    pattern = r"《([^》]+)》第([零一二三四五六七八九十百千万\d]+)条(?:第([零一二三四五六七八九十百千万\d]+)款)?"
    for m in re.finditer(pattern, raw):
        laws.append({
            "law_name": m.group(1).strip(),
            "article": m.group(2).strip(),
            "paragraph": "",
            "item": m.group(3).strip() if m.group(3) else ""
        })
    return laws


def md5_id(prefix: str, *parts) -> str:
    content = "|".join(str(p) for p in parts)
    return f"{prefix}_{hashlib.md5(content.encode()).hexdigest()[:12]}"


def main():
    input_path = Path("data_samples/guiding_cases_raw.csv")
    output_dir = Path("data_lake/gold")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Parsing {input_path} ...")
    raw_rows = robust_parse_tsv(input_path)
    print(f"Parsed {len(raw_rows)} rows")

    guiding_cases: List[Dict] = []
    courts: Dict[str, Dict] = {}
    case_types: Dict[str, Dict] = {}
    provisions: Dict[str, Dict] = {}
    edges_cites: List[Dict] = []
    edges_guides: List[Dict] = []

    for row in raw_rows:
        row_id = (row.get("id") or "").strip()
        if not row_id or not row_id.isdigit():
            continue

        gc_id = f"guiding_case_{row_id}"
        case_type_raw = row.get("case_type") or "unknown"
        category, sub_type = extract_case_category(case_type_raw)

        # CaseType
        ct_id = md5_id("case_type", category, sub_type)
        if ct_id not in case_types:
            case_types[ct_id] = {
                "id": ct_id,
                "code": ct_id.replace("case_type_", ""),
                "name": sub_type or category,
                "category": category,
                "level1": category,
                "level2": sub_type,
                "source": "指导案例库分类",
                "desensitize": "false",
                "create_time": "2026-04-21T00:00:00Z",
                "update_time": "2026-04-21T00:00:00Z",
            }

        # Court
        court_name = normalize_court_name(row.get("court_name"))
        court_id = md5_id("court", court_name)
        if court_id not in courts:
            level = "supreme" if "最高" in court_name else "high" if "高级" in court_name else "intermediate" if "中级" in court_name else "basic"
            courts[court_id] = {
                "id": court_id,
                "name": court_name,
                "org_type": "court",
                "credit_code": md5_id("cc", court_name)[-18:],
                "court_level": level,
                "district_id": "",
                "source": "指导案例库",
                "desensitize": "false",
                "create_time": "2026-04-21T00:00:00Z",
                "update_time": "2026-04-21T00:00:00Z",
            }

        # GuidingCase
        pub_date = parse_date(row.get("trial_year") or "")
        case_level = (row.get("case_level") or "").strip()
        trial_level_map = {"1": "first_instance", "2": "second_instance", "": ""}
        trial_level = trial_level_map.get(case_level, "")

        web_name = (row.get("web_name") or "").strip()
        binding = "mandatory" if "人民法院案例库" in web_name else "persuasive"

        # 清理 judgment_essence 中的 HTML 标签
        essence = (row.get("judgment_essence") or "").strip()
        essence = re.sub(r'<[^>]+>', '', essence)  # 去除 HTML 标签
        essence = essence.replace("u3000", "\u3000").replace("\n", " ").replace("\r", " ")
        essence = essence[:2000]

        guiding_cases.append({
            "id": gc_id,
            "guiding_case_number": (row.get("storage_no") or "").strip(),
            "name": f"{case_type_raw}-{(row.get('storage_no') or '').strip()}",
            "issuing_court_id": court_id,
            "publication_date": pub_date,
            "guiding_points": essence,
            "binding_force": binding,
            "source_url": (row.get("web_url") or "").strip(),
            "tags": (row.get("key_words") or "").strip(),
            "trial_procedure": (row.get("trial_procedure") or "").strip(),
            "trial_level": trial_level,
            "source": web_name,
            "desensitize": "false",
            "create_time": "2026-04-21T00:00:00Z",
            "update_time": "2026-04-21T00:00:00Z",
        })

        edges_guides.append({
            "guiding_case_id": gc_id,
            "case_type_id": ct_id,
        })

        related_law = row.get("related_law") or ""
        for law in parse_related_law(related_law):
            prov_id = md5_id("provision", law["law_name"], law["article"], law["item"])
            if prov_id not in provisions:
                provisions[prov_id] = {
                    "id": prov_id,
                    "law_id": md5_id("law", law["law_name"]),
                    "article": law["article"],
                    "paragraph": law["paragraph"],
                    "item": law["item"],
                    "content": "",
                    "status": "effective",
                    "source": law["law_name"],
                    "desensitize": "false",
                    "create_time": "2026-04-21T00:00:00Z",
                    "update_time": "2026-04-21T00:00:00Z",
                }
            edges_cites.append({
                "case_id": gc_id,
                "provision_id": prov_id,
                "citation_position": "裁判要旨",
                "citation_purpose": "法律依据"
            })

    def write_csv(name: str, data: List[Dict]):
        if not data:
            print(f"Skipping empty {name}")
            return
        keys = list(data[0].keys())
        path = output_dir / name
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        print(f"Wrote {len(data)} rows to {path}")

    write_csv("GuidingCase.csv", guiding_cases)
    write_csv("Court.csv", list(courts.values()))
    write_csv("CaseType.csv", list(case_types.values()))
    write_csv("LegalProvision.csv", list(provisions.values()))
    write_csv("edges_GUIDES_CASE_TYPE.csv", edges_guides)
    write_csv("edges_CITES.csv", edges_cites)

    print("\nDone. 可以运行: python pipelines/bulk_import.py 导入到 Neo4j")


if __name__ == "__main__":
    main()
