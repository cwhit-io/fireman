import json
from datetime import UTC, datetime

from channels.generic.websocket import AsyncWebsocketConsumer


class JobStatusConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer that streams live status updates for a single print job."""

    async def connect(self):
        self.job_id = self.scope["url_route"]["kwargs"]["job_id"]
        self.group_name = f"job_status_{self.job_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # Clients do not send messages; this consumer is read-only.
        pass

    async def job_status_update(self, event):
        """Handle messages sent to the job status group."""
        await self.send(
            text_data=json.dumps(
                {
                    "job_id": event["job_id"],
                    "status": event["status"],
                    "progress": event.get("progress"),
                    "timestamp": event.get(
                        "timestamp",
                        datetime.now(tz=UTC).isoformat(),
                    ),
                }
            )
        )
