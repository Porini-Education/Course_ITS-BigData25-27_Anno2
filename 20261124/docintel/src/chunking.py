"""Split extracted document text into retrieval chunks.

Works on Document Intelligence Layout markdown (preferred) or on plain text.
Strategy: break on headings, bullets and blank lines, tidy whitespace, then
merge fragments that are too short to mean anything on their own.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAYOUT_MD = ROOT / "data" / "layout" / "r11_air_canada_itinerary.md"
FALLBACK_TXT = ROOT / "data" / "air_canada_text_fallback.txt"

BREAK = re.compile(r"\n\s*\n|\n\s*(?:[-*\u2022]|\d+\.)\s+|\n(?=#)")


def load_source_text() -> tuple[str, str]:
    """Prefer the Layout model's markdown; fall back to the plain-text copy."""
    if LAYOUT_MD.exists():
        return LAYOUT_MD.read_text(encoding="utf-8"), "layout markdown"
    return FALLBACK_TXT.read_text(encoding="utf-8"), "plain-text fallback"


def chunk_text(text: str, min_words: int = 8, max_words: int = 80) -> list[str]:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)      # layout page markers
    text = text.replace("\u2022", "\n\u2022 ")
    pieces = [re.sub(r"\s+", " ", p).strip(" #*-\u2022") for p in BREAK.split(text)]
    pieces = [p for p in pieces if p]
    chunks: list[str] = []
    buf = ""
    for p in pieces:
        buf = f"{buf} {p}".strip() if buf else p
        if len(buf.split()) >= min_words:
            words = buf.split()
            while len(words) > max_words:
                chunks.append(" ".join(words[:max_words]))
                words = words[max_words:]
            chunks.append(" ".join(words))
            buf = ""
    if buf:
        chunks.append(buf)
    return chunks


# Questions with a phrase that must appear in a good answer chunk.
# Used to score retrieval methods against each other.
QUESTIONS = {
    "Can I get a refund if I cancel?": "non-refundable",
    "What happens if I miss my flight?": "no-show",
    "How much does it cost to change my flight?": "Change fee per direction",
    "Can I change to another flight on the day I travel?": "Same-day confirmed changes",
    "How much did I pay to choose my seats?": "Advance Seat Selection",
}


def is_relevant(chunk: str, phrase: str) -> bool:
    return phrase.lower() in chunk.lower()
