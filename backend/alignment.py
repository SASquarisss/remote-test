import re
from typing import Any, Dict, List, Tuple


COLLECTION_FIELDS: Dict[str, Tuple[str, ...]] = {
    "facts": ("content",),
    "dispute_focuses": ("content", "focus_issue", "focus"),
    "litigation_claims": ("claim_text", "content"),
    "procedural_opinions": ("content", "opinion_text"),
    "argument_points": ("argument_text", "content", "reason"),
    "judicial_assessments": ("assessment_text", "content"),
    "evidence": ("content", "name", "text"),
    "judgment_results": ("specific_judgment", "reasoning", "content"),
    "legal_provisions": ("content", "article", "statute"),
    "legal_provision_elements": ("content", "name"),
    "legal_subjects": ("name", "content"),
    "attorneys": ("name", "content"),
}


def _normalize_text(value: Any) -> str:
    text = str(value or "").replace("\ufeff", "").strip()
    text = re.sub(r"\s+", "", text)
    return text


def _shorten(text: str, max_len: int = 48) -> str:
    text = re.sub(r"\s+", " ", str(text or "").strip())
    return text[:max_len]


def _extract_item_text(item: Dict[str, Any], keys: Tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        if value:
            return str(value).strip()
    return ""


def _match_item_to_chunks(text: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    exact_matches = []
    fuzzy_matches = []
    for chunk in chunks:
        chunk_text = str(chunk.get("text") or "")
        normalized_chunk = _normalize_text(chunk_text)
        if not normalized_chunk:
            continue
        if normalized in normalized_chunk:
            exact_matches.append({
                "chunk_id": chunk.get("chunk_id"),
                "score": 1.0,
                "match_type": "contains",
            })
            continue

        overlap = min(len(normalized), len(normalized_chunk))
        if overlap >= 12:
            prefix = normalized[:overlap]
            if prefix and prefix in normalized_chunk:
                fuzzy_matches.append({
                    "chunk_id": chunk.get("chunk_id"),
                    "score": round(overlap / max(len(normalized), 1), 3),
                    "match_type": "fuzzy",
                })

    if exact_matches:
        return exact_matches[:3]
    fuzzy_matches.sort(key=lambda item: item["score"], reverse=True)
    return fuzzy_matches[:3]


def align_output_to_chunks(output: Dict[str, Any], chunks: List[Dict[str, Any]], row: Dict[str, Any]) -> Dict[str, Any]:
    del row  # reserved for future section-aware alignment
    source_alignment: Dict[str, List[Dict[str, Any]]] = {}
    unmatched_items: List[Dict[str, Any]] = []
    aligned_count = 0

    for collection, text_fields in COLLECTION_FIELDS.items():
        items = output.get(collection) or []
        if not isinstance(items, list):
            continue
        label = collection[:-1] if collection.endswith("s") else collection
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            item_id = item.get("id") or item.get("stable_id") or f"{collection}_{index}"
            item_text = _extract_item_text(item, text_fields)
            if not item_text:
                continue
            matches = _match_item_to_chunks(item_text, chunks)
            node_key = f"{label}:{item_id}"
            if matches:
                source_alignment[node_key] = matches
                aligned_count += 1
            else:
                unmatched_items.append({
                    "node_key": node_key,
                    "collection": collection,
                    "preview": _shorten(item_text),
                })

    return {
        "source_alignment": source_alignment,
        "unmatched_items": unmatched_items,
        "stats": {
            "aligned_items": aligned_count,
            "unmatched_items": len(unmatched_items),
            "chunk_count": len(chunks),
        },
    }
