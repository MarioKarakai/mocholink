import base64
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional, TypedDict

import httpx
import streamlit as st

BACKEND_URL: str = os.getenv("MOCHOLINK_BACKEND_URL", "http://localhost:8000").rstrip("/")
REQUIRE_AUTH: bool = os.getenv("MOCHOLINK_REQUIRE_AUTH", "").lower() in {"1", "true", "yes"}
SHORTEN_ENDPOINT: str = f"{BACKEND_URL}/api/v1/shorten"
URLS_ENDPOINT: str = f"{BACKEND_URL}/api/v1/urls"
REQUEST_TIMEOUT_SECONDS: float = 10.0
ORIGINAL_URL_MAX_CHARS: int = 50
THEME_CSS_PATH: Path = Path(__file__).with_name("theme.css")

MSG_SUCCESS = "¡Enlace acortado con éxito!"
MSG_EMPTY_URL = "Introduce la URL que quieres acortar."
MSG_CONFLICT = "El alias personalizado ya está ocupado. Intenta con otro."
MSG_UNAUTHORIZED = "Clave de acceso incorrecta. Verifica tu contraseña de administrador."
MSG_INVALID = "Verifica que la URL ingresada sea válida (debe incluir http:// o https://)."
MSG_SERVER_ERROR = "El servidor tuvo un problema al procesar la solicitud. Inténtalo de nuevo en unos segundos."
MSG_CONNECTION_ERROR = (
    f"No se pudo conectar con el servidor de MochoLink ({BACKEND_URL}). "
    "Comprueba que el backend esté en marcha."
)


class HistoryItem(TypedDict):
    original: str
    short: str
    alias: str
    created_at: str


ResultKind = Literal["success", "conflict", "unauthorized", "invalid", "server_error", "connection_error"]


@dataclass(frozen=True)
class ShortenResult:
    kind: ResultKind
    item: Optional[HistoryItem] = None


def _auth_headers(api_key: str) -> dict[str, str]:
    cleaned = api_key.strip()
    return {"X-API-Key": cleaned} if cleaned else {}


