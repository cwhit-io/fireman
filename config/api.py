from ninja import NinjaAPI, Schema

api = NinjaAPI(title="My API", version="1.0.0")


class MessageSchema(Schema):
    message: str


@api.get("/hello", response=MessageSchema, tags=["health"])
def hello(request):
    """Health check / hello endpoint."""
    return {"message": "Hello from Django Ninja!"}
