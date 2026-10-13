import asyncio
import json
import threading
import webbrowser
from contextlib import AsyncExitStack
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx2
from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import (
    AuthorizationCodeResult,
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthToken,
)

FO_URL = "https://mcp.api.wajo.ai/fo"
CACHE_DIR = Path.home() / ".cache" / "embodied_fo"
TOKENS_FILE = CACHE_DIR / "tokens.json"
CLIENT_FILE = CACHE_DIR / "client.json"
CALLBACK_PORT = 3030
CALLBACK_URL = f"http://localhost:{CALLBACK_PORT}/callback"

_fresh_conversation = True
_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_stack: AsyncExitStack | None = None
_session: ClientSession | None = None


class FileStorage(TokenStorage):
    async def get_tokens(self):
        if not TOKENS_FILE.exists():
            return None
        return OAuthToken.model_validate_json(TOKENS_FILE.read_text())

    async def set_tokens(self, tokens):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        TOKENS_FILE.write_text(tokens.model_dump_json())

    async def get_client_info(self):
        if not CLIENT_FILE.exists():
            return None
        return OAuthClientInformationFull.model_validate_json(CLIENT_FILE.read_text())

    async def set_client_info(self, info):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CLIENT_FILE.write_text(info.model_dump_json())


async def _open_browser(url: str) -> None:
    print(f"\n[opening browser for Wajo sign-in: {url}]\n")
    webbrowser.open(url)


async def _wait_for_code() -> AuthorizationCodeResult:
    captured: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            q = parse_qs(urlparse(self.path).query)
            code = q.get("code", [None])[0]
            if code is None:
                self.send_response(204)
                self.end_headers()
                return
            captured["code"] = code
            captured["state"] = q.get("state", [None])[0]
            captured["iss"] = q.get("iss", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Signed in. You can close this tab.</h1>")

        def log_message(self, *_):
            pass

    server = HTTPServer(("localhost", CALLBACK_PORT), Handler)
    loop = asyncio.get_running_loop()
    while "code" not in captured:
        await loop.run_in_executor(None, server.handle_request)
    return AuthorizationCodeResult(
        code=captured["code"],
        state=captured.get("state"),
        iss=captured.get("iss"),
    )


def _build_oauth_provider() -> OAuthClientProvider:
    return OAuthClientProvider(
        server_url=FO_URL,
        client_metadata=OAuthClientMetadata(
            client_name="embodied_fo",
            redirect_uris=[CALLBACK_URL],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
        ),
        storage=FileStorage(),
        redirect_handler=_open_browser,
        callback_handler=_wait_for_code,
    )


def _extract_tool_result(result) -> dict:
    structured = getattr(result, "structured_content", None)
    if structured:
        return structured
    for item in result.content:
        text = getattr(item, "text", None)
        if text is None:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"status": "ready", "reply": text}
    return {}


async def _open_session() -> None:
    global _stack, _session
    _stack = AsyncExitStack()
    http = await _stack.enter_async_context(
        httpx2.AsyncClient(auth=_build_oauth_provider(), timeout=httpx2.Timeout(30, read=300))
    )
    read, write = await _stack.enter_async_context(
        streamable_http_client(FO_URL, http_client=http)
    )
    _session = await _stack.enter_async_context(ClientSession(read, write))
    await _session.initialize()


async def _ask(message: str) -> str:
    global _fresh_conversation
    payload: dict = {"message": message}
    if _fresh_conversation:
        payload["newConversation"] = True
        _fresh_conversation = False
    data = _extract_tool_result(await _session.call_tool("ask_fo", payload))
    while data.get("status") == "working":
        print(f"[fo working] {data}")
        data = _extract_tool_result(await _session.call_tool("get_fo_reply", {}))
    return data.get("response") or data.get("reply") or data.get("message") or ""


# Background event loop lets us expose sync start/ask_fo/stop while the
# MCP library underneath stays async.
def start() -> None:
    global _loop, _thread
    _loop = asyncio.new_event_loop()
    _thread = threading.Thread(target=_loop.run_forever, daemon=True)
    _thread.start()
    asyncio.run_coroutine_threadsafe(_open_session(), _loop).result()


def ask_fo(message: str) -> str:
    return asyncio.run_coroutine_threadsafe(_ask(message), _loop).result()


def stop() -> None:
    if _stack is not None:
        try:
            asyncio.run_coroutine_threadsafe(_stack.aclose(), _loop).result(timeout=5)
        except Exception:
            pass
    if _loop is not None:
        _loop.call_soon_threadsafe(_loop.stop)
    if _thread is not None:
        _thread.join(timeout=5)


def sign_out() -> None:
    TOKENS_FILE.unlink(missing_ok=True)
