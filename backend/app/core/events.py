# app/core/events.py
from __future__ import annotations
import asyncio, json, time
from typing import AsyncGenerator, Dict, Set

class _EventBus:
    def __init__(self) -> None:
        # incident_id -> set[asyncio.Queue]
        self._subs: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, incident_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subs.setdefault(incident_id, set()).add(q)
        return q

    async def unsubscribe(self, incident_id: str, q: asyncio.Queue) -> None:
        async with self._lock:
            subs = self._subs.get(incident_id)
            if subs and q in subs:
                subs.remove(q)
            if subs and not subs:
                self._subs.pop(incident_id, None)

    async def publish(self, incident_id: str, event: str, data: dict) -> None:
        payload = {
            "ts": time.time(),
            "event": event,
            "data": data or {},
        }
        msg = f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        async with self._lock:
            for q in list(self._subs.get(incident_id, ())):
                # best-effort; drop if slow
                if q.full():
                    try:
                        q.get_nowait()
                    except Exception:
                        pass
                await q.put(msg)

BUS = _EventBus()

async def sse_stream(incident_id: str) -> AsyncGenerator[bytes, None]:
    # subscribe
    q = await BUS.subscribe(incident_id)
    try:
        # initial hello so client knows it’s connected
        await BUS.publish(incident_id, "connected", {"incident_id": incident_id})
        while True:
            msg = await q.get()
            yield msg.encode("utf-8")
    except asyncio.CancelledError:
        # client disconnected
        raise
    finally:
        await BUS.unsubscribe(incident_id, q)

async def emit(incident_id: str, event: str, **data) -> None:
    await BUS.publish(incident_id, event, data)
