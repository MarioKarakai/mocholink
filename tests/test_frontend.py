from pathlib import Path
from typing import Any

import httpx
import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "frontend" / "app.py")

SUCCESS_BODY: dict[str, str] = {
    "alias": "python-docs",
    "original_url": "https://python.org/",
    "short_url": "http://localhost:8000/python-docs",
    "created_at": "2026-10-27T19:59:44.211166Z",
}


def mock_backend(monkeypatch: pytest.MonkeyPatch, status_code: int, body: Any = None) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> httpx.Response:
        calls.append(json)
        return httpx.Response(status_code, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    return calls


def submit(url: str, alias: str = "") -> AppTest:
    at = AppTest.from_file(APP_PATH).run()
    return fill_and_submit(at, url, alias)


def fill_and_submit(at: AppTest, url: str, alias: str = "") -> AppTest:
    at.text_input(key="url_input").set_value(url)
    at.text_input(key="alias_input").set_value(alias)
    at.button[0].click()
    return at.run()


def test_initial_render_shows_empty_history() -> None:
    at = AppTest.from_file(APP_PATH).run()

    assert not at.exception
    assert at.session_state.history == []
    assert at.subheader[0].value == "Enlaces Creados Recientemente"
    assert len(at.info) == 1


def test_empty_url_does_not_call_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = mock_backend(monkeypatch, 201, SUCCESS_BODY)

    at = submit("   ")

    assert calls == []
    assert at.warning[0].value == "Introduce la URL que quieres acortar."


def test_success_adds_to_history(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = mock_backend(monkeypatch, 201, SUCCESS_BODY)

    at = submit(" https://python.org ", " python-docs ")

    assert not at.exception
    assert calls == [{"url": "https://python.org", "custom_alias": "python-docs"}]
    assert at.success[0].value == "¡Enlace acortado con éxito!"
    assert at.code[0].value == "http://localhost:8000/python-docs"
    assert at.session_state.history[0]["alias"] == "python-docs"
    assert len(at.info) == 0


def test_empty_alias_is_not_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = mock_backend(monkeypatch, 201, SUCCESS_BODY)

    submit("https://python.org")

    assert calls == [{"url": "https://python.org"}]


def test_newest_link_goes_first(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_backend(monkeypatch, 201, SUCCESS_BODY)
    at = submit("https://python.org", "python-docs")

    mock_backend(monkeypatch, 201, {**SUCCESS_BODY, "alias": "segundo", "short_url": "http://localhost:8000/segundo"})
    at = fill_and_submit(at, "https://python.org", "segundo")

    assert [item["alias"] for item in at.session_state.history] == ["segundo", "python-docs"]


def test_conflict_shows_error(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_backend(monkeypatch, 409, {"detail": "El alias 'x' ya está en uso. Elige otro."})

    at = submit("https://python.org", "ocupado")

    assert at.error[0].value == "El alias personalizado ya está ocupado. Intenta con otro."
    assert at.session_state.history == []


def test_validation_error_shows_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_backend(monkeypatch, 422, {"detail": []})

    at = submit("not-a-url")

    assert "http:// o https://" in at.warning[0].value
    assert at.session_state.history == []


@pytest.mark.parametrize("status_code,body", [(500, {"detail": "x"}), (503, None), (201, {"inesperado": 1})])
def test_server_errors_do_not_crash(monkeypatch: pytest.MonkeyPatch, status_code: int, body: Any) -> None:
    mock_backend(monkeypatch, status_code, body)

    at = submit("https://python.org")

    assert not at.exception
    assert "servidor" in at.error[0].value
    assert at.session_state.history == []


def test_connection_error_does_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(url: str, json: dict[str, Any], timeout: float) -> httpx.Response:
        raise httpx.ConnectError("conexión rechazada")

    monkeypatch.setattr(httpx, "post", fail)

    at = submit("https://python.org")

    assert not at.exception
    assert "No se pudo conectar" in at.error[0].value
