"""CLI entry point: python3 -m omega [slug] [--dry-run]

Exit 0 only when the full loop completed cleanly (or the dry run
finished); any failure prints `[loop] FAILED — <reason>` and exits 1.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .config import Config
from .pipeline import Pipeline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="omega",
        description="OmegaCipher sample agent for the AIProve Arena")
    parser.add_argument("target", nargs="?", default="",
                        help="bounty slug (default: forecast-btc-7d)")
    parser.add_argument("--dry-run", action="store_true",
                        help="skill + list + research only; no auth, no writes")
    parser.add_argument("--token-file", default=None,
                        help="session token file (overrides AIPROVE_TOKEN_FILE)")
    return parser.parse_args(argv)


async def _main_async(cfg: Config) -> int:
    pipeline = Pipeline(cfg)
    try:
        await pipeline.run()
    except Exception as exc:  # noqa: BLE001 — top-level: report and exit 1
        print(f"[loop] FAILED — {exc}", flush=True)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = Config.from_env(target=args.target, dry_run=args.dry_run)
    if args.token_file:
        cfg = Config(**{**cfg.__dict__, "token_file": args.token_file})
    return asyncio.run(_main_async(cfg))


if __name__ == "__main__":
    sys.exit(main())
