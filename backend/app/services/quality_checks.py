
import re
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Card, Chunk


MAX_ANSWER_WORDS = 60
MIN_SUPPORT_OVERLAP = 0.5


@dataclass
class CardDraft:
    id: int
    question: str
    answer: str
    chunk_id: int = 0
    source_text: str = ""
    source_quote: str = ""
    edited: bool = False


@dataclass
class Flag:
    code: str
    message: str
    severity: str = "warning"


def _norm(text: str) -> str:
    """Normalize whitespace and capitalization for comparisons."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def _words(text: str) -> set[str]:
    """Return words longer than three characters for overlap checks."""
    return {
        word
        for word in re.findall(r"[a-z']+", text.casefold())
        if len(word) > 3
    }


def source_looks_garbled(text: str) -> bool:
    """Heuristically detect text that may have been extracted poorly."""
    lines = [line for line in text.splitlines() if line.strip()]

    if len(lines) < 20:
        return False

    single_word_lines = sum(
        1 for line in lines if len(line.split()) <= 1
    )

    return single_word_lines / len(lines) > 0.6


def find_flags(drafts: list[CardDraft]) -> dict[int, list[Flag]]:
    """Find suspicious patterns without modifying any flashcard."""
    found: dict[int, dict[str, Flag]] = defaultdict(dict)

    def add(
        card_id: int,
        code: str,
        message: str,
        severity: str = "warning",
    ) -> None:
        found[card_id].setdefault(
            code, Flag(code, message, severity)
        )

    by_question = defaultdict(list)
    by_answer = defaultdict(list)

    for draft in drafts:
        normalized_question = _norm(draft.question)
        normalized_answer = _norm(draft.answer)

        by_question[normalized_question].append(draft)

        if normalized_answer:
            by_answer[normalized_answer].append(draft)

    # 1. Repeated questions
    for group in by_question.values():
        if len(group) > 1:
            for draft in group:
                add(
                    draft.id,
                    "repeated_question",
                    "This question appears on multiple cards. "
                    "Check whether the repetition is intentional.",
                    "info",
                )

    # 2. Identical answers under different questions
    for group in by_answer.values():
        distinct_questions = {
            _norm(draft.question) for draft in group
        }

        if len(distinct_questions) < 2:
            continue

        for draft in group:
            others = [
                other
                for other in group
                if _norm(other.question) != _norm(draft.question)
            ]

            if not others:
                continue

            names = "; ".join(
                sorted({other.question for other in others})[:3]
            )

            same_chunk = any(
                other.chunk_id == draft.chunk_id
                for other in others
            )

            if same_chunk:
                add(
                    draft.id,
                    "shared_answer",
                    f"Same answer as another card in the same section "
                    f"({names}). Check whether this is intentional.",
                    "warning",
                )
            else:
                add(
                    draft.id,
                    "shared_answer",
                    f"Same answer as a card elsewhere in the document "
                    f"({names}). This may be legitimate. Check if unsure.",
                    "info",
                )

    # 3. Individual card checks
    for draft in drafts:
        answer = draft.answer.strip()

        if not answer:
            add(
                draft.id,
                "empty_answer",
                "This answer is empty or contains only whitespace.",
            )
            # Avoid treating an empty answer as a copied answer.
            copied = False
        elif draft.source_text:
            copied = _norm(answer) in _norm(draft.source_text)
        else:
            copied = False

        if draft.source_text:
            # Check whether the supporting quote appears in the source.
            if (
                draft.source_quote
                and _norm(draft.source_quote)
                not in _norm(draft.source_text)
            ):
                add(
                    draft.id,
                    "quote_not_found",
                    "The supporting quote was not found in the source. "
                    "Formatting differences or extraction problems may "
                    "explain this. Check the original notes.",
                )

            # A word overlap heuristic cannot prove correctness.
            # Edited answers are skipped because they may be paraphrases.
            if answer and not copied and not draft.edited:
                answer_words = _words(answer)
                source_words = _words(draft.source_text)

                if len(answer_words) >= 3:
                    overlap = (
                        len(answer_words & source_words)
                        / len(answer_words)
                    )

                    if overlap < MIN_SUPPORT_OVERLAP:
                        add(
                            draft.id,
                            "weak_support",
                            "Many words in this answer do not appear in "
                            "the source passage. It may still be a valid "
                            "paraphrase. Check it against the original notes.",
                        )

        # 4. Answers that are too long
        if len(answer.split()) > MAX_ANSWER_WORDS:
            add(
                draft.id,
                "too_long",
                "This answer is very long for a flashcard.",
                "info",
            )

    return {
        card_id: list(flags.values())
        for card_id, flags in found.items()
    }


def flag_document(db: Session, document_id: int) -> int:
    """Recheck one document's cards and persist their quality flags.

    This function changes only each card's flags attribute. Questions
    and answers are not rewritten.

    Returns the number of cards that have at least one flag.
    """
    rows = db.execute(
        select(Card, Chunk)
        .join(Chunk, Card.chunk_id == Chunk.id)
        .where(Chunk.document_id == document_id)
    ).all()

    if not rows:
        return 0

    drafts = [
        CardDraft(
            id=card.id,
            question=card.question,
            answer=card.answer,
            chunk_id=chunk.id,
            source_text=chunk.text,
            source_quote=card.source_quote or "",
            edited=card.edited_at is not None,
        )
        for card, chunk in rows
    ]

    result = find_flags(drafts)

    garbled_by_chunk: dict[int, bool] = {}
    flagged_count = 0

    for card, chunk in rows:
        card_flags = [
            {
                "code": flag.code,
                "message": flag.message,
                "page": chunk.page_start,
                "severity": flag.severity,
            }
            for flag in result.get(card.id, [])
        ]

        if chunk.id not in garbled_by_chunk:
            garbled_by_chunk[chunk.id] = source_looks_garbled(
                chunk.text or ""
            )

        if garbled_by_chunk[chunk.id]:
            card_flags.append(
                {
                    "code": "source_garbled",
                    "message": (
                        "The extracted text looks jumbled, with mostly "
                        "one word per line. This can also be a normal "
                        "word list. Check the original source."
                    ),
                    "page": chunk.page_start,
                    "severity": "warning",
                }
            )

        card.flags = card_flags

        if card_flags:
            flagged_count += 1

    db.commit()
    return flagged_count
