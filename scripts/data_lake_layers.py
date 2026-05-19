"""
data_lake_layers.py

统一定义 data_lake 的文件分层规则。

当前最小分层：
1. extracted_*      -> 正式候选池（generate_prompt.py 默认只扫描这一层）
2. fewshot_cmp_* /
   compare*         -> 实验输出，不参与 few-shot 候选
3. manual_parsed    -> 人工保存结果
4. extracted_candidate_* -> 结构化 few-shot 候选池
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List


OFFICIAL_CANDIDATE_LAYER = "extracted"
STRUCTURED_CANDIDATE_LAYER = "extracted_candidate"
EXPERIMENT_LAYERS = {"fewshot_cmp", "compare"}
MANUAL_LAYER = "manual"


def classify_data_lake_layer(path: Path) -> str:
    name = path.name
    if name.startswith("extracted_candidate_"):
        return STRUCTURED_CANDIDATE_LAYER
    if name.startswith("extracted_"):
        return OFFICIAL_CANDIDATE_LAYER
    if name.startswith("fewshot_cmp_"):
        return "fewshot_cmp"
    if name.startswith("compare"):
        return "compare"
    if name == "manual_parsed.jsonl" or name.startswith("manual_"):
        return MANUAL_LAYER
    return "other"


def iter_data_lake_jsonl_files(data_lake_dir: Path) -> Iterable[Path]:
    return sorted(data_lake_dir.glob("*.jsonl"))


def get_data_lake_layer_files(data_lake_dir: Path, layer: str) -> List[Path]:
    return [p for p in iter_data_lake_jsonl_files(data_lake_dir) if classify_data_lake_layer(p) == layer]


def get_fewshot_candidate_files(data_lake_dir: Path) -> List[Path]:
    """
    few-shot 候选来源：
    1. extracted_candidate_* 结构化候选池
    2. extracted_* 正式历史池
    """
    files: List[Path] = []
    for layer in (STRUCTURED_CANDIDATE_LAYER, OFFICIAL_CANDIDATE_LAYER):
        files.extend(get_data_lake_layer_files(data_lake_dir, layer))
    return files


def summarize_data_lake_layers(data_lake_dir: Path) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for path in iter_data_lake_jsonl_files(data_lake_dir):
        layer = classify_data_lake_layer(path)
        counts[layer] = counts.get(layer, 0) + 1
    return counts
