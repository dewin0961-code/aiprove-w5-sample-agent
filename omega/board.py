"""Stage 3 — list open bounties and enter one.

Enter is free and idempotent-ish: a 409 means this agent already
entered, which is fine — the pipeline continues to submit (and the
verify stage confirms the submission, not the entry).
"""

from __future__ import annotations

from .config import Config
from .events import Bus, Event
from .http import ArenaClient, WriteUncertainError


async def run_list_stage(client: ArenaClient, bus: Bus, cfg: Config,
                         token: str) -> dict:
    data = await client.get_json("/api/bounties?status=open", token=token)
    items = data.get("bounties", data.get("_list", []))
    if not isinstance(items, list):
        items = []
    target = next((b for b in items if b.get("slug") == cfg.target), None)
    await bus.emit(Event(
        "list_bounties", "info",
        f"{len(items)} open bounties",
    ))
    if target is None:
        detail = await client.get_json(f"/api/bounties/{cfg.target}")
        target = detail.get("bounty", detail)
        if not target.get("slug"):
            raise RuntimeError(f"target bounty not found: {cfg.target}")
    await bus.emit(Event(
        "list_bounties", "info",
        f"target: {cfg.target} — {target.get('title')} "
        f"({target.get('amt')} {target.get('unit')}, "
        f"lane={target.get('lane')}, closes={target.get('closes')})",
    ))
    return target


async def run_enter_stage(client: ArenaClient, bus: Bus, cfg: Config,
                          token: str) -> str | None:
    try:
        status, data = await client.post_json(
            f"/api/bounties/{cfg.target}/enter",
            {"handle": cfg.handle}, token=token)
    except WriteUncertainError as exc:
        await bus.emit(Event(
            "enter", "error",
            f"enter connection dropped ({exc}); checking server state first",
        ))
        subs = await client.get_json("/api/me/submissions", token=token)
        mine = _mine(subs, cfg.target)
        if mine:
            await bus.emit(Event(
                "enter", "info",
                "server already has our submission — enter was processed",
            ))
            return mine.get("id")
        status, data = await client.post_json(
            f"/api/bounties/{cfg.target}/enter",
            {"handle": cfg.handle}, token=token)
    if status == 409:
        await bus.emit(Event(
            "enter", "info",
            f"POST /{cfg.target}/enter -> HTTP 409 already entered",
        ))
        return None
    if status not in (200, 201):
        raise RuntimeError(f"enter failed: HTTP {status} {str(data)[:200]}")
    entry_id = (data.get("entry") or {}).get("id") or data.get("id")
    await bus.emit(Event(
        "enter", "info",
        f"POST /{cfg.target}/enter -> HTTP {status} entry id={entry_id}",
    ))
    return entry_id


def _mine(subs_data: dict, slug: str) -> dict | None:
    items = subs_data.get("submissions", subs_data.get("_list", []))
    if not isinstance(items, list):
        return None
    return next((s for s in items if s.get("bountySlug") == slug), None)


async def my_submissions(client: ArenaClient, token: str) -> list[dict]:
    data = await client.get_json("/api/me/submissions", token=token)
    items = data.get("submissions", data.get("_list", []))
    return items if isinstance(items, list) else []
