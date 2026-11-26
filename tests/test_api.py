import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import crud
from app.config import settings
from app.main import app
from app.models import URL

SHORTEN_ENDPOINT = "/api/v1/shorten"


def test_shorten_url_success(client: TestClient) -> None:
    response = client.post(
        SHORTEN_ENDPOINT, json={"url": "https://python.org", "custom_alias": "python-docs"}
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"alias", "original_url", "short_url", "created_at"}
    assert body["alias"] == "python-docs"
    assert body["original_url"] == "https://python.org/"
    assert body["short_url"] == f"{settings.BASE_URL}/python-docs"
    assert body["created_at"]


def test_shorten_url_with_random_alias(client: TestClient) -> None:
    response = client.post(SHORTEN_ENDPOINT, json={"url": "https://python.org"})

    assert response.status_code == 201
    assert len(response.json()["alias"]) == 7


def test_shorten_url_invalid_format(client: TestClient) -> None:
    response = client.post(SHORTEN_ENDPOINT, json={"url": "not-a-url"})

    assert response.status_code == 422


def test_shorten_url_invalid_alias(client: TestClient) -> None:
    response = client.post(
        SHORTEN_ENDPOINT, json={"url": "https://python.org", "custom_alias": "mal alias!"}
    )

    assert response.status_code == 422


def test_shorten_url_duplicate_alias(client: TestClient) -> None:
    payload = {"url": "https://python.org", "custom_alias": "repetido"}
    assert client.post(SHORTEN_ENDPOINT, json=payload).status_code == 201

    response = client.post(SHORTEN_ENDPOINT, json=payload)

    assert response.status_code == 409
    assert response.json() == {"detail": "El alias 'repetido' ya está en uso. Elige otro."}


def test_shorten_url_alias_generation_exhausted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(db: Session, url_in: object) -> URL:
        raise crud.AliasGenerationError("sin alias")

    monkeypatch.setattr(crud, "create_url", fail)

    response = client.post(SHORTEN_ENDPOINT, json={"url": "https://python.org"})

    assert response.status_code == 503


def test_redirect_success(client: TestClient) -> None:
    client.post(SHORTEN_ENDPOINT, json={"url": "https://python.org/doc", "custom_alias": "docs-py"})

    response = client.get("/docs-py")

    assert response.status_code == 307
    assert response.headers["location"] == "https://python.org/doc"


def test_redirect_head_request(client: TestClient) -> None:
    client.post(SHORTEN_ENDPOINT, json={"url": "https://python.org", "custom_alias": "head-py"})

    response = client.head("/head-py")

    assert response.status_code == 307
    assert response.headers["location"] == "https://python.org/"


def test_redirect_not_found(client: TestClient) -> None:
    response = client.get("/alias-inexistente")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "alias-inexistente" in response.text


def test_redirect_not_found_escapes_alias(client: TestClient) -> None:
    response = client.get("/<img src=x onerror=alert(1)>")

    assert response.status_code == 404
    assert "<img src=x onerror=alert(1)>" not in response.text
    assert "&lt;img src=x onerror=alert(1)&gt;" in response.text


def test_redirect_inactive_url_returns_404(client: TestClient, db_session: Session) -> None:
    client.post(SHORTEN_ENDPOINT, json={"url": "https://python.org", "custom_alias": "inactivo"})
    url_record = crud.get_url_by_alias(db_session, "inactivo")
    assert url_record is not None
    url_record.is_active = False
    db_session.commit()

    response = client.get("/inactivo")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")


def test_unhandled_exception_returns_generic_500(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(db: Session, alias: str) -> URL:
        raise RuntimeError("detalle interno sensible")

    monkeypatch.setattr(crud, "get_url_by_alias", boom)

    with TestClient(app, raise_server_exceptions=False) as safe_client:
        response = safe_client.get("/cualquiera")

    assert response.status_code == 500
    assert response.json() == {"detail": "Error interno del servidor."}
    assert "sensible" not in response.text


def test_data_isolation_between_tests(db_session: Session) -> None:
    # Ningún test anterior debe haber dejado filas: cada uno usa una BD en memoria nueva.
    assert db_session.query(URL).count() == 0
