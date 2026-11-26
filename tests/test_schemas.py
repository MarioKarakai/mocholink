import pytest
from pydantic import ValidationError

from app.schemas import URLCreate
from app.utils import generate_random_alias


def test_url_is_stripped() -> None:
    assert URLCreate(url="  https://example.com/a  ").url == "https://example.com/a"


@pytest.mark.parametrize("bad_url", ["not-a-url", "ftp://example.com", "", "https://", 123])
def test_invalid_urls_are_rejected(bad_url: object) -> None:
    with pytest.raises(ValidationError):
        URLCreate(url=bad_url)  # type: ignore[arg-type]


@pytest.mark.parametrize("empty_alias", [None, "", "   "])
def test_empty_alias_becomes_none(empty_alias: str | None) -> None:
    assert URLCreate(url="https://example.com", custom_alias=empty_alias).custom_alias is None


def test_alias_is_stripped() -> None:
    assert URLCreate(url="https://example.com", custom_alias="  Abc_Z-9 ").custom_alias == "Abc_Z-9"


@pytest.mark.parametrize(
    "bad_alias", ["ab", "a" * 31, "con espacio", "x'; DROP TABLE urls;--", "ñandú", "a/b", 42]
)
def test_invalid_aliases_are_rejected(bad_alias: object) -> None:
    with pytest.raises(ValidationError):
        URLCreate(url="https://example.com", custom_alias=bad_alias)  # type: ignore[arg-type]


def test_generate_random_alias() -> None:
    alias = generate_random_alias(8)
    assert len(alias) == 8
    assert alias.isalnum()
    assert generate_random_alias() != generate_random_alias()


def test_generate_random_alias_rejects_non_positive_length() -> None:
    with pytest.raises(ValueError):
        generate_random_alias(0)
