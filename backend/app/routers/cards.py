from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Card
from app.schemas import CardOut

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/{card_id}", response_model=CardOut)
def get_card(card_id: int, db: Session = Depends(get_db)):
    card = db.get(Card, card_id)

    if not card:
        raise HTTPException(404, "Card not found.")

    return card