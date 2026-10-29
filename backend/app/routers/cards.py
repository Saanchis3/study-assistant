import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from groq import APIError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Card
from app.schemas import CardOut, CardUpdate, CardVerificationOut
from app.services.card_editing import apply_edit
from app.services.card_verification import verify_card
from app.services.provider_errors import (
    ProviderErrorKind,
    classify_provider_error,
)
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


@router.post(
    "/{card_id}/verify",
    response_model=CardVerificationOut,
)
def verify_card_endpoint(
    card_id: int,
    db: Session = Depends(get_db),
):
    card = db.get(Card, card_id)

    if not card:
        raise HTTPException(
            status_code=404,
            detail="Card not found.",
        )

    try:
        return verify_card(db, card_id)

    except ValueError as exc:
        db.rollback()
        logger.warning(
            "Verification validation failed for card %d: %s",
            card_id,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail="The verification response was invalid. Please try again later.",
        ) from exc

    except APIError as exc:
        db.rollback()
        decision = classify_provider_error(exc)
        logger.warning(
            "Verification provider error for card %d: %s",
            card_id,
            exc,
        )

        if decision.kind in (
            ProviderErrorKind.DAILY_QUOTA_EXHAUSTED,
            ProviderErrorKind.TEMPORARY_RATE_LIMIT,
            ProviderErrorKind.UNKNOWN,
        ):
            raise HTTPException(
                status_code=429,
                detail="The AI provider's limit was reached. Please try again later.",
            ) from exc

        raise HTTPException(
            status_code=502,
            detail="The AI provider is unavailable. Please try again later.",
        ) from exc

    except Exception as exc:
        db.rollback()
        logger.exception(
            "Verification failed for card %d",
            card_id,
        )
        raise HTTPException(
            status_code=502,
            detail="Card verification failed. Please try again later.",
        ) from exc