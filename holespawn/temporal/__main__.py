"""
CLI: build temporal NLP series and influence signature from recordings.
Usage:
  python -m holespawn.temporal --subject @handle [--recordings-dir recordings] [--output trends.json]
  python -m holespawn.temporal --list-subjects [--recordings-dir recordings]  # JSON summary for TUI
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from . import build_series, compute_signature, list_recordings, list_subjects

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    p = argparse.ArgumentParser(description="Temporal NLP over recordings (VADER + topics). No LLM.")
    p.add_argument("--subject", "-s", default=None, help="Subject id, e.g. @handle (required unless --list-subjects)")
    p.add_argument("--recordings-dir", "-r", default=None, help="Recordings root (default: RECORDINGS_DIR or 'recordings')")
    p.add_argument("--limit", "-n", type=int, default=30, help="Max snapshots to process (default 30)")
    p.add_argument("--output", "-o", default=None, help="Write series + signature JSON here")
    p.add_argument("--no-signature", action="store_true", help="Only output time series, skip drift summary")
    p.add_argument("--list-subjects", action="store_true", help="Print JSON summary of recorded subjects (for TUI Recording tab)")
    args = p.parse_args()

    recordings_dir = args.recordings_dir or os.environ.get("RECORDINGS_DIR", "recordings")
    root = Path(recordings_dir).resolve()
    db_path = root / "recordings.db"

    if args.list_subjects:
        if not db_path.is_file():
            json.dump([], sys.stdout, ensure_ascii=False)
            sys.stdout.write("\n")
            return 0
        out = []
        for sid in list_subjects(db_path):
            rows = list_recordings(db_path, sid, limit=1, order_desc=True)
            last = rows[0] if rows else None
            all_rows = list_recordings(db_path, sid, limit=10000)
            out.append({
                "subject_id": sid,
                "last_timestamp": last["timestamp"] if last else None,
                "snapshot_count": len(all_rows),
                "record_count": last["record_count"] if last else 0,
            })
        json.dump(out, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    if not args.subject:
        logger.error("--subject is required unless --list-subjects is set")
        return 1

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
