from ninja import NinjaAPI, Schema

from apps.cutter.api import router as cutter_router
from apps.impose.api import router as impose_router
from apps.jobs.api import router as jobs_router
from apps.routing.api import router as routing_router
from apps.rules.api import router as rules_router

api = NinjaAPI(title="PrintOps API", version="1.0.0", urls_namespace="mainapi")


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
api.add_router("/rules/", rules_router)
