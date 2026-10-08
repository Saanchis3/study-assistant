import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Card, Chunk, Document
from app.schemas import CardOut, DocumentOut
from app.services.chunking import chunk_pages
from app.services.parsing import ParsingError, parse_file
from app.services.pipeline import generate_cards_for_document

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_TYPES = {".pdf", ".docx", ".txt", ".md"}
MAX_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("", response_model=DocumentOut, status_code=202)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    suffix = Path(file.filename or "").suffix.lower()

    if suffix not in ALLOWED_TYPES:
        raise HTTPException(
            400,
            f"Unsupported file type. Use: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    content = file.file.read(MAX_BYTES + 1)

    if len(content) > MAX_BYTES:
        raise HTTPException(413, "File is too large (limit 20 MB).")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        pages = parse_file(tmp_path)
        chunks = chunk_pages(pages)
    except ParsingError as e:
        raise HTTPException(400, str(e))
    finally:
        tmp_path.unlink(missing_ok=True)

    if not chunks:
        raise HTTPException(400, "No usable text found in this file.")

    doc = Document(
        filename=file.filename,
        status="processing",
        total_chunks=len(chunks),
    )

    db.add(doc)
    db.flush()

    for c in chunks:
        db.add(
            Chunk(
                document_id=doc.id,
                chunk_index=c.chunk_index,
                text=c.text,
                page_start=c.page_start,
                page_end=c.page_end,
                char_start=c.char_start,
                char_end=c.char_end,
            )
        )

    db.commit()
    db.refresh(doc)

    background_tasks.add_task(generate_cards_for_document, doc.id)

    return doc


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)

    if not doc:
        raise HTTPException(404, "Document not found.")

    return doc


@router.get("/{document_id}/cards", response_model=list[CardOut])
def list_cards(document_id: int, db: Session = Depends(get_db)):
    if not db.get(Document, document_id):
        raise HTTPException(404, "Document not found.")

    return db.scalars(
        select(Card)
        .join(Chunk, Card.chunk_id == Chunk.id)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index, Card.id)
    ).all()