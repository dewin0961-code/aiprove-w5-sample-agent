"""Configuration: everything comes from the environment, with the agent's
own public identity as defaults. No secrets have defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass

API_BASE = "https://aiprove.fun"
ADDRESS = "0xe597392dF235ff99A0062E7512358f26de58135A"
HANDLE = "OmegaCipher3"
REFERRAL = "https://aiprove.fun/r/5c6864d4"

BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# NOTE: this sandbox's aiohttp/brotli build cannot decode `br` bodies, so
# the client advertises gzip/deflate only. See http.py.
ACCEPT_ENCODING = "gzip, deflate"


@dataclass(frozen=True)
class Config:
    api_base: str = API_BASE
    address: str = ADDRESS
    handle: str = HANDLE
    token_file: str | None = None
    signer_command: str | None = None
    private_key: str | None = None  # local signer only; never logged
    target: str = "forecast-btc-7d"
    dry_run: bool = False
    timeout_s: float = 25.0

    @classmethod
    def from_env(cls, target: str = "", dry_run: bool = False) -> "Config":
        return cls(
            api_base=os.environ.get("AIPROVE_API_BASE", API_BASE),
            address=os.environ.get("AGENT_ADDRESS", ADDRESS),
            handle=os.environ.get("AGENT_HANDLE", HANDLE),
            token_file=os.environ.get("AIPROVE_TOKEN_FILE"),
            signer_command=os.environ.get("AGENT_SIGNER_COMMAND"),
            private_key=os.environ.get("AGENT_PRIVATE_KEY"),
            target=target or os.environ.get("AGENT_TARGET", "forecast-btc-7d"),
            dry_run=dry_run,
            timeout_s=float(os.environ.get("AIPROVE_TIMEOUT_S", "25")),
        )
