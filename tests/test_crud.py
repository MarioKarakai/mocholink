import pytest
from sqlalchemy.orm import Session

from app import crud
from app.models import URL
from app.schemas import URLCreate


def test_create_url_with_random_alias(db_session: Session) -> None:
    url_record = crud.create_url(db_session, URLCreate(url="https://example.com/page"))

    assert url_record.id is not None
    assert len(url_record.alias) == 7
    assert url_record.alias.isalnum()
    assert url_record.original_url == "https://example.com/page"
    assert url_record.is_active is True
    assert url_record.created_at.tzinfo is not None


def test_create_url_with_custom_alias(db_session: Session) -> None:
    url_record = crud.create_url(
        db_session, URLCreate(url="https://example.com", custom_alias="mi-alias")
    )

    assert url_record.alias == "mi-alias"
    assert crud.get_url_by_alias(db_session, "mi-alias") == url_record


def test_get_url_by_alias_returns_none_when_missing(db_session: Session) -> None:
    assert crud.get_url_by_alias(db_session, "no-existe") is None


def test_create_url_duplicate_custom_alias_raises(db_session: Session) -> None:
    crud.create_url(db_session, URLCreate(url="https://a.com", custom_alias="repetido"))

    with pytest.raises(crud.AliasAlreadyExistsError) as exc_info:
        crud.create_url(db_session, URLCreate(url="https://b.com", custom_alias="repetido"))

    assert exc_info.value.alias == "repetido"
    assert db_session.query(URL).count() == 1


def test_create_url_custom_alias_race_condition_raises(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simula que otra petición insertó el alias entre la comprobación y el commit.
    crud.create_url(db_session, URLCreate(url="https://a.com", custom_alias="carrera"))
    monkeypatch.setattr(crud, "get_url_by_alias", lambda db, alias: None)

    with pytest.raises(crud.AliasAlreadyExistsError):
        crud.create_url(db_session, URLCreate(url="https://b.com", custom_alias="carrera"))

    assert db_session.query(URL).count() == 1


def test_create_url_retries_on_random_alias_collision(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    crud.create_url(db_session, URLCreate(url="https://a.com", custom_alias="ocupado"))
    aliases = iter(["ocupado", "libre12"])
    monkeypatch.setattr(crud, "generate_random_alias", lambda: next(aliases))

    url_record = crud.create_url(db_session, URLCreate(url="https://b.com"))

    assert url_record.alias == "libre12"


def test_create_url_retries_on_integrity_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # La comprobación previa no ve la colisión, pero la restricción UNIQUE de la BD sí.
    crud.create_url(db_session, URLCreate(url="https://a.com", custom_alias="ocupado"))
    aliases = iter(["ocupado", "libre12"])
    monkeypatch.setattr(crud, "generate_random_alias", lambda: next(aliases))
    monkeypatch.setattr(crud, "get_url_by_alias", lambda db, alias: None)

    url_record = crud.create_url(db_session, URLCreate(url="https://b.com"))

    assert url_record.alias == "libre12"


def test_create_url_gives_up_after_max_attempts(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    crud.create_url(db_session, URLCreate(url="https://a.com", custom_alias="ocupado"))
    calls: list[int] = []

    def always_colliding() -> str:
        calls.append(1)
        return "ocupado"

    monkeypatch.setattr(crud, "generate_random_alias", always_colliding)

    with pytest.raises(crud.AliasGenerationError):
        crud.create_url(db_session, URLCreate(url="https://b.com"))

    assert len(calls) == crud.MAX_ALIAS_GENERATION_ATTEMPTS
