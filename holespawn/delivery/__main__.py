"""
CLI: generate delivery message from existing run and write to file or stdout.

  python -m holespawn.delivery --output-dir outputs/20260210_055918_liminaldoge --channel file --out delivery_out
  python -m holespawn.delivery --output-dir outputs/20260210_055918_liminaldoge --channel stdout
"""

import argparse
import logging
import sys
from pathlib import Path

from .run import run_delivery

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    p = argparse.ArgumentParser(description="Generate tailored message from profile + binding protocol; deliver to file or stdout.")
    p.add_argument("--output-dir", "-o", required=True, type=Path, help="Run directory (contains behavioral_matrix.json, binding_protocol.md)")
    p.add_argument("--channel", "-c", default="file", choices=("file", "stdout", "twitter_dm", "discord_dm", "email"),
                   help="Delivery channel (file/stdout write; others return text only, no send)")
    p.add_argument("--out", default=None, type=Path, help="Output directory for channel=file (default: delivery_out)")
    p.add_argument("--phase", default=None, help="Optional phase hint e.g. 'Phase 1: technical curiosity'")
    args = p.parse_args()

    if not args.output_dir.is_dir():
        logger.error("Output dir not found: %s", args.output_dir)
        return 1
    if (args.output_dir / "binding_protocol.md").exists() is False:
        logger.error("binding_protocol.md not found in %s", args.output_dir)
        return 1

    try:
        result = run_delivery(
            args.output_dir,
            channel=args.channel,
            out_path=args.out,
            phase_hint=args.phase,
        )
    except FileNotFoundError as e:
        logger.error("%s", e)
        return 1

    if args.channel == "stdout":
        print(result["delivered_to"], end="")
    else:
        logger.info("Delivered to: %s", result["delivered_to"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
