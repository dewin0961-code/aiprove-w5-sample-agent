"""The pipeline: wires the stages together over the event bus.

Order: skill -> auth -> list -> enter -> research -> submit -> verify.
In --dry-run mode the pipeline stops after research (no writes, no
auth). Submit follows the verify-before-retry rule: if the POST's
connection drops, the pipeline asks the server what it already has
before it ever re-issues the write.
"""

from __future__ import annotations

import asyncio

from .auth import run_auth_stage
from .board import my_submissions, run_enter_stage, run_list_stage
from .config import Config
from .events import Bus, Event, Transcript
from .http import ArenaClient, WriteUncertainError
from .research import run_research_stage
from .secrets import SecretRegistry
from .skill import run_skill_stage


class Pipeline:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.registry = SecretRegistry()
        self.bus = Bus()
        self.transcript = Transcript(self.registry)
        self.result: dict = {}

    async def run(self) -> dict:
        drain = asyncio.create_task(self.transcript.drain(self.bus))
        try:
            await self._stages()
        finally:
            await self.bus.close()
            await drain
        return self.result

    async def _emit_header(self) -> None:
        await self.bus.emit(Event(
            "loop", "info",
            f"OmegaCipher sample agent — address={self.cfg.address} "
            f"handle={self.cfg.handle} target={self.cfg.target}",
        ))

    async def _stages(self) -> None:
        cfg = self.cfg
        await self._emit_header()
        async with ArenaClient(cfg.api_base, cfg.timeout_s) as client:
            await run_skill_stage(client, self.bus)
            if cfg.dry_run:
                await run_list_stage_public(client)
                prediction = await run_research_stage(self.bus, cfg.target)
                await self.bus.emit(Event(
                    "loop", "result",
                    f"DRY RUN — prediction {prediction}, no auth, no writes",
                ))
                self.result = {"dry_run": True, "prediction": prediction}
                return

            token = await run_auth_stage(client, self.bus, cfg, self.registry)
            await run_list_stage(client, self.bus, cfg, token)
            await run_enter_stage(client, self.bus, cfg, token)
            prediction = await run_research_stage(self.bus, cfg.target)
            submission = await self._submit(client, token, prediction)
            await self._verify(client, token, submission)
            await self.bus.emit(Event(
                "loop", "result",
                "DONE — full loop completed cleanly end to end",
            ))
            self.result = submission

    async def _submit(self, client: ArenaClient, token: str,
                      prediction: dict) -> dict:
        cfg = self.cfg
        payload = {"prediction": prediction, "handle": cfg.handle}
        try:
            status, data = await client.post_json(
                f"/api/bounties/{cfg.target}/submit", payload, token=token)
        except WriteUncertainError as exc:
            await self.bus.emit(Event(
                "submit", "error",
                f"submit connection dropped ({exc}); verifying before retry",
            ))
            mine = await self._find_mine(client, token)
            if mine:
                return mine
            status, data = await client.post_json(
                f"/api/bounties/{cfg.target}/submit", payload, token=token)
        if status == 409:
            await self.bus.emit(Event(
                "submit", "info",
                f"POST /{cfg.target}/submit -> HTTP 409 already submitted; "
                "fetching the existing record",
            ))
            mine = await self._find_mine(client, token)
            if mine:
                return mine
            raise RuntimeError("submit 409 but no submission found on /api/me")
        if status not in (200, 201):
            raise RuntimeError(
                f"submit failed: HTTP {status} {str(data)[:300]}")
        await self.bus.emit(Event(
            "submit", "result",
            f"POST /{cfg.target}/submit -> HTTP {status} submission "
            f"id={data.get('id')} status={data.get('status')}",
        ))
        return {"id": data.get("id"), "status": data.get("status"),
                "slug": cfg.target, "prediction": prediction}

    async def _find_mine(self, client: ArenaClient, token: str) -> dict | None:
        for sub in await my_submissions(client, token):
            if sub.get("bountySlug") == self.cfg.target:
                return {"id": sub.get("id"), "status": sub.get("status"),
                        "slug": self.cfg.target}
        return None

    async def _verify(self, client: ArenaClient, token: str,
                      submission: dict) -> None:
        subs = await my_submissions(client, token)
        mine = next((s for s in subs
                     if s.get("id") == submission.get("id")), None)
        if mine is None:
            raise RuntimeError(
                f"submission {submission.get('id')} not found on "
                "/api/me/submissions after submit")
        await self.bus.emit(Event(
            "verify", "result",
            f"confirmed on GET /api/me/submissions: "
            f"id={mine.get('id')} status={mine.get('status')} "
            f"({len(subs)} total submissions for this agent)",
        ))


async def run_list_stage_public(client: ArenaClient) -> None:
    """Dry-run list: public endpoint, no token needed."""
    data = await client.get_json("/api/bounties?status=open")
    items = data.get("bounties", data.get("_list", []))
    print(f"[list_bounties] {len(items)} open bounties (dry run, public)")
