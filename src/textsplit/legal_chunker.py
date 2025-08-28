from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Tuple


# Heuristics tailored for legal documents and land descriptions.
# We try to split on natural legal boundaries first (headings, exhibits, parcels,
# paragraphs that start with compass steps like "Thence"), then refine to
# sentence-like units that respect common legal abbreviations and bearing notations.


LEGAL_HEADING_PATTERNS: Sequence[re.Pattern[str]] = [
    re.compile(r"^\s*(EXHIBIT\s+[A-Z0-9]+)\s*$"),
    re.compile(r"^\s*(LEGAL\s+DESCRIPTION)\s*$"),
    re.compile(r"^\s*(DESCRIPTION)\s*$"),
    re.compile(r"^\s*(PARCEL\s+\d+|PARCEL\s+[A-Z])\b"),
    re.compile(r"^\s*(LOT\s+\d+[A-Z]?)\b"),
    re.compile(r"^\s*(TRACT\s+\w+)\b"),
    re.compile(r"^\s*(SECTION\s+\d+)\b"),
    re.compile(r"^\s*(TOWNSHIP\s+\w+|T\.?\s*\d+[NS]?)\b"),
    re.compile(r"^\s*(RANGE\s+\w+|R\.?\s*\d+[EW]?)\b"),
]

# Bearings like N 12°34'56" E, also tolerate no-seconds, and symbols variations.
BEARING_RE: re.Pattern[str] = re.compile(
    r"\b([NS])\s*\d{1,3}[°\s]\s*\d{1,2}(?:['′]\s*\d{1,2}(?:[\"″])?)?\s*([EW])\b",
    re.IGNORECASE,
)

# Common legal/measurement abbreviations to avoid splitting after.
ABBREVIATIONS: Sequence[str] = (
    "co.", "inc.", "ltd.", "no.", "sec.", "t.", "r.", "nw.", "ne.", "sw.", "se.",
    "ft.", "in.", "deg.", "min.", "sec.", "rd.", "ave.", "st.", "blvd.", "dr.", "hwy.",
)


def is_heading_line(line: str) -> bool:
    text = line.strip()
    if not text:
        return False
    if text.isupper() and len(text) <= 80:
        return True
    for pat in LEGAL_HEADING_PATTERNS:
        if pat.search(text):
            return True
    return False


def is_legal_step_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s.lower().startswith(("thence", "then", "beginning", "commencing")):
        return True
    if BEARING_RE.search(s):
        return True
    # Lines with distance + unit often indicate a step.
    if re.search(r"\b\d+(?:\.\d+)?\s*(feet|foot|ft|meters|meter|m)\b", s, re.IGNORECASE):
        return True
    return False


def split_into_sections(text: str) -> List[str]:
    # Split by blank-line groups while preserving headings as their own sections when possible
    lines = text.splitlines()
    sections: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        if is_heading_line(line):
            # Start a new section at headings
            if current:
                sections.append(current)
                current = []
            sections.append([line])
            continue
        if not line.strip():
            # Blank line separates paragraphs; defer full split to later but keep marker
            current.append("")
            continue
        current.append(line)
    if current:
        sections.append(current)

    # Join lines in each section, compressing multiple blank lines to two
    joined: List[str] = []
    for sec in sections:
        # If the section is a pure heading, keep as-is
        if len(sec) == 1 and is_heading_line(sec[0]):
            joined.append(sec[0].strip())
            continue
        # Normalize blank lines
        body = "\n".join(sec)
        body = re.sub(r"\n{3,}", "\n\n", body)
        joined.append(body.strip("\n"))
    # Merge adjacent tiny heading + body
    merged: List[str] = []
    i = 0
    while i < len(joined):
        if is_heading_line(joined[i]) and i + 1 < len(joined):
            merged.append(joined[i] + "\n\n" + joined[i + 1])
            i += 2
        else:
            merged.append(joined[i])
            i += 1
    return [s for s in merged if s.strip()]


def split_section_into_units(section: str) -> List[str]:
    # First consider paragraph breaks
    paragraphs = [p for p in section.split("\n\n") if p.strip()]
    units: List[str] = []
    for para in paragraphs:
        # If a paragraph appears to be a chain of steps, further split by semicolons
        if is_legal_step_line(para) or ";" in para:
            units.extend(split_legal_sentences(para))
        else:
            units.append(para)
    # Remove whitespace-only units
    return [u.strip() for u in units if u.strip()]


def split_legal_sentences(text: str) -> List[str]:
    # Split on strong punctuation that likely ends a step or sentence: ; . :
    # But avoid breaking after common abbreviations and inside bearings with quotes.
    spans: List[Tuple[int, int]] = []
    start = 0
    i = 0
    L = len(text)
    while i < L:
        ch = text[i]
        if ch in ";.:":
            # Look back for abbreviation token
            prev = text[max(0, i - 8):i].lower()
            if any(prev.endswith(abbr) for abbr in ABBREVIATIONS):
                i += 1
                continue
            # Bearings often contain quotes; don't break right after DMS tokens if next char is 
            # immediately a direction continuation.
            left = text[max(0, i - 30):i + 1]
            right = text[i + 1:i + 12]
            if BEARING_RE.search(left + right):
                i += 1
                continue
            end = i + 1
            spans.append((start, end))
            # Skip following whitespace
            j = end
            while j < L and text[j].isspace():
                j += 1
            start = j
            i = j
            continue
        i += 1
    if start < L:
        spans.append((start, L))
    parts = [text[a:b].strip() for a, b in spans]
    return [p for p in parts if p]


