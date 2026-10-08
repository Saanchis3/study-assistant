import json
import re

from pydantic import BaseModel, Field
from groq import Groq

from app.config import GROQ_API_KEY, MODEL_NAME


PROMPT_VERSION = "v1"


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
    """Check whether the source quote comes from the original chunk."""
    return _normalize(quote) in _normalize(chunk)


def extract_json(text: str) -> str:
    """Extract a JSON object from an LLM response."""
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

Create 3 to 8 high-quality flashcards from the most important information in the chunk.

For every flashcard:

1. QUESTION
- Ask one clear, focused study question.
- The question should test an important concept, person, event, term, date, feature, or significance.

2. ANSWER
- Give a concise but complete answer that is easy to memorize.
- Extract the KEY FACTS from the study material.
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
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "flashcard_batch",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "cards": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question": {"type": "string"},
                                    "answer": {"type": "string"},
                                    "card_type": {
                                        "type": "string",
                                        "enum": [
                                            "definition",
                                            "concept",
                                            "process",
                                            "example",
                                        ],
                                    },
                                    "source_quote": {"type": "string"},
                                },
                                "required": [
                                    "question",
                                    "answer",
                                    "card_type",
                                    "source_quote",
                                ],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["cards"],
                    "additionalProperties": False,
                },
            },
        },
        reasoning_format="hidden",
    )

    return response.choices[0].message.content


def generate_cards(chunk: str, max_retries: int = 2) -> list[Card]:
    """
    Generate validated flashcards from one document chunk.
    Invalid cards are filtered out.
    """

    last_error = None

    for _ in range(max_retries + 1):
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

    raise CardGenerationError(
        f"Failed to generate valid flashcards: {last_error}"
    )