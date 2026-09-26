"""Tests for core/mcp_proxy.py — publishing the MCP server under Ember's host."""

import httpx
import pytest

from core.mcp_proxy import McpProxy, is_mcp_path

UPSTREAM = "http://127.0.0.1:8766"


class _Stream(httpx.AsyncByteStream):
    """Body iterator for mock responses.

    ``httpx.Response(content=...)`` is preloaded and refuses to stream, so mock
    handlers build responses from a stream to match a real transport.
    """

    def __init__(self, chunks):
        self._chunks = [chunks] if isinstance(chunks, bytes) else list(chunks)

    async def __aiter__(self):
        for chunk in self._chunks:
            yield chunk


def _streaming_response(status=200, headers=None, body=b"", chunks=None):
    return httpx.Response(
        status,
        headers=headers,
        stream=_Stream(chunks if chunks is not None else body),
    )


async def _call(app, method="GET", path="/mcp", headers=None, body=b"", query=b""):
    """Drive an ASGI app once and return the messages it sent."""
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query,
        "headers": raw_headers,
        "scheme": "https",
        "client": ("203.0.113.9", 51234),
        "server": ("ember.bhm.li", 443),
    }

    sent = []
    state = {"consumed": False}

    async def receive():
        if state["consumed"]:
            return {"type": "http.disconnect"}
        state["consumed"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    return sent


def _body_of(sent) -> bytes:
    return b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")


def _status_of(sent) -> int:
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


def _headers_of(sent) -> dict[str, str]:
    start = next(m for m in sent if m["type"] == "http.response.start")
    return {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in start["headers"]}


class TestIsMcpPath:
    @pytest.mark.parametrize(
        "path",
        [
            "/mcp",
            "/mcp/",
            "/login",
            "/authorize",
            "/token",
            "/register",
            "/revoke",
            "/.well-known/oauth-authorization-server",
            "/.well-known/oauth-protected-resource/mcp",
        ],
    )
    def test_mcp_owned_paths_match(self, path):
        assert is_mcp_path(path)

    @pytest.mark.parametrize(
        "path",
        ["/", "/jobs/", "/api/hello", "/mlogin", "/mcpfoo", "/cr/links/", "/static/x.css"],
    )
    def test_application_paths_do_not_match(self, path):
        assert not is_mcp_path(path)


class TestPassthrough:
    async def test_non_mcp_path_reaches_django(self):
        seen = {}

        async def django_app(scope, receive, send):
            seen["path"] = scope["path"]
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"django"})

        proxy = McpProxy(django_app, upstream_url=UPSTREAM)
        sent = await _call(proxy, path="/jobs/")

        assert seen["path"] == "/jobs/"
        assert _status_of(sent) == 200
        assert _body_of(sent) == b"django"

    async def test_websocket_scope_bypasses_proxy(self):
        seen = {}

        async def django_app(scope, receive, send):
            seen["type"] = scope["type"]

        proxy = McpProxy(django_app, upstream_url=UPSTREAM)
        await proxy({"type": "websocket", "path": "/ws/chat/x/"}, None, None)

        assert seen["type"] == "websocket"


