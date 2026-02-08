"""
CLI for profile DB: init, store run dir, search by agenda.
Usage:
  python -m holespawn.db init [--db path]
  python -m holespawn.db store <run_dir> [--db path]
  python -m holespawn.db search --agenda "interested in X" [--db path] [--limit N]
"""

import argparse
import json
import sys
from pathlib import Path

from .search import search_by_agenda
from .store import init_db, store_profile


def _db_path_arg(path: str | None) -> Path:
    if path:
        return Path(path)
    return Path("outputs") / "holespawn.sqlite"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profile DB: init, store run dir, search by agenda (research/product understanding).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    db_arg = lambda p: p.add_argument(
        "--db", type=Path, default=None, help="DB path (default: outputs/holespawn.sqlite)."
    )

    init_p = sub.add_parser("init", help="Create DB and tables.")
    db_arg(init_p)
    init_p.set_defaults(cmd="init")

    store_p = sub.add_parser(
        "store", help="Store a run directory (behavioral_matrix + binding_protocol) into DB."
    )
    store_p.add_argument(
        "run_dir", type=Path, help="Run directory (e.g. outputs/20260201_120000_username)."
    )
    db_arg(store_p)
    store_p.set_defaults(cmd="store")

    search_p = sub.add_parser(
        "search", help="Search profiles by agenda (descriptive query). Returns ranked list."
    )
    search_p.add_argument(
        "--agenda", "-a", type=str, required=True, help="Descriptive query (e.g. interested in X)."
    )
    search_p.add_argument("--limit", "-n", type=int, default=20, help="Max results (default 20).")
    db_arg(search_p)
    search_p.set_defaults(cmd="search")

    args = parser.parse_args()
    db = _db_path_arg(getattr(args, "db", None))

    if args.cmd == "init":
        init_db(db)
        print(f"DB initialized: {db}", file=sys.stderr)
        return

    if args.cmd == "store":
        run_id = store_profile(args.run_dir, db)
        if run_id is None:
            sys.stderr.write(
                "error: run_dir must contain behavioral_matrix.json and metadata.json\n"
            )
            sys.exit(1)
        print(run_id)
        return

    if args.cmd == "search":
        results = search_by_agenda(args.agenda, db, limit=args.limit)
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
