"""
SSE (Server-Sent Events) broadcaster for real-time pipeline updates.
"""

import asyncio
import json
from typing import AsyncGenerator


class SSEBroadcaster:
    """Fan-out SSE events to all connected clients."""

    def __init__(self):
        self._queues: list[asyncio.Queue] = []

    async def subscribe(self) -> AsyncGenerator[str, None]:
        queue: asyncio.Queue = asyncio.Queue()
        self._queues.append(queue)
        try:
            while True:
                data = await queue.get()
                yield data
        except asyncio.CancelledError:
            pass
        finally:
            self._queues.remove(queue)

    async def broadcast(self, event: str, data: dict):
        msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        for queue in self._queues:
            await queue.put(msg)


broadcaster = SSEBroadcaster()