def fetch_recent_urls(api_key: str) -> tuple[bool, list[HistoryItem]]:
    try:
        kwargs: dict[str, Any] = {"timeout": REQUEST_TIMEOUT_SECONDS}
        headers = _auth_headers(api_key)
        if headers:
            kwargs["headers"] = headers
        response = httpx.get(URLS_ENDPOINT, **kwargs)
    except httpx.HTTPError:
        return False, []

    if response.status_code != 200:
        return False, []

    try:
        rows = response.json()
        items: list[HistoryItem] = [
            HistoryItem(
                original=str(row["original_url"]),
                short=str(row["short_url"]),
                alias=str(row["alias"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]
        return True, items
    except (ValueError, KeyError, TypeError):
        return False, []


def shorten_url(url: str, custom_alias: str, api_key: str = "") -> ShortenResult:
    payload: dict[str, str] = {"url": url.strip()}
    if custom_alias.strip():
        payload["custom_alias"] = custom_alias.strip()

    try:
        kwargs: dict[str, Any] = {"json": payload, "timeout": REQUEST_TIMEOUT_SECONDS}
        headers = _auth_headers(api_key)
        if headers:
            kwargs["headers"] = headers
        response = httpx.post(SHORTEN_ENDPOINT, **kwargs)
    except httpx.HTTPError:
        return ShortenResult("connection_error")

    if response.status_code == 201:
        try:
            data = response.json()
            item = HistoryItem(
                original=str(data["original_url"]),
                short=str(data["short_url"]),
                alias=str(data["alias"]),
                created_at=str(data["created_at"]),
            )
        except (ValueError, KeyError, TypeError):
            return ShortenResult("server_error")
        return ShortenResult("success", item)
    if response.status_code == 401:
        return ShortenResult("unauthorized")
    if response.status_code == 409:
        return ShortenResult("conflict")
    if response.status_code >= 500:
        return ShortenResult("server_error")
    return ShortenResult("invalid")


def truncate(text: str, max_chars: int = ORIGINAL_URL_MAX_CHARS) -> str:
    return text if len(text) <= max_chars else f"{text[: max_chars - 1]}…"


def format_created_at(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


CREST_SVG: str = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    '<g fill="none" stroke-linecap="round">'
    '<g stroke="#6B4423" stroke-width="8">'
    '<rect x="5" y="23" width="32" height="18" rx="9" transform="rotate(-35 21 32)"/>'
    '<rect x="27" y="23" width="32" height="18" rx="9" transform="rotate(-35 43 32)"/></g>'
    '<g stroke="#D4AF37" stroke-width="4.5">'
    '<rect x="5" y="23" width="32" height="18" rx="9" transform="rotate(-35 21 32)"/>'
    '<rect x="27" y="23" width="32" height="18" rx="9" transform="rotate(-35 43 32)"/></g>'
    "</g></svg>"
)
CREST_DATA_URI: str = "data:image/svg+xml;base64," + base64.b64encode(CREST_SVG.encode()).decode()


def apply_theme() -> None:
    st.html(f"<style>{THEME_CSS_PATH.read_text(encoding='utf-8')}</style>")


def render_header() -> None:
    st.html(
        f"""
        <header class="ml-header">
          <img class="ml-crest" src="{CREST_DATA_URI}" alt="" />
          <h1 class="ml-title">MochoLink</h1>
          <p class="ml-tagline">Forja enlaces breves que viajan lejos, de una comarca a otra.</p>
          <div class="ml-flourish">&#x269C;&#xFE0E;</div>
        </header>
        """
    )


def ensure_authenticated() -> str:
    if "api_key" not in st.session_state:
        st.session_state.api_key = ""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = not REQUIRE_AUTH
    if "loaded_initial" not in st.session_state:
        st.session_state.loaded_initial = False

    if not st.session_state.authenticated:
        with st.form("auth_form", border=True):
            secret_input = st.text_input(
                "Clave de administrador",
                type="password",
                placeholder="Ingresa tu ADMIN_SECRET",
            )
            unlock = st.form_submit_button("Entrar", type="primary", use_container_width=True)

        if unlock:
            ok, items = fetch_recent_urls(secret_input)
            if ok:
                st.session_state.api_key = secret_input.strip()
                st.session_state.authenticated = True
                st.session_state.loaded_initial = True
                st.session_state.history = items
                st.rerun()
            else:
                st.error(MSG_UNAUTHORIZED)
        st.stop()

    if not st.session_state.loaded_initial:
        st.session_state.loaded_initial = True
        ok, items = fetch_recent_urls(str(st.session_state.api_key))
        if ok and items:
            st.session_state.history = items

    return str(st.session_state.api_key)


def render_form(api_key: str) -> None:
    with st.form("shorten_form", clear_on_submit=False, border=True):
        url = st.text_input(
            "URL larga *",
            placeholder="https://ejemplo.com/mi-link-muy-largo",
            key="url_input",
        )
        custom_alias = st.text_input(
            "Alias personalizado (opcional)",
            placeholder="mi-alias-genial",
            help="Entre 3 y 30 caracteres: letras, números, guiones (-) y guiones bajos (_).",
            key="alias_input",
        )
        submitted = st.form_submit_button("Acortar enlace", type="primary", use_container_width=True)

    if not submitted:
        return
    if not url.strip():
        st.warning(MSG_EMPTY_URL)
        return

    with st.spinner("Acortando enlace…"):
        result = shorten_url(url, custom_alias, api_key=api_key)

    if result.kind == "success" and result.item is not None:
        st.session_state.history = [
            item for item in st.session_state.history if item["alias"] != result.item["alias"]
        ]
        st.session_state.history.insert(0, result.item)
        st.success(MSG_SUCCESS)
        st.code(result.item["short"], language=None)
        st.caption(
            "Copia el enlace con el botón de la esquina del recuadro y compártelo: "
            "quien lo abra será redirigido a la URL original."
        )
    elif result.kind == "unauthorized":
        st.error(MSG_UNAUTHORIZED)
    elif result.kind == "conflict":
        st.error(MSG_CONFLICT)
    elif result.kind == "invalid":
        st.warning(MSG_INVALID)
    elif result.kind == "connection_error":
        st.error(MSG_CONNECTION_ERROR)
    else:
        st.error(MSG_SERVER_ERROR)


def render_history() -> None:
    st.divider()
    st.subheader("Enlaces Creados Recientemente")

    history: list[HistoryItem] = st.session_state.history
    if not history:
        st.info("Aún no has acortado ningún enlace en esta sesión. ¡Prueba con el formulario de arriba!")
        return

    for index, item in enumerate(history):
        with st.container(border=True, key=f"ml-card-{index}"):
            col_short, col_original = st.columns([2, 3], vertical_alignment="center")
            with col_short:
                st.markdown(f"**[{item['short']}]({item['short']})**")
                st.caption(format_created_at(item["created_at"]))
            with col_original:
                st.text(truncate(item["original"]))


def main() -> None:
    st.set_page_config(page_title="MochoLink", page_icon="📜", layout="centered")
    if "history" not in st.session_state:
        st.session_state.history = []

    apply_theme()
    render_header()
    api_key = ensure_authenticated()
    render_form(api_key)
    render_history()


main()
