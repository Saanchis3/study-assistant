
import json

from sqlalchemy.orm import Session
from groq import Groq

from app.config import GROQ_API_KEY, MODEL_NAME
from app.models import Card, CardVerification


def verify_card(db: Session, card_id: int) -> CardVerification:
    card = db.get(Card, card_id)

    if not card:
        raise ValueError("Card not found")

    chunk = card.chunk
    client = Groq(api_key=GROQ_API_KEY)

    prompt = f"""
You are checking the factual accuracy of a study flashcard.

Use ONLY the source passage below. Do not use outside knowledge.
If the passage does not provide enough evidence to judge the answer,
return unable_to_verify.

SOURCE PASSAGE:
{chunk.text}

QUESTION:
{card.question}

ANSWER:
{card.answer}

Return ONLY valid JSON with this structure:
{{
  "status": "discrepancy" or "none_found" or "unable_to_verify",
  "explanation": "Brief explanation based on the source"
}}

Rules:
- discrepancy: the answer contradicts the source or contains unsupported factual claims.
- none_found: the answer is supported by the source.
- unable_to_verify: the source does not contain enough information.
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        reasoning_effort="low",
        include_reasoning=False,
        max_completion_tokens=1024,
    )

    content = response.choices[0].message.content

    if not content:
        raise ValueError("Verifier returned an empty response")

    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Verifier returned invalid JSON") from exc

    allowed_statuses = {
        "discrepancy",
        "none_found",
        "unable_to_verify",
    }

    status = result.get("status")

    if status not in allowed_statuses:
        raise ValueError("Verifier returned an invalid status")

    verification = CardVerification(
        card_id=card.id,
        status=status,
        explanation=str(result.get("explanation", "")),
        sources=[],
    )

    db.add(verification)
    db.commit()
    db.refresh(verification)

    return verification
