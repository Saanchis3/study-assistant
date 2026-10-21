import csv
import sys

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Card, Chunk, Document

# Usage: python export_for_rating.py [how_many] [prompt_version]
n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
version = sys.argv[2] if len(sys.argv) > 2 else None

db = SessionLocal()
query = (
    select(Card, Chunk, Document)
    .join(Chunk, Card.chunk_id == Chunk.id)
    .join(Document, Chunk.document_id == Document.id)
)

if version:
    query = query.where(Card.prompt_version == version)

query = query.where(Document.filename == "GregMat_Vocab_3.pdf")

rows = db.execute(query.order_by(func.random()).limit(n)).all()
filename = f"ratings_{version or 'all'}.csv"

with open(filename, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)

    writer.writerow([
        "card_id",
        "document",
        "pages",
        "card_type",
        "question",
        "answer",
        "source_quote",
        "prompt_version",
        "correct",
        "useful",
        "problem",
    ])

    for card, chunk, doc in rows:
        writer.writerow([
    card.id,
    doc.filename,
    f"pages {chunk.page_start} to {chunk.page_end}",
    card.card_type,
    " ".join(card.question.split()),
    " ".join(card.answer.split()),
    " ".join(card.source_quote.split()),
    card.prompt_version,
    "",
    "",
    "",
])

print(f"Wrote {len(rows)} cards to {filename}")

db.close()