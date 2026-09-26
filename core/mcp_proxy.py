"""Publish the Fireman MCP server under Ember's public hostname.

The MCP server is a separate process that binds ``127.0.0.1:8766`` only, on
purpose: it must never listen on a public interface. Ember's public hostname
reaches this Daphne process, so the MCP paths are forwarded from here instead
of widening the MCP bind address.

Requests for any other path fall through to Django untouched.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("core.mcp_proxy")

# Paths owned by the MCP server: the streamable-HTTP endpoint plus the OAuth
# 2.1 surface it acts as authorization server for.
MCP_PATH_PREFIXES = (
    "/mcp",
    "/login",
    "/authorize",
    "/token",
    "/register",
    "/revoke",
    "/.well-known/oauth-authorization-server",
    "/.well-known/oauth-protected-resource",
)

# RFC 7230 hop-by-hop headers. These describe a single connection, so they must
# not be passed along to the upstream server.
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)

# Length and framing headers are recomputed by the HTTP client from the actual
# body, so forwarding the originals would risk a mismatch.
_FRAMING = frozenset({"content-length", "host"})

# Proxy headers are rebuilt below from the client's connection details.
# Passing the originals through as well would emit each one twice.
_FORWARDED = frozenset({"x-forwarded-proto", "x-forwarded-for", "x-forwarded-host"})

_UNAVAILABLE_BODY = b"MCP server unavailable"


def is_mcp_path(path: str) -> bool:
    """True when ``path`` belongs to the MCP server rather than Django."""
    return any(path == p or path.startswith(p + "/") for p in MCP_PATH_PREFIXES)


def _scope_header(scope, name: str) -> str:
    target = name.lower().encode("latin-1")
    for key, value in scope.get("headers", []):
        if key.lower() == target:
            return value.decode("latin-1")
    return ""


def _forwarded_headers(scope) -> list[tuple[str, str]]:
    """Request headers to send upstream, with the public Host preserved.

    The MCP server's host/origin guard validates against its own allow-list, so
    it must see the hostname the client actually used (``ember.bhm.li``), not
    the loopback address it is bound to.
    """
    headers = [
        (key.decode("latin-1"), value.decode("latin-1"))
        for key, value in scope.get("headers", [])
        if key.decode("latin-1").lower() not in _HOP_BY_HOP | _FRAMING | _FORWARDED
    ]

    host = _scope_header(scope, "host")
    if host:
        headers.append(("host", host))

    # Cloudflare terminates TLS, so Daphne sees a plain HTTP connection. Keep the
    # scheme Cloudflare reported; fall back to the connection scheme.
    proto = _scope_header(scope, "x-forwarded-proto") or scope.get("scheme", "http")
    headers.append(("x-forwarded-proto", proto))

    # Keep Cloudflare's hop and append the direct peer, so the chain still ends
    # at the Cloudflare edge rather than pretending Daphne saw the client.
    hops = _scope_header(scope, "x-forwarded-for")
    client = scope.get("client")
    chain = ", ".join(h for h in (hops, client[0] if client else "") if h)
    if chain:
        headers.append(("x-forwarded-for", chain))
    if host:
        headers.append(("x-forwarded-host", host))

    return headers


async def _send_plain(send, status: int, body: bytes) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"content-length", str(len(body)).encode("latin-1")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


class McpProxy:
    """ASGI wrapper that routes MCP paths to the MCP server.

    ``transport`` exists for tests: it is handed to the underlying HTTP client
    so the upstream can be simulated without a live MCP process.
    """

    def __init__(
        self,
        django_app,
        upstream_url: str = "http://127.0.0.1:8766",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.django_app = django_app
        self.upstream_url = upstream_url.rstrip("/")
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            # No read timeout: MCP streamable HTTP holds SSE responses open.
            self._client = httpx.AsyncClient(
                base_url=self.upstream_url,
                timeout=httpx.Timeout(connect=10.0, read=None, write=300.0, pool=30.0),
                follow_redirects=False,
                transport=self._transport,
            )
        return self._client

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http" or not is_mcp_path(scope.get("path", "")):
            await self.django_app(scope, receive, send)
            return
        await self._forward(scope, receive, send)

    async def _request_body(self, receive):
        """Buffer the first chunk so bodyless requests stay bodyless upstream.

        Passing an async iterator unconditionally would make the HTTP client
        fall back to chunked framing even for a plain GET.
        """
        first = await receive()
        if first["type"] == "http.disconnect":
            return None

        initial = first.get("body", b"")
        more = first.get("more_body", False)
        if not initial and not more:
            return None

        async def stream():
            chunk, has_more = initial, more
            while True:
                if chunk:
                    yield chunk
                if not has_more:
                    return
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                has_more = message.get("more_body", False)

        return stream()

    async def _forward(self, scope, receive, send) -> None:
        query = scope.get("query_string", b"").decode("latin-1")
        target = scope["path"] + (f"?{query}" if query else "")

        try:
            request = self._http().build_request(
                scope["method"],
                target,
                headers=_forwarded_headers(scope),
                content=await self._request_body(receive),
            )
            response = await self._http().send(request, stream=True)
        except httpx.HTTPError as exc:
            logger.warning(
                "MCP upstream %s unreachable for %s: %s",
                self.upstream_url,
                target,
                exc,
            )
            await _send_plain(send, 502, _UNAVAILABLE_BODY)
            return

        try:
            headers = [
                (key.encode("latin-1"), value.encode("latin-1"))
                for key, value in response.headers.multi_items()
                if key.lower() not in _HOP_BY_HOP | _FRAMING
            ]
            await send(
                {
                    "type": "http.response.start",
                    "status": response.status_code,
                    "headers": headers,
                }
            )
            # Raw chunks keep the upstream content-encoding header truthful and
            # let SSE frames reach the client as they are produced.
            async for chunk in response.aiter_raw():
                await send(
                    {"type": "http.response.body", "body": chunk, "more_body": True}
                )
            await send(
                {"type": "http.response.body", "body": b"", "more_body": False}
            )
        finally:
            await response.aclose()
