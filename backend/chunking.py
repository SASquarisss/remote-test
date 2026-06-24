import hashlib
import re
from typing import Dict, List


SECTION_ORDER = [
    "basic_facts",
    "judgment_reason",
    "judgment_essence",
    "related_law",
    "related_info",
]


def _normalize_text(value: str) -> str:
    text = str(value or "").replace("\ufeff", "").strip()
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _doc_ref(raw_text: str, row: Dict[str, str]) -> str:
    seed = (
        row.get("id")
        or row.get("storage_no")
        or row.get("web_name")
        or hashlib.sha1((raw_text or "").encode("utf-8")).hexdigest()[:12]
    )
    return f"manual_{hashlib.sha1(str(seed).encode('utf-8')).hexdigest()[:12]}"


def _split_paragraphs(text: str) -> List[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text or "") if part.strip()]
    if paragraphs:
        return paragraphs
    text = _normalize_text(text)
    return [text] if text else []


def _split_sentences(text: str, max_len: int = 260) -> List[str]:
    text = _normalize_text(text)
    if not text:
        return []
    if len(text) <= max_len:
        return [text]

    pieces = []
    current = ""
    for part in re.split(r"(?<=[。！？；;])", text):
        part = part.strip()
        if not part:
            continue
        if current and len(current) + len(part) > max_len:
            pieces.append(current.strip())
            current = part
        else:
            current = f"{current}{part}"
    if current.strip():
        pieces.append(current.strip())
    return pieces or [text]


def _find_offsets(raw_text: str, parts: List[str]) -> List[Dict[str, int]]:
    results: List[Dict[str, int]] = []
    cursor = 0
    lowered = raw_text or ""
    for part in parts:
        idx = lowered.find(part, cursor)
        if idx == -1:
            idx = lowered.find(part)
        if idx == -1:
            results.append({"char_start": -1, "char_end": -1})
            continue
        end = idx + len(part)
        cursor = end
        results.append({"char_start": idx, "char_end": end})
    return results


def segment_case_text(raw_text: str, row: Dict[str, str], *, version: str = "v1") -> Dict[str, object]:
    normalized_raw = _normalize_text(raw_text)
    doc_ref = _doc_ref(normalized_raw, row)
    chunks: List[Dict[str, object]] = []
    global_seq = 1

    sections = []
    for section_name in SECTION_ORDER:
        section_text = _normalize_text(row.get(section_name, ""))
        if section_text:
            sections.append((section_name, section_text))

    if not sections and normalized_raw:
        sections = [("full_text", normalized_raw)]

    for section_name, section_text in sections:
        paragraphs = _split_paragraphs(section_text)
        paragraph_offsets = _find_offsets(normalized_raw, paragraphs)
        section_seq = 1
        for paragraph_index, paragraph in enumerate(paragraphs, start=1):
            sentence_pieces = _split_sentences(paragraph)
            sentence_offsets = _find_offsets(paragraph, sentence_pieces)
            base_offset = paragraph_offsets[paragraph_index - 1]["char_start"]
            for local_idx, piece in enumerate(sentence_pieces, start=1):
                local_offset = sentence_offsets[local_idx - 1]
                char_start = -1 if base_offset < 0 or local_offset["char_start"] < 0 else base_offset + local_offset["char_start"]
                char_end = -1 if base_offset < 0 or local_offset["char_end"] < 0 else base_offset + local_offset["char_end"]
                chunks.append({
                    "chunk_id": f"{doc_ref}:{section_name}:{section_seq:03d}",
                    "doc_ref": doc_ref,
                    "section_type": section_name,
                    "seq": global_seq,
                    "section_seq": section_seq,
                    "paragraph_index": paragraph_index,
                    "text": piece,
                    "char_start": char_start,
                    "char_end": char_end,
                    "chunking_version": version,
                })
                global_seq += 1
                section_seq += 1

    return {
        "chunks": chunks,
        "meta": {
            "version": version,
            "strategy": "section_paragraph_sentence",
            "doc_ref": doc_ref,
            "chunk_count": len(chunks),
        },
    }