class TestForwarding:
    def _proxy(self, handler, django_app=None):
        async def _django(scope, receive, send):  # pragma: no cover - not reached
            raise AssertionError("Django should not be called for MCP paths")

        return McpProxy(
            django_app or _django,
            upstream_url=UPSTREAM,
            transport=httpx.MockTransport(handler),
        )

    async def test_forwards_mcp_request_and_returns_response(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["url"] = str(request.url)
            return _streaming_response(
                401,
                headers={
                    "www-authenticate": 'Bearer scope="mcp", '
                    'resource_metadata="https://ember.bhm.li/'
                    '.well-known/oauth-protected-resource/mcp"',
                    "content-type": "application/json",
                },
                body=b'{"detail":"unauthorized"}',
            )

        sent = await _call(
            self._proxy(handler),
            path="/mcp",
            headers={"host": "ember.bhm.li", "accept": "application/json"},
        )

        assert captured["method"] == "GET"
        assert captured["url"] == f"{UPSTREAM}/mcp"
        assert _status_of(sent) == 401
        assert _body_of(sent) == b'{"detail":"unauthorized"}'
        assert "www-authenticate" in _headers_of(sent)

    async def test_public_host_header_is_preserved_upstream(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["host"] = request.headers.get("host")
            captured["xfh"] = request.headers.get("x-forwarded-host")
            captured["xfp"] = request.headers.get("x-forwarded-proto")
            return _streaming_response(200, body=b"ok")

        await _call(
            self._proxy(handler),
            path="/mcp",
            headers={"host": "ember.bhm.li", "x-forwarded-proto": "https"},
        )

        # The MCP host guard validates the hostname the client used, not the
        # loopback address the upstream is bound to.
        assert captured["host"] == "ember.bhm.li"
        assert captured["xfh"] == "ember.bhm.li"
        assert captured["xfp"] == "https"

    async def test_query_string_and_body_are_forwarded(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["query"] = request.url.query.decode()
            captured["body"] = request.content
            captured["content_type"] = request.headers.get("content-type")
            return _streaming_response(200, body=b"{}")

        await _call(
            self._proxy(handler),
            method="POST",
            path="/mcp",
            headers={
                "host": "ember.bhm.li",
                "content-type": "application/json",
                "content-length": "19",
            },
            body=b'{"jsonrpc":"2.0"}',
            query=b"session=abc",
        )

        assert captured["query"] == "session=abc"
        assert captured["body"] == b'{"jsonrpc":"2.0"}'
        assert captured["content_type"] == "application/json"

    async def test_bodyless_get_sends_no_body_upstream(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["content"] = request.content
            captured["transfer_encoding"] = request.headers.get("transfer-encoding")
            return _streaming_response(200, body=b"ok")

        await _call(self._proxy(handler), path="/.well-known/oauth-authorization-server")

        # A GET must not acquire chunked framing from an empty body iterator.
        assert captured["content"] == b""
        assert captured["transfer_encoding"] is None

    async def test_hop_by_hop_headers_are_stripped(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return _streaming_response(
                200,
                headers={
                    "connection": "keep-alive",
                    "keep-alive": "timeout=5",
                    "transfer-encoding": "chunked",
                    "content-type": "application/json",
                },
                body=b"{}",
            )

        sent = await _call(self._proxy(handler), path="/mcp")
        headers = _headers_of(sent)

        assert "connection" not in headers
        assert "keep-alive" not in headers
        assert "transfer-encoding" not in headers
        assert headers["content-type"] == "application/json"

    async def test_client_address_chain_keeps_cloudflare_hop(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["xff"] = request.headers.get("x-forwarded-for")
            return _streaming_response(200, body=b"ok")

        await _call(
            self._proxy(handler),
            path="/mcp",
            headers={"host": "ember.bhm.li", "x-forwarded-for": "198.51.100.7"},
        )

        # Cloudflare's hop stays first; the direct peer is appended.
        assert captured["xff"] == "198.51.100.7, 203.0.113.9"

    async def test_upstream_failure_returns_502(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        sent = await _call(self._proxy(handler), path="/mcp")

        assert _status_of(sent) == 502
        assert b"MCP server unavailable" in _body_of(sent)


class TestSettings:
    def test_proxy_enabled_and_upstream_from_settings(self, settings):
        settings.MCP_PROXY_ENABLED = True
        settings.MCP_UPSTREAM_URL = "http://127.0.0.1:9999"
        proxy = McpProxy(object(), upstream_url=settings.MCP_UPSTREAM_URL)
        assert proxy.upstream_url == "http://127.0.0.1:9999"

    def test_asgi_application_wraps_django_when_enabled(self, settings):
        import importlib

        import config.asgi as asgi_module

        settings.MCP_PROXY_ENABLED = True
        reloaded = importlib.reload(asgi_module)
        http_app = reloaded.application.application_mapping["http"]
        assert isinstance(http_app, McpProxy)

    def test_asgi_application_uses_django_when_disabled(self, settings):
        import importlib

        import config.asgi as asgi_module

        settings.MCP_PROXY_ENABLED = False
        reloaded = importlib.reload(asgi_module)
        http_app = reloaded.application.application_mapping["http"]
        assert not isinstance(http_app, McpProxy)

        settings.MCP_PROXY_ENABLED = True
        importlib.reload(asgi_module)
