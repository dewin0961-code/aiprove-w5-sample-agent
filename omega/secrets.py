"""Secret masking. Every secret that enters the process is registered
here; the Transcript scrubs registered values (and anything that looks
like a raw session token or signature) before a line is emitted, so a
secret can never leak into stdout or the saved transcript."""

from __future__ import annotations

import re

_HEX64 = re.compile(r"\b[0-9a-fA-F]{64}\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")


def mask_token(token: str) -> str:
    return (token[:8] + "...") if len(token) > 8 else "***"


def mask_signature(sig: str) -> str:
    if len(sig) > 16:
        return sig[:10] + "..." + sig[-6:]
    return "***"


class SecretRegistry:
    """Holds secret values only to redact them from output."""

    def __init__(self) -> None:
        self._secrets: list[str] = []

    def register(self, value: str | None) -> None:
        if value and len(value) >= 16 and value not in self._secrets:
            self._secrets.append(value)

    def scrub(self, text: str) -> str:
        for secret in self._secrets:
            if secret in text:
                text = text.replace(secret, mask_token(secret))
        text = _JWT.sub("<token>", text)
        text = _HEX64.sub("<hex>", text)
        return text
