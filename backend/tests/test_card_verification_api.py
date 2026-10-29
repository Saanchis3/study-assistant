import pytest
from fastapi.testclient import TestClient
from groq import RateLimitError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import httpx

from app.db import Base, get_db
from app.main import app
from app.models import Card, CardVerification, Chunk, Document
from app.routers import cards as cards_router


@pytest.fixture
def env():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    try:
        yield TestClient(app), Session
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()

def seed_card(Session) -> int:
    db = Session()
    doc = Document(filename="t.txt", status="done", total_chunks=1)
    db.add(doc)
    db.flush()
    chunk = Chunk(
        document_id=doc.id, chunk_index=0, text="Blithe means carefree.",
        page_start=1, page_end=1, char_start=0, char_end=1,
    )
    db.add(chunk)
    db.flush()
    card = Card(
        chunk_id=chunk.id, question="What does 'blithe' mean?",
        answer="carefree", card_type="definition",
        source_quote="Blithe means carefree.", prompt_version="test",
    )
    db.add(card)
    db.commit()
    card_id = card.id
    db.close()
    return card_id


def make_rate_limit_error(message: str) -> RateLimitError:
    request = httpx.Request("POST", "https://api.groq.com/test")
    response = httpx.Response(429, request=request)
    return RateLimitError(message, response=response, body=None)


def test_verify_success_returns_result(env, monkeypatch):
    client, Session = env
    card_id = seed_card(Session)

    def fake_verify(db, cid):
        v = CardVerification(
            card_id=cid, status="none_found",
            explanation="Supported by the source.", sources=[],
        )
        db.add(v)
        db.commit()
        db.refresh(v)
        return v

    monkeypatch.setattr(cards_router, "verify_card", fake_verify)
    r = client.post(f"/cards/{card_id}/verify")
    assert r.status_code == 200
    assert r.json()["status"] == "none_found"


def test_verify_missing_card_returns_404(env):
    client, _ = env
    assert client.post("/cards/999999/verify").status_code == 404


def test_verify_daily_quota_returns_429(env, monkeypatch):
    client, Session = env
    card_id = seed_card(Session)

    def fake_verify(db, cid):
        raise make_rate_limit_error(
            "Rate limit reached on tokens per day (TPD): Limit 200000"
        )

    monkeypatch.setattr(cards_router, "verify_card", fake_verify)
    r = client.post(f"/cards/{card_id}/verify")
    assert r.status_code == 429
    assert "200000" not in r.text  # raw provider text must not leak


def test_verify_invalid_output_returns_502(env, monkeypatch):
    client, Session = env
    card_id = seed_card(Session)

    def fake_verify(db, cid):
        raise ValueError("Verifier returned an invalid status")

    monkeypatch.setattr(cards_router, "verify_card", fake_verify)
    assert client.post(f"/cards/{card_id}/verify").status_code == 502


def test_verify_unexpected_error_returns_502(env, monkeypatch):
    client, Session = env
    card_id = seed_card(Session)

    def fake_verify(db, cid):
        raise RuntimeError("boom")

    monkeypatch.setattr(cards_router, "verify_card", fake_verify)
    assert client.post(f"/cards/{card_id}/verify").status_code == 502