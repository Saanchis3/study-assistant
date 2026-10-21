import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Card
from app.schemas import CardOut, CardUpdate
from app.services.card_editing import apply_edit
from app.services.quality_checks import flag_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/{card_id}", response_model=CardOut)
def get_card(card_id: int, db: Session = Depends(get_db)):
    card = db.get(Card, card_id)

    if not card:
        raise HTTPException(status_code=404, detail="Card not found.")

    return card


@router.patch("/{card_id}", response_model=CardOut)
def edit_card(
    card_id: int,
    update: CardUpdate,
    db: Session = Depends(get_db),
):
    card = db.get(Card, card_id)

    if not card:
        raise HTTPException(status_code=404, detail="Card not found.")

    apply_edit(card, update.question, update.answer)
    db.commit()

    # Re-run quality checks so flags reflect the current card content.
    try:
        flag_document(db, card.chunk.document_id)
    except Exception:
        db.rollback()
        # The edit is already saved; only the flag refresh failed.
        logger.exception("Quality check failed for card %d", card_id)

    db.refresh(card)
    return card


@router.delete("/{card_id}", status_code=204)
def delete_card(card_id: int, db: Session = Depends(get_db)):
    card = db.get(Card, card_id)

    if not card:
        raise HTTPException(status_code=404, detail="Card not found.")

    db.delete(card)
    db.commit()

    return Response(status_code=204)
