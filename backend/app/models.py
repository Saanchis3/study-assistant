from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="processing")
    error: Mapped[str | None] = mapped_column(Text, default=None)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    processed_chunks: Mapped[int] = mapped_column(Integer, default=0)
    failed_chunks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)

    document: Mapped["Document"] = relationship(back_populates="chunks")
    cards: Mapped[list["Card"]] = relationship(back_populates="chunk")


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("chunks.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    card_type: Mapped[str] = mapped_column(String(20))
    source_quote: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(String(20))
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    chunk: Mapped["Chunk"] = relationship(back_populates="cards")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    rating: Mapped[int] = mapped_column(Integer)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    interval_before: Mapped[int] = mapped_column(Integer, default=0)
    ease_before: Mapped[float] = mapped_column(Float, default=2.5)