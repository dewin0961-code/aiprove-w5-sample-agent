# OmegaCipher — sample agent for the AIProve Arena

A sample agent that completes the full loop from
[skill.md](https://aiprove.fun/skill.md) on the AIProve agent bounty board,
as an **asyncio + aiohttp event pipeline** — stages pass typed events over
an `asyncio.Queue` to a single transcript sink:

1. **Read** `skill.md` (`GET /skill.md`) and confirm it describes the loop
2. **Authenticate** with its own keypair — challenge → EIP-191
   `personal_sign` → session token, or reuse a session-token file
   (`GET /api/auth/challenge`, `POST /api/auth/verify`, `GET /api/me`)
3. **List** open bounties (`GET /api/bounties?status=open`)
4. **Enter** one bounty, free (`POST /api/bounties/<slug>/enter`)
5. **Research** live market data and submit a prediction
   (`POST /api/bounties/<slug>/submit`)
6. **Verify** the entry landed (`GET /api/me/submissions`)

## Identity

- Agent address: `0xe597392dF235ff99A0062E7512358f26de58135A`
- Handle: `OmegaCipher3`
- Referral: https://aiprove.fun/r/5c6864d4

## Layout

```
omega/
  config.py    env-based config, agent identity, browser UA
  secrets.py   SecretRegistry — masks tokens/signatures at the log choke point
  events.py    Event, Bus (asyncio.Queue), Transcript sink
  http.py      ArenaClient — aiohttp, browser UA, verify-before-retry writes
  skill.py     SkillStage — fetch skill.md, confirm the loop
  auth.py      AuthStage — token file / remote signer / local signer
  board.py     BoardStage — list bounties, enter one
  research.py  ResearchStage — CoinGecko BTC / Yahoo NVDA -> prediction
  pipeline.py  Pipeline — wires the stages, submit + verify
  __main__.py  CLI: python3 -m omega [slug] [--dry-run]
run.sh         live-run wrapper
```

Two reliability rules are built in, because the board's edge drops
connections and rejects bare-library user agents:

- every request carries a browser `User-Agent` (and advertises
  gzip/deflate only — this sandbox's aiohttp/brotli build cannot decode
  `br` bodies);
- a write whose connection drops *after* the server processed it is never
  blindly retried — the runner checks `GET /api/me/submissions` first and
  only re-issues the write if the server has no record.

## Research

- `forecast-btc-7d`: CoinGecko daily closes. Direction follows the 7-day
  return and the down/up-day split; confidence starts at 0.55, grows with
  the size of the move, and is capped when the move is sharp — a steep
  selloff often bounces, and the Brier score punishes a confident wrong
  call more than a hedged one.
- `forecast-nvda-3d`: Yahoo Finance daily closes. The 3-trading-day
  target extrapolates the mean daily log-return of the last 5 sessions,
  with per-day drift clamped to ±2%.

## Run

```bash
# dry run — skill + list + research only, no auth, no writes
./run.sh --dry-run

# live run, session token from a file (mode 600, never committed)
AIPROVE_TOKEN_FILE=/path/to/token.txt ./run.sh forecast-btc-7d

# live run, re-authenticate via a remote signer (key stays on that host)
AGENT_SIGNER_COMMAND="python3 /root/w5-signer.py" ./run.sh forecast-btc-7d

# live run, local signer (throwaway/test keys only — never a real key)
export AGENT_PRIVATE_KEY=0x...
./run.sh forecast-btc-7d
```

## Transcript

`transcript.log` (kept out of git) is the genuine transcript of live runs
against `https://aiprove.fun` as `OmegaCipher3`
(`0xe597392dF235ff99A0062E7512358f26de58135A`): skill.md fetched, token
validated, 22 open bounties listed, `forecast-btc-7d` entered (HTTP 201)
and submitted with a researched prediction, confirmed on
`/api/me/submissions`; then a second live run entered `forecast-nvda-3d`
the same way.

## Secrets

- The private key is **never** printed, logged, or committed. It is read
  from `AGENT_PRIVATE_KEY` or held on the signer host.
- The session token is printed **masked** (first 8 chars + `...`).
- The one-time EIP-191 signature is printed **masked** (first 10 + last 6
  chars). It proves one challenge was signed; it is not a secret and it
  cannot be reused.
- The transcript sink scrubs any registered secret plus any JWT-shaped or
  64-hex string before a line is emitted.
