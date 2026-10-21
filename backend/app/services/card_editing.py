from app.models import Card, now


def apply_edit(card: Card, question: str | None = None, answer: str | None = None) -> bool:
    """Edit a card without losing the original text.

    - Only the very first version of the question/answer is saved
      in original_question / original_answer.
    - Editing clears the card's quality flags, because the user has
      now reviewed it.
    Returns True if anything changed.
    """
    changed = False

    if question is not None and question.strip() != card.question:
        if card.original_question is None:
            card.original_question = card.question
        card.question = question.strip()
        changed = True

    if answer is not None and answer.strip() != card.answer:
        if card.original_answer is None:
            card.original_answer = card.answer
        card.answer = answer.strip()
        changed = True

    if changed:
        card.edited_at = now()


    return changed