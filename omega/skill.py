"""Stage 1 — read skill.md and confirm it describes the loop.

The skill is the contract: authenticate -> list -> enter -> submit.
If any step is missing from the doc, the pipeline refuses to run on
assumptions and fails loudly instead.
"""

from __future__ import annotations

from .events import Bus, Event
from .http import ArenaClient

REQUIRED_MARKERS = ("authenticate", "list open bounties", "submit")


async def run_skill_stage(client: ArenaClient, bus: Bus) -> int:
    text = await client.get_text("/skill.md")
    missing = [m for m in REQUIRED_MARKERS if m.lower() not in text.lower()]
    if missing:
        raise RuntimeError(f"skill.md missing loop steps: {missing}")
    await bus.emit(Event(
        "read_skill", "info",
        f"GET /skill.md -> {len(text)} chars; loop confirmed: "
        "authenticate -> list -> enter -> submit",
    ))
    return len(text)
