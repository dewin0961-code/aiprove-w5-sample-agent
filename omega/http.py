"""Async HTTP client for the arena.

Two reliability rules, learned the hard way on this board:

- every request carries a browser User-Agent (bare-library UAs get
  rejected) and advertises gzip/deflate only (see config.py);
- a write whose connection drops *after* the server processed it is
  never blindly retried. The caller checks GET /api/me/submissions
  first and only re-issues the write if the server has no record.

GETs are retried (up to 3 attempts, backoff); POSTs raise on transport
failure so the pipeline can run the verify-before-retry path.
"""

from __future__ import annotations

import asyncio
import json

import aiohttp

from .config import ACCEPT_ENCODING, BROWSER_UA


class WriteUncertainError(Exception):
    """A POST's connection dropped; the server may already have it."""


class ArenaClient:
    def __init__(self, api_base: str, timeout_s: float = 25.0) -> None:
        self._api_base = api_base.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout_s)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "ArenaClient":
        self._session = aiohttp.ClientSession(
            trust_env=True,  # honour the sandbox egress proxy
            timeout=self._timeout,
            headers={
                "User-Agent": BROWSER_UA,
                "Accept-Encoding": ACCEPT_ENCODING,
            },
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def get_json(self, path: str, token: str | None = None,
                       attempts: int = 3) -> dict:
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                async with self._session.get(
                    self._api_base + path, headers=self._auth(token)
                ) as resp:
                    return await self._read_json(resp)
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exc = exc
                await asyncio.sleep(1.5 * (attempt + 1))
        raise last_exc  # type: ignore[misc]

    async def get_text(self, path: str, attempts: int = 3) -> str:
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                async with self._session.get(self._api_base + path) as resp:
                    resp.raise_for_status()
                    return await resp.text()
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exc = exc
                await asyncio.sleep(1.5 * (attempt + 1))
        raise last_exc  # type: ignore[misc]

    async def post_json(self, path: str, payload: dict,
                        token: str | None = None) -> tuple[int, dict]:
        try:
            async with self._session.post(
                self._api_base + path,
                json=payload,
                headers=self._auth(token, json=True),
            ) as resp:
                return resp.status, await self._read_json(resp)
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise WriteUncertainError(f"POST {path} dropped: {exc}") from exc

    @staticmethod
    def _auth(token: str | None, json: bool = False) -> dict:
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if json:
            headers["content-type"] = "application/json"
        return headers

    @staticmethod
    async def _read_json(resp: aiohttp.ClientResponse) -> dict:
        text = await resp.text()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {"_raw": text[:500], "_status": resp.status}
        return data if isinstance(data, dict) else {"_list": data}