def assemble_chunks(
    units: Sequence[str],
    min_chars: int,
    target_chars: int,
    max_chars: int,
    overlap_chars: int,
) -> List[str]:
    chunks: List[str] = []
    buffer: List[str] = []
    buffer_len = 0

    def flush() -> None:
        nonlocal buffer, buffer_len
        if not buffer:
            return
        chunk = "\n\n".join(buffer).strip()
        if chunk:
            chunks.append(chunk)
        buffer = []
        buffer_len = 0

    for unit in units:
        sep = "\n\n" if buffer else ""
        candidate_len = buffer_len + len(sep) + len(unit)

        if candidate_len <= target_chars:
            buffer.append(sep + unit if sep else unit)
            buffer_len = candidate_len
            continue

        # If adding would exceed target; if current buffer is too small, allow overflow up to max
        if buffer_len < min_chars:
            buffer.append(sep + unit if sep else unit)
            buffer_len += len(sep) + len(unit)
            if buffer_len >= min_chars or buffer_len >= max_chars:
                flush()
            continue

        # Current buffer is healthy; flush, then start new with this unit
        flush()
        buffer = [unit]
        buffer_len = len(unit)

    if buffer_len:
        flush()

    # Add overlap by carrying tail of previous chunk into next chunk, at sentence boundary
    if overlap_chars > 0 and len(chunks) > 1:
        overlapped: List[str] = []
        for idx, chunk in enumerate(chunks):
            if idx == 0:
                overlapped.append(chunk)
                continue
            prev = overlapped[-1]
            tail = prev[-overlap_chars:]
            # Try to expand to the previous sentence boundary
            boundary = max(tail.rfind("\n\n"), tail.rfind(". "), tail.rfind("; "))
            if boundary != -1:
                tail = tail[boundary + 1 :]
            # Avoid duplicate whitespace
            merged = tail.strip() + ("\n\n" if tail.strip() else "") + chunk
            overlapped.append(merged)
        chunks = overlapped

    # Final guardrails: hard-cut giant outliers while preserving min
    normalized: List[str] = []
    for c in chunks:
        if len(c) <= max_chars:
            normalized.append(c)
            continue
        s = c
        start = 0
        L = len(s)
        while start < L:
            end = min(start + max_chars, L)
            piece = s[start:end]
            # Try to avoid cutting mid-token by backing to last whitespace
            if end < L:
                ws = piece.rfind(" ")
                if ws >= min_chars // 2:
                    end = start + ws
                    piece = s[start:end]
            normalized.append(piece)
            start = end
    return normalized


def _line_iter(text: str):
    start = 0
    for m in re.finditer(r".*?(\n|$)", text):
        end = m.end()
        yield start, text[start:end]
        start = end


def chunk_text_for_rag(
    text: str,
    min_chars: int = 600,
    target_chars: int = 1000,
    max_chars: int = 1400,
    overlap_chars: int = 150,
    by_section: bool = True,
) -> List[str]:
    # Always preserve original text; do not normalize newlines or spaces.
    if not text:
        return []

    n = len(text)
    # Build candidate breakpoints in original index space
    breaks: set[int] = {0, n}

    # Paragraph boundaries: after runs of >=2 newlines
    for m in re.finditer(r"\n{2,}", text):
        breaks.add(m.end())

    # Line-based headings or legal step starts
    for start, line in _line_iter(text):
        raw = line.rstrip("\n")
        if is_heading_line(raw) or is_legal_step_line(raw):
            if start not in (0, n):
                breaks.add(start)

    # Sentence/step punctuation boundaries (avoid abbreviations)
    for m in re.finditer(r"[;.:]", text):
        i = m.start()
        # Check abbreviations in preceding 8 chars
        prev = text[max(0, i - 8):i].lower()
        if any(prev.endswith(abbr) for abbr in ABBREVIATIONS):
            continue
        # Bearing proximity check
        left = text[max(0, i - 30):i + 1]
        right = text[i + 1:i + 12]
        if BEARING_RE.search(left + right):
            continue
        j = i + 1
        breaks.add(j)

    sorted_breaks = sorted(breaks)

    # Helper to get the best next boundary
    def next_boundary(start_idx: int) -> int:
        j_min = start_idx + min_chars
        j_target = min(start_idx + target_chars, n)
        j_max = min(start_idx + max_chars, n)

        # Find candidate <= target and >= min
        leq_target = [b for b in sorted_breaks if j_min <= b <= j_target]
        if leq_target:
            return max(leq_target)
        # Otherwise pick the smallest > target but <= max
        gt_target = [b for b in sorted_breaks if j_target < b <= j_max]
        if gt_target:
            return min(gt_target)
        # Fallback: hard cut at max
        return j_max

    chunks: List[str] = []
    i = 0
    while i < n:
        j = next_boundary(i)
        if j <= i:
            # Ensure progress
            j = min(i + max_chars, n)
        chunks.append(text[i:j])
        if j >= n:
            break
        # Overlap: move start back by overlap_chars, but not before 0
        i = max(0, j - overlap_chars)
        # Ensure we don't get stuck: if overlap is too large for tiny texts
        if i >= j:
            break
    return chunks


__all__ = [
    "chunk_text_for_rag",
    "split_into_sections",
    "split_section_into_units",
]


