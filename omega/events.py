"""Typed events and the transcript sink.

Stages never print directly. They push Events onto the bus; the
Transcript drains the bus and renders `[stage] message` lines, scrubbed
of secrets. That single choke point is what makes the transcript safe
to submit to the board (the server only stores its SHA-256 anyway).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from .secrets import SecretRegistry


@dataclass(frozen=True)
class Event:
    stage: str
    kind: str  # info | decision | result | error
    message: str
    data: dict = field(default_factory=dict)


class Bus:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[Event | None] = asyncio.Queue()

    async def emit(self, event: Event) -> None:
        await self._queue.put(event)

    async def close(self) -> None:
        await self._queue.put(None)

    def __aiter__(self):
        return self

    async def __anext__(self) -> Event:
        item = await self._queue.get()
        if item is None:
            raise StopAsyncIteration
        return item


class Transcript:
    """Drains the bus, renders lines, keeps a copy for the caller."""

    def __init__(self, registry: SecretRegistry) -> None:
        self._registry = registry
        self.lines: list[str] = []

    async def drain(self, bus: Bus) -> None:
        async for event in bus:
            line = f"[{event.stage}] {event.message}"
            line = self._registry.scrub(line)
            self.lines.append(line)
            print(line, flush=True)

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"
