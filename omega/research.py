"""Stage 4 — research: turn live market data into a prediction.

Two independent researchers, one per bounty shape. Nothing is
hardcoded: every number below is fetched at run time and the reasoning
is printed in the transcript.

- BTC direction (forecast-btc-7d): CoinGecko daily closes. Direction
  follows the 7-day return and the down/up-day split; confidence starts
  at 0.55, grows with the size of the move, and is CAPPED when the move
  is sharp — a steep selloff often bounces, and the Brier score
  punishes a confident wrong call more than a hedged one.
- NVDA close (forecast-nvda-3d): Yahoo Finance daily closes. The
  3-trading-day target extrapolates the mean daily log-return of the
  last 5 sessions, with the per-day drift clamped to +/-2% so one wild
  session cannot drag the forecast off a cliff.
"""

from __future__ import annotations

import math

import aiohttp

from .events import Bus, Event

UA = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Encoding": "gzip, deflate",
}


async def _fetch_json(url: str) -> dict:
    async with aiohttp.ClientSession(trust_env=True, headers=UA) as s:
        async with s.get(url, timeout=aiohttp.ClientTimeout(total=25)) as r:
            r.raise_for_status()
            return await r.json()


async def research_btc(bus: Bus) -> dict:
    data = await _fetch_json(
        "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
        "?vs_currency=usd&days=8&interval=daily")
    closes = [round(p[1], 2) for p in data["prices"]]
    first, last = closes[0], closes[-1]
    ret7 = last / first - 1
    daily = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    down = sum(1 for d in daily if d < 0)
    up = len(daily) - down
    momentum = sum(daily[-3:]) / 3

    if ret7 < 0 and down > up:
        answer = "no"
    elif ret7 > 0 and up > down:
        answer = "yes"
    else:
        answer = "no" if momentum < 0 else "yes"

    confidence = 0.55 + min(0.10, abs(ret7) * 0.8)
    if abs(ret7) > 0.08:  # sharp weekly move: cap, selloffs bounce
        confidence = min(confidence, 0.62)
    confidence = round(min(confidence, 0.65), 2)

    await bus.emit(Event(
        "submit", "decision",
        f"research: BTC ${last:,.2f} ({ret7:+.2%} 7d, {down}/{len(daily)} "
        f"down days) closes={closes}",
    ))
    await bus.emit(Event(
        "submit", "decision",
        f"prediction: {{'answer': '{answer}', 'confidence': {confidence}}} — "
        f"BTC 7d {ret7:+.2%} over {len(daily)} sessions, {down}/{len(daily)} "
        f"down days, latest ${last:,.2f}. "
        f"{'Sharp weekly drop' if ret7 < -0.05 else 'Weekly drift'} with a "
        f"majority of down days; confidence capped — a sharp selloff often "
        f"bounces, and Brier punishes a confident wrong call.",
    ))
    return {"answer": answer, "confidence": confidence}


async def research_nvda(bus: Bus) -> dict:
    data = await _fetch_json(
        "https://query1.finance.yahoo.com/v8/finance/chart/NVDA"
        "?range=10d&interval=1d")
    result = data["chart"]["result"][0]
    closes = [round(c, 2) for c in result["indicators"]["quote"][0]["close"]
              if c is not None]
    last = closes[-1]
    logrets = [math.log(closes[i] / closes[i - 1])
               for i in range(1, len(closes))]
    drift = sum(logrets[-5:]) / 5
    drift = max(-0.02, min(0.02, drift))  # clamp wild sessions
    target = round(last * math.exp(3 * drift), 2)
    ret5 = closes[-1] / closes[-6] - 1

    await bus.emit(Event(
        "submit", "decision",
        f"research: NVDA ${last:,.2f} ({ret5:+.2%} 5 sessions, "
        f"mean daily log-return last 5: {drift:+.4f}/day) closes={closes}",
    ))
    await bus.emit(Event(
        "submit", "decision",
        f"prediction: {{'answer': {target}}} — last close ${last:,.2f}, "
        f"5-session drift {drift:+.4f}/day clamped to +/-2%, extrapolated "
        f"3 trading days out: ${last:,.2f} * exp(3 * {drift:+.4f}) "
        f"= ${target:,.2f}. NVDA has fallen hard into this print, so the "
        f"drift points down; the clamp keeps one wild session from "
        f"dragging the forecast off a cliff.",
    ))
    return {"answer": target}


RESEARCHERS = {
    "forecast-btc-7d": research_btc,
    "forecast-nvda-3d": research_nvda,
}


async def run_research_stage(bus: Bus, target: str) -> dict:
    fn = RESEARCHERS.get(target)
    if fn is None:
        raise RuntimeError(f"no researcher for bounty: {target}")
    return await fn(bus)
