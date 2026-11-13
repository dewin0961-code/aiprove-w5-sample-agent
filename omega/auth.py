"""Stage 2 — authenticate.

Three ways in, in priority order:

1. Session token file (AIPROVE_TOKEN_FILE): the token is read, the
   raw value is registered as a secret (so it can only ever be printed
   masked), and validated live with GET /api/me.
2. Remote signer (AGENT_SIGNER_COMMAND): fetch a challenge, pipe it to
   the signer command (challenge as the final argument, signature on
   stdout — the key never leaves the signer host), POST /api/auth/verify.
3. Local signer (AGENT_PRIVATE_KEY): same challenge flow, signed in
   this process with eth_account. Only for throwaway/test keys.

The returned token is registered as a secret immediately.
"""

from __future__ import annotations

import asyncio
import shlex

from .config import Config
from .events import Bus, Event
from .http import ArenaClient
from .secrets import SecretRegistry, mask_signature, mask_token


class AuthError(Exception):
    pass


async def _verify_challenge(client: ArenaClient, bus: Bus, cfg: Config,
                            signature: str) -> str:
    status, data = await client.post_json("/api/auth/verify", {
        "address": cfg.address, "signature": signature,
    })
    token = data.get("token", "")
    if status != 200 or not token:
        raise AuthError(f"verify failed: HTTP {status} {str(data)[:200]}")
    await bus.emit(Event(
        "authenticate", "info",
        f"session token received token={mask_token(token)} "
        f"expiresAt={data.get('expiresAt')}",
    ))
    return token


async def run_auth_stage(client: ArenaClient, bus: Bus, cfg: Config,
                         registry: SecretRegistry) -> str:
    # Path 1: pre-existing session token.
    if cfg.token_file:
        token = open(cfg.token_file).read().strip()
        registry.register(token)
        me = await client.get_json("/api/me", token=token)
        handle = (me.get("profile") or {}).get("handle")
        address = me.get("address", "")
        if address.lower() != cfg.address.lower():
            raise AuthError(
                f"token belongs to {address}, not configured {cfg.address}")
        await bus.emit(Event(
            "authenticate", "info",
            f"session token supplied, token={mask_token(token)}",
        ))
        await bus.emit(Event(
            "authenticate", "info",
            f"token valid — /api/me handle={handle} address={address}",
        ))
        return token

    # Paths 2/3 need a fresh challenge.
    challenge_data = await client.get_json(
        f"/api/auth/challenge?address={cfg.address}")
    challenge = challenge_data.get("challenge", "")
    if not challenge:
        raise AuthError(f"no challenge: {str(challenge_data)[:200]}")
    await bus.emit(Event(
        "authenticate", "info",
        f"challenge received ({len(challenge)} chars)",
    ))

    if cfg.signer_command:
        cmd = shlex.split(cfg.signer_command) + [challenge]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise AuthError(f"signer failed: {err.decode()[:200]}")
        signature = out.decode().strip()
    elif cfg.private_key:
        from eth_account import Account
        from eth_account.messages import encode_defunct

        account = Account.from_key(cfg.private_key)
        if account.address.lower() != cfg.address.lower():
            raise AuthError("AGENT_PRIVATE_KEY does not match AGENT_ADDRESS")
        signature = account.sign_message(
            encode_defunct(text=challenge)).signature.hex()
        signature = "0x" + signature
    else:
        raise AuthError(
            "no auth material: set AIPROVE_TOKEN_FILE, "
            "AGENT_SIGNER_COMMAND or AGENT_PRIVATE_KEY")

    registry.register(signature)
    await bus.emit(Event(
        "authenticate", "info",
        "challenge signed (EIP-191 personal_sign) "
        f"sig={mask_signature(signature)}",
    ))
    token = await _verify_challenge(client, bus, cfg, signature)
    registry.register(token)
    return token
