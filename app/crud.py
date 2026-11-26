from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import URL
from app.schemas import URLCreate
from app.utils import generate_random_alias

MAX_ALIAS_GENERATION_ATTEMPTS: int = 3


class AliasAlreadyExistsError(Exception):
    def __init__(self, alias: str) -> None:
        super().__init__(f"El alias '{alias}' ya está en uso.")
        self.alias = alias


class AliasGenerationError(Exception):
    pass


def get_url_by_alias(db: Session, alias: str) -> Optional[URL]:
    return db.scalars(select(URL).where(URL.alias == alias)).first()


def _persist(db: Session, url_record: URL) -> URL:
    db.add(url_record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(url_record)
    return url_record


def create_url(db: Session, url_in: URLCreate) -> URL:
    if url_in.custom_alias is not None:
        if get_url_by_alias(db, url_in.custom_alias) is not None:
            raise AliasAlreadyExistsError(url_in.custom_alias)
        try:
            return _persist(db, URL(original_url=url_in.url, alias=url_in.custom_alias))
        except IntegrityError as exc:
            # Otra petición concurrente reservó el mismo alias entre la comprobación y el commit.
            raise AliasAlreadyExistsError(url_in.custom_alias) from exc

    for _ in range(MAX_ALIAS_GENERATION_ATTEMPTS):
        alias = generate_random_alias()
        if get_url_by_alias(db, alias) is not None:
            continue
        try:
            return _persist(db, URL(original_url=url_in.url, alias=alias))
        except IntegrityError:
            continue

    raise AliasGenerationError(
        f"No se pudo generar un alias único tras {MAX_ALIAS_GENERATION_ATTEMPTS} intentos"
    )
