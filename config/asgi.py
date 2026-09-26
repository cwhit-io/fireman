"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.conf import settings
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

django_asgi_app = get_asgi_application()

from core.mcp_proxy import McpProxy  # noqa: E402
from core.routing import websocket_urlpatterns  # noqa: E402

# The MCP server binds loopback only, so its paths are published through this
# ASGI process rather than by exposing its own port.
http_app = (
    McpProxy(django_asgi_app, upstream_url=settings.MCP_UPSTREAM_URL)
    if settings.MCP_PROXY_ENABLED
    else django_asgi_app
)

application = ProtocolTypeRouter(
    {
        "http": http_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
