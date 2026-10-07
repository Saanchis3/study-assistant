
import re
from dataclasses import dataclass

from app.services.parsing import PageText

TARGET_WORDS = 400
MAX_WORDS = 500
MIN_WORDS = 50


@dataclass
class Chunk:
    chunk_index: int
    text: str
    page_start: int
    page_end: int
    char_start: int
    char_end: int


@dataclass
class _Paragraph:
    text: str
    page: int
    start: int
    end: int


def _words(text: str) -> int:
    return len(text.split())


def _make_paragraphs(text, base, page, parts):
    """Turn text pieces into _Paragraph objects with their exact positions."""
    result = []
    cursor = 0
    for part in parts:
        part = part.strip()
        if not part:
            continue
        idx = text.find(part, cursor)
        if idx == -1:
            continue
        result.append(_Paragraph(part, page, base + idx, base + idx + len(part)))
        cursor = idx + len(part)
    return result


def _hard_split(par: _Paragraph):
    """Last resort: cut text with no punctuation into blocks of words."""
    words = list(re.finditer(r"\S+", par.text))
    pieces = []
    for i in range(0, len(words), TARGET_WORDS):
        group = words[i : i + TARGET_WORDS]
        s, e = group[0].start(), group[-1].end()
        pieces.append(_Paragraph(par.text[s:e], par.page, par.start + s, par.start + e))
    return pieces


def _split_long(par: _Paragraph):
    """Split an oversized paragraph into sentences (then words if needed)."""
    sentences = _make_paragraphs(
        par.text, par.start, par.page, re.split(r"(?<=[.!?])\s+", par.text)
    )
    result = []
    for s in sentences:
        if _words(s.text) > MAX_WORDS:
            result.extend(_hard_split(s))
        else:
            result.append(s)
    return result


def _split_page(page: PageText, base: int):
    parts = re.split(r"\n\s*\n", page.text)
    paragraphs = _make_paragraphs(page.text, base, page.page_number, parts)
    result = []
    for p in paragraphs:
        if _words(p.text) > MAX_WORDS:
            result.extend(_split_long(p))
        else:
            result.append(p)
    return result


def chunk_pages(pages: list[PageText]) -> list[Chunk]:
    paragraphs = []
    offset = 0
    for page in pages:
        paragraphs.extend(_split_page(page, offset))
        offset += len(page.text) + 2

    groups, current, count = [], [], 0
    for p in paragraphs:
        w = _words(p.text)
        if current and (count + w > MAX_WORDS or count >= TARGET_WORDS):
            groups.append(current)
            current, count = [], 0
        current.append(p)
        count += w
    if current:
        groups.append(current)

    if len(groups) > 1 and sum(_words(p.text) for p in groups[-1]) < MIN_WORDS:
        groups[-2].extend(groups.pop())

    return [
        Chunk(
            chunk_index=i,
            text="\n\n".join(p.text for p in group),
            page_start=group[0].page,
            page_end=group[-1].page,
            char_start=group[0].start,
            char_end=group[-1].end,
        )
        for i, group in enumerate(groups)
    ]
