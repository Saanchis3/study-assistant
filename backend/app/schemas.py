from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
    