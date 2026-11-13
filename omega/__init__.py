"""OmegaCipher — sample agent for the AIProve Arena.

Asyncio + aiohttp pipeline. Stages pass typed events over an asyncio
queue; a single Transcript sink renders the human-readable log. The
private key never enters this process: authentication uses either a
session-token file or a remote signer command (challenge out, signature
back). See README.md.
"""

__version__ = "1.0.0"
