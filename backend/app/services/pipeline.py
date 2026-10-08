import logging
import time

from sqlalchemy import select

from app import config
from app.db import SessionLocal
from app.models import Card, Chunk, Document
from app.services.card_generation import (
    PROMPT_VERSION,
    CardGenerationError,
    generate_cards,
)


logger = logging.getLogger(__name__)


def generate_cards_for_document(document_id: int) -> None:
    """Runs in the background: makes cards for every chunk of a document."""
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        chunks = db.scalars(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        ).all()

        for i, chunk in enumerate(chunks):
            if i > 0:
                time.sleep(config.REQUEST_DELAY_SECONDS)

            try:
                cards = generate_cards(chunk.text)
            except CardGenerationError as e:
                logger.warning("Chunk %d failed: %s", chunk.chunk_index, e)
                doc.failed_chunks += 1
            else:
                for c in cards:
                    db.add(
                        Card(
                            chunk_id=chunk.id,
                            question=c.question,
                            answer=c.answer,
                            card_type=c.card_type,
                            source_quote=c.source_quote,
                            prompt_version=PROMPT_VERSION,
                        )
                    )

            doc.processed_chunks += 1
            db.commit()

        doc.status = "failed" if doc.failed_chunks == len(chunks) else "done"
        db.commit()

    except Exception as e:
        logger.exception("Document %d crashed", document_id)
        db.rollback()
        doc = db.get(Document, document_id)
        if doc:
            doc.status = "failed"
            doc.error = str(e)[:500]
            db.commit()

    finally:
        db.close()