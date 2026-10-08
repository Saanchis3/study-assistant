from fastapi.testclient import TestClient

from app.main import app


def test_unsupported_file_type_is_rejected():
    with TestClient(app) as client:
        r = client.post(
            "/documents",
            files={"file": ("notes.xyz", b"hello")},
        )

    assert r.status_code == 400


def test_missing_card_returns_404():
    with TestClient(app) as client:
        r = client.get("/cards/999999")

    assert r.status_code == 404
    