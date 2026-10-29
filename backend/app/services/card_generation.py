import json
import re
import time

from pydantic import BaseModel
from groq import Groq

from app.config import GROQ_API_KEY, MODEL_NAME
from app.services.provider_errors import (
    ProviderErrorKind,
    classify_provider_error,
)


PROMPT_VERSION = "v3"
RETRY_DELAY_SECONDS = 3


class Card(BaseModel):
    question: str
    answer: str
    card_type: str
    source_quote: str


class CardBatch(BaseModel):
    cards: list[Card]


class CardGenerationError(Exception):
    pass


def _normalize(text: str) -> str:
    """Normalize whitespace for quote checking."""
    return re.sub(r"\s+", " ", text).strip()


def quote_is_in_chunk(quote: str, chunk: str) -> bool:
    """Check whether a non-empty source quote comes from the original chunk."""
    return bool(quote.strip()) and _normalize(quote) in _normalize(chunk)


def extract_json(text: str) -> str:
    """Extract a JSON object from an LLM response."""
    if not text or not text.strip():
        raise CardGenerationError("LLM returned an empty response.")

    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise CardGenerationError("No JSON object found in LLM response.")

    return text[start : end + 1]


def _get_client() -> Groq:
    if not GROQ_API_KEY:
        raise CardGenerationError("GROQ_API_KEY is not set.")

    return Groq(api_key=GROQ_API_KEY)


def _ask_llm(chunk: str) -> str:
    client = _get_client()

    prompt = f"""
You are an AI study assistant creating flashcards from a student's study guide.

Use ONLY the information provided in the study material.
Do not add outside knowledge.

Your goal is to make the material EASY TO STUDY, REMEMBER, and MEMORIZE for an exam.

Create flashcards from the study material.

If the material is a vocabulary list, create one separate flashcard
for EVERY word and its definition in the chunk. Do not skip any words.

If the material is general study notes, create 3 to 8 high-quality
flashcards from the most important information.

For every flashcard:

1. QUESTION
- Ask one clear, focused study question.
- The question should test an important concept, person, event, term, date, feature, or significance.

2. ANSWER
- Give a concise but complete answer that is easy to memorize.
- Extract the KEY FACTS from the study material.
- For definition cards, make the definition match the study material exactly in meaning; never guess or use an outside definition.
- For vocabulary lists, treat each word and its definition as a separate entry.
- Never combine a word's definition with the definition of a neighboring word, even if the extracted text appears continuous.
- If you cannot confidently identify where a definition ends and the next word's definition begins, do not create a card for that word.
- Include important:
  - dates or years
  - names of important people
  - places
  - defining features
  - important numbers
  - causes or effects
  - significance
  when they are relevant to the topic.
- Do NOT include every detail from the study material.
- Do NOT simply copy the source.
- Do NOT turn the entire paragraph into an answer.
- Compress the important information into a short study-friendly answer.
- Use semicolons or commas to separate key facts when helpful.
- The answer should normally be 1–3 short sentences or a compact set of facts.

3. CARD TYPE
card_type must be exactly one of:
- definition
- concept
- process
- example

4. SOURCE QUOTE
- Copy the relevant text EXACTLY from the study material.
- The source quote is for verification and citation.
- It should contain the information supporting the answer.
- Do not invent or modify the source quote.

IMPORTANT:
Think like a student preparing for an exam.

Before creating each card, ask yourself:
"What are the most important facts I would actually need to remember about this topic?"

Prioritize information that is likely to be tested, especially:
- dates
- names
- important places
- definitions
- distinguishing features
- important numbers
- major developments
- significance

Do NOT make a separate card for every tiny fact.
Combine closely related facts when they belong to the same topic.

Example:

Study material:
"Urania (1761, Philadelphia): first tunebook addressing both congregation and choir; published by subscription; first American tunebook to bring psalmody into the commercial arena."

Good card:

Question:
"What was significant about Urania?"

Answer:
"1761, Philadelphia — first tunebook for both congregation and choir; published by subscription; first American tunebook to bring psalmody into the commercial arena."

Source quote:
"Urania (1761, Philadelphia): first tunebook addressing both congregation and choir; published by subscription; first American tunebook to bring psalmody into the commercial arena."

Return ONLY valid JSON.

Use exactly this structure:

{{
  "cards": [
    {{
      "question": "string",
      "answer": "string",
      "card_type": "definition",
      "source_quote": "exact text from the study material"
    }}
  ]
}}

Study material:

{chunk}
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0.2,
        reasoning_effort="low",
        include_reasoning=False,
        max_completion_tokens=4096,
    )

    choice = response.choices[0]
    message = choice.message

    if not message.content:
        raise CardGenerationError(
            f"Groq returned empty content. "
            f"finish_reason={choice.finish_reason!r}, "
            f"reasoning_present={bool(getattr(message, 'reasoning', None))}, "
            f"refusal={getattr(message, 'refusal', None)!r}"
        )

    return message.content


def generate_cards(chunk: str, max_retries: int = 2) -> list[Card]:
    """
    Generate validated flashcards from one document chunk.
    Invalid cards are filtered out.
    Retries failed attempts with a delay.
    """

    last_error = None
    attempts = max_retries + 1

    for attempt in range(attempts):
        try:
            raw_response = _ask_llm(chunk)
            json_text = extract_json(raw_response)

            data = json.loads(json_text)
            batch = CardBatch.model_validate(data)

            valid_cards = []

            for card in batch.cards:
                if card.card_type not in {
                    "definition",
                    "concept",
                    "process",
                    "example",
                }:
                    continue

                if not card.question.strip():
                    continue

                if not card.answer.strip():
                    continue

                if not quote_is_in_chunk(card.source_quote, chunk):
                    continue

                valid_cards.append(card)

            if not valid_cards:
                raise CardGenerationError(
                    "No valid flashcards remained after validation."
                )

            return valid_cards
        except Exception as e:
            last_error = e

            # Only Groq errors are classified. Bad JSON, validation errors and
            # "no valid cards" are model-output problems, so they just retry.
            if isinstance(e, APIError):
                decision = classify_provider_error(e)

                if decision.kind == ProviderErrorKind.DAILY_QUOTA_EXHAUSTED:
                    raise CardGenerationError(
                        f"Groq daily quota exhausted: {decision.message}"
                    ) from e

                if decision.kind in (
                    ProviderErrorKind.TEMPORARY_RATE_LIMIT,
                    ProviderErrorKind.UNKNOWN,
                ):
                    raise CardGenerationError(
                        f"Groq rate limit or unknown provider error: {decision.message}"
                    ) from e

                if decision.kind == ProviderErrorKind.PERMANENT_ERROR:
                    raise CardGenerationError(
                        f"Groq provider error: {decision.message}"
                    ) from e

            # Transient provider errors and model-output errors: retry
            if attempt < attempts - 1:
                time.sleep(RETRY_DELAY_SECONDS)

    raise CardGenerationError(
        f"Failed to generate valid flashcards: {last_error}"
    ) from last_error
