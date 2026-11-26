import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, HttpUrl, TypeAdapter, field_validator, model_validator

from app.config import settings

ALIAS_PATTERN: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_-]+$")
ALIAS_MIN_LENGTH: int = 3
ALIAS_MAX_LENGTH: int = 30
RESERVED_ALIASES: frozenset[str] = frozenset(
    {"api", "docs", "redoc", "openapi.json", "health", "admin", "login", "static"}
)

_http_url_adapter: TypeAdapter[HttpUrl] = TypeAdapter(HttpUrl)


class URLCreate(BaseModel):
    url: str
    custom_alias: Optional[str] = None

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, value: Any) -> str:
        if not isinstance(value, (str, HttpUrl)):
            raise ValueError("La URL debe ser un string")
        cleaned = str(value).strip()
        return str(_http_url_adapter.validate_python(cleaned))

    @field_validator("custom_alias", mode="before")
    @classmethod
    def validate_custom_alias(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("El alias debe ser un string")
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned.lower() in RESERVED_ALIASES:
            raise ValueError(f"El alias '{cleaned}' está reservado por el sistema")
        if not ALIAS_MIN_LENGTH <= len(cleaned) <= ALIAS_MAX_LENGTH:
            raise ValueError(
                f"El alias debe tener entre {ALIAS_MIN_LENGTH} y {ALIAS_MAX_LENGTH} caracteres"
            )
        if not ALIAS_PATTERN.fullmatch(cleaned):
            raise ValueError("El alias solo admite letras, números, '-' y '_'")
        return cleaned


class URLResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alias: str
    original_url: str
    short_url: str
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def build_short_url(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "short_url" not in data and "alias" in data:
                return {**data, "short_url": f"{settings.BASE_URL.rstrip('/')}/{data['alias']}"}
            return data
        alias = getattr(data, "alias", None)
        if alias is None:
            return data
        return {
            "alias": alias,
            "original_url": getattr(data, "original_url", None),
            "created_at": getattr(data, "created_at", None),
            "short_url": f"{settings.BASE_URL.rstrip('/')}/{alias}",
        }
