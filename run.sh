#!/usr/bin/env bash
# Live-run wrapper for the OmegaCipher sample agent.
# Usage:
#   ./run.sh                    # live run, token from AIPROVE_TOKEN_FILE
#   ./run.sh forecast-nvda-3d   # live run, another bounty
#   ./run.sh --dry-run          # skill + list + research only, no writes
# The private key never enters this machine: signing happens on the VPS
# via AGENT_SIGNER_COMMAND (challenge out, signature back), or the run
# reuses a session token file (mode 600, never committed).
set -euo pipefail
cd "$(dirname "$0")"

if [[ "${*}" != *"--dry-run"* && -z "${AIPROVE_TOKEN_FILE:-}" && -z "${AGENT_SIGNER_COMMAND:-}" && -z "${AGENT_PRIVATE_KEY:-}" ]]; then
  echo "no auth material — set AIPROVE_TOKEN_FILE, AGENT_SIGNER_COMMAND or AGENT_PRIVATE_KEY" >&2
  exit 1
fi

exec python3 -m omega "$@"
