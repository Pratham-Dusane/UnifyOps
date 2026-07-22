import asyncio
from typing import Dict, List
import logging

logger = logging.getLogger("unifyops-agent-bus")


class AgentEventBus:
    def __init__(self):
        # request_id -> list of asyncio.Queue
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        # Track start time to calculate offset
        self._start_times: Dict[str, float] = {}

    def init_request(self, request_id: str):
        import time

        self._start_times[request_id] = time.time()

    def subscribe(self, request_id: str) -> asyncio.Queue:
        if request_id not in self._subscribers:
            self._subscribers[request_id] = []
        q = asyncio.Queue()
        self._subscribers[request_id].append(q)
        logger.debug(f"Subscribed to agent stream for {request_id}")
        return q

    def unsubscribe(self, request_id: str, queue: asyncio.Queue):
        if request_id in self._subscribers:
            if queue in self._subscribers[request_id]:
                self._subscribers[request_id].remove(queue)
            if not self._subscribers[request_id]:
                del self._subscribers[request_id]
        logger.debug(f"Unsubscribed from agent stream for {request_id}")

    def emit(
        self,
        request_id: str,
        agent_name: str,
        action_summary: str,
        detail: dict = None,
        metric: dict = None,
    ):
        """Broadcast a message to all subscribers of a request_id."""
        if request_id not in self._subscribers:
            return  # No active subscribers, drop the message

        import time

        start_time = self._start_times.get(request_id, time.time())
        offset_ms = int((time.time() - start_time) * 1000)

        payload = {
            "timestamp_offset_ms": offset_ms,
            "agent_name": agent_name,
            "action_summary": action_summary,
            "detail": detail,
            "metric": metric,
        }

        for q in self._subscribers[request_id]:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass


agent_bus = AgentEventBus()
