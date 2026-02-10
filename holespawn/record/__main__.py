"""
Run the recorder: python -m holespawn.record
Loads subjects.yaml, fetches Twitter (self-hosted scraper) for each subject, writes
recordings/{twitter|discord}/{id}/YYYYMMDD_HHMMSS.json, updates recordings.db.
Schedule via cron, e.g.: 0 14 * * * cd /path/to/repo && python -m holespawn.record
"""

import argparse
import logging
import os
import sys

from .config import load_subjects
from .recorder import record_all

logging.basicConfig(
    level=logging.INFO,
    format="[holespawn] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record time-stamped snapshots of Twitter/Discord data for temporal analysis.",
    )
    parser.add_argument(
        "--config",
        "-c",
        default=os.environ.get("RECORD_CONFIG", "subjects.yaml"),
        help="Path to subjects.yaml (default: RECORD_CONFIG or subjects.yaml)",
    )
    parser.add_argument(
        "--recordings-dir",
        "-o",
        default=os.environ.get("RECORDINGS_DIR", "recordings"),
        help="Output directory for recordings (default: RECORDINGS_DIR or recordings)",
    )
    parser.add_argument(
        "--max-tweets",
        type=int,
        default=500,
        help="Max tweets per Twitter subject (default: 500)",
    )
    args = parser.parse_args()

    subjects = load_subjects(args.config)
    if not subjects:
        logger.error("No subjects found in %s. Add a 'subjects:' list with handle/source/interval.", args.config)
        return 1

    counts = record_all(
        config_path=args.config,
        recordings_dir=args.recordings_dir,
        max_tweets_per_user=args.max_tweets,
    )
    logger.info("Recorded=%d failed=%d", counts["recorded"], counts["failed"])
    return 0 if counts["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
