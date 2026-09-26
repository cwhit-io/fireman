import secrets
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from ninja import NinjaAPI, Schema
from ninja.security import HttpBearer

from apps.cutter.api import router as cutter_router
from apps.impose.api import router as impose_router
from apps.jobs.api import router as jobs_router
from apps.routing.api import router as routing_router


def _expected_printops_token() -> str:
    return (getattr(settings, "PRINTOPS_API_TOKEN", None) or "").strip()


def _bearer_token_ok(request) -> bool:
    expected = _expected_printops_token()
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not expected or not auth.lower().startswith("bearer "):
        return False
    token = auth.split(" ", 1)[1].strip()
    return bool(token) and secrets.compare_digest(token, expected)


class PrintOpsBearerAuth(HttpBearer):
    """Require Authorization: Bearer <PRINTOPS_API_TOKEN> on all Ninja routes."""

    def authenticate(self, request, token: str):
        expected = _expected_printops_token()
        if not expected or not token:
            return None
        if secrets.compare_digest(token, expected):
            return token
        return None


def require_printops_bearer(view_func):
    """Same bearer gate for OpenAPI/docs views (Ninja does not apply auth= there)."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not _bearer_token_ok(request):
            return JsonResponse({"detail": "Unauthorized"}, status=401)
        return view_func(request, *args, **kwargs)

    return _wrapped


api = NinjaAPI(
    title="PrintOps API",
    version="1.0.0",
    urls_namespace="mainapi",
    auth=PrintOpsBearerAuth(),
    docs_decorator=require_printops_bearer,
)


class MessageSchema(Schema):
    message: str


@api.get("/hello", response=MessageSchema, tags=["health"])
def hello(request):
    """Health check / hello endpoint."""
    return {"message": "Hello from Django Ninja!"}


api.add_router("/jobs/", jobs_router)
api.add_router("/impose/", impose_router)
api.add_router("/cutter/", cutter_router)
api.add_router("/routing/", routing_router)
