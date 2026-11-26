import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud
from app.config import settings
from app.database import get_db
from app.models import URL
from app.schemas import URLCreate, URLResponse
from app.templates import render_not_found_page

api_router = APIRouter(prefix="/api/v1", tags=["urls"])
redirect_router = APIRouter(tags=["redirect"])


def verify_admin_secret(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = settings.ADMIN_SECRET.strip()
    if not expected:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clave de acceso inválida o ausente.",
        )


@api_router.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@api_router.get(
    "/urls",
    response_model=list[URLResponse],
    dependencies=[Depends(verify_admin_secret)],
)
def list_recent_urls(limit: int = 20, db: Session = Depends(get_db)) -> list[URLResponse]:
    stmt = select(URL).where(URL.is_active.is_(True)).order_by(URL.created_at.desc()).limit(limit)
    records = db.scalars(stmt).all()
    return [URLResponse.model_validate(r) for r in records]


@api_router.post(
    "/shorten",
    response_model=URLResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_admin_secret)],
    responses={status.HTTP_409_CONFLICT: {"description": "El alias personalizado ya está en uso"}},
)
def shorten_url(url_in: URLCreate, db: Session = Depends(get_db)) -> URLResponse:
    try:
        url_record = crud.create_url(db, url_in)
    except crud.AliasAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El alias '{exc.alias}' ya está en uso. Elige otro.",
        ) from exc
    except crud.AliasGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo generar un enlace corto. Inténtalo de nuevo.",
        ) from exc
    return URLResponse.model_validate(url_record)


@redirect_router.api_route(
    "/{alias}",
    methods=["GET", "HEAD"],
    response_class=RedirectResponse,
    response_model=None,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    responses={status.HTTP_404_NOT_FOUND: {"content": {"text/html": {}}}},
)
def redirect_to_original(alias: str, db: Session = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    url_record = crud.get_url_by_alias(db, alias)
    if url_record is None or not url_record.is_active:
        return HTMLResponse(
            content=render_not_found_page(alias), status_code=status.HTTP_404_NOT_FOUND
        )
    return RedirectResponse(
        url=url_record.original_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )
