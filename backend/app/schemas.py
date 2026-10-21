from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: str
    error: str | None
    total_chunks: int
    processed_chunks: int
    failed_chunks: int
    created_at: datetime


class FlagOut(BaseModel):
    code: str
    message: str
    page: int | None = None
    severity: str = "warning"

class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chunk_id: int
    question: str
    answer: str
    card_type: str
    source_quote: str
    prompt_version: str
    due_at: datetime
    edited_at: datetime | None = None
    original_answer: str | None = None
    flags: list[FlagOut] = []


class CardUpdate(BaseModel):
    question: str | None = Field(default=None, max_length=2000)
    answer: str | None = Field(default=None, max_length=4000)

    @field_validator("question", "answer")
    @classmethod
    def not_blank(cls, v):
        if v is not None and not v.strip():
            raise ValueError("must not be blank")
        return v

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.question is None and self.answer is None:
            raise ValueError("Provide a question, an answer, or both.")
        return self


class SourceOut(BaseModel):
    title: str | None = None
    url: str


class CardVerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    status: str  # discrepancy / none_found / unable_to_verify
    explanation: str
    sources: list[SourceOut] = []
    checked_at: datetime