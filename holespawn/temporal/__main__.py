"""
CLI: build temporal NLP series and influence signature from recordings.
Usage: python -m holespawn.temporal --subject @handle [--recordings-dir recordings] [--output trends.json]
"""

import argparse
import json
import logging
import os
import sys

from . import build_series, compute_signature

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    p = argparse.ArgumentParser(description="Temporal NLP over recordings (VADER + topics). No LLM.")
    p.add_argument("--subject", "-s", required=True, help="Subject id, e.g. @handle")
    p.add_argument("--recordings-dir", "-r", default=None, help="Recordings root (default: RECORDINGS_DIR or 'recordings')")
    p.add_argument("--limit", "-n", type=int, default=30, help="Max snapshots to process (default 30)")
    p.add_argument("--output", "-o", default=None, help="Write series + signature JSON here")
    p.add_argument("--no-signature", action="store_true", help="Only output time series, skip drift summary")
    args = p.parse_args()

    recordings_dir = args.recordings_dir or os.environ.get("RECORDINGS_DIR", "recordings")
    series = build_series(
        recordings_dir,
        args.subject,
        source_type="twitter",
        limit=args.limit,
        order_desc=False,
    )
    if not series:
        logger.warning("No recordings found for %s in %s", args.subject, recordings_dir)
        out = {"subject_id": args.subject, "series": [], "signature": None}
    else:
        signature = None if args.no_signature else compute_signature(series)
        out = {"subject_id": args.subject, "series": series, "signature": signature}
        logger.info("Processed %d snapshots; sentiment_shift=%.3f", len(series), (signature or {}).get("sentiment_shift", 0))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        logger.info("Wrote %s", args.output)
    else:
        json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
