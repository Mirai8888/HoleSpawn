"""
C2 Dashboard CLI.
  python -m dashboard serve       # Start Flask server
  python -m dashboard init-db      # Create C2 tables
  python -m dashboard worker      # Run job worker (process queued jobs)
  python -m dashboard import-targets <file>  # Import targets from JSON
  python -m dashboard queue-profile <target_id>
  python -m dashboard generate-trap <target_id>
  python -m dashboard deploy-trap <trap_id>
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def cmd_serve(args):
    from dashboard.app import app
    host = args.host or "0.0.0.0"
    port = args.port or 5000
    app.run(host=host, port=port, debug=args.debug)


def cmd_init_db(args):
    from dashboard.db import init_db
    init_db()
    print("C2 database initialized.")


def cmd_worker(args):
    from dashboard.services.queue import JobQueue
    import time
    q = JobQueue()
    print("Worker running (Ctrl+C to stop)...")
    try:
        while True:
            n = q.process_jobs(max_jobs=args.batch)
            if n:
                print("Processed", n, "jobs")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Stopped.")


def cmd_import_targets(args):
    path = Path(args.file)
    if not path.is_file():
        print("File not found:", path, file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    targets = data if isinstance(data, list) else data.get("targets", [data])
    from dashboard.db import get_db
    from dashboard.db import operations as ops
    for t in targets:
        identifier = t.get("identifier") or t.get("id") or str(t)
        if isinstance(identifier, dict):
            identifier = identifier.get("identifier") or identifier.get("id") or ""
        platform = t.get("platform") if isinstance(t, dict) else None
        with get_db() as db:
            if ops.get_target_by_identifier(db, str(identifier)):
                print("Skip (exists):", identifier)
                continue
            ops.create_target(db, identifier=str(identifier), platform=platform)
            print("Added:", identifier)
    print("Done.")


def cmd_queue_profile(args):
    from dashboard.services.queue import JobQueue
    target_id = int(args.target_id)
    q = JobQueue()
    job_id = q.enqueue("profile", target_id=target_id, priority=1)
    print("Queued profile job:", job_id)


def cmd_generate_trap(args):
    from dashboard.services.queue import JobQueue
    target_id = int(args.target_id)
    q = JobQueue()
    job_id = q.enqueue("generate_trap", target_id=target_id, priority=1)
    print("Queued generate_trap job:", job_id)


def cmd_deploy_trap(args):
    from dashboard.services.queue import JobQueue
    trap_id = int(args.trap_id)
    q = JobQueue()
    job_id = q.enqueue("deploy", target_id=None, params={"trap_id": trap_id})
    print("Queued deploy job:", job_id)


def main():
    ap = argparse.ArgumentParser(prog="python -m dashboard", description="C2 Dashboard CLI")
    sub = ap.add_subparsers(dest="command", help="Command")

    p_serve = sub.add_parser("serve", help="Start Flask server")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=5000)
    p_serve.add_argument("--debug", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    p_init = sub.add_parser("init-db", help="Initialize C2 database")
    p_init.set_defaults(func=cmd_init_db)

    p_worker = sub.add_parser("worker", help="Run job worker")
    p_worker.add_argument("--batch", type=int, default=5)
    p_worker.add_argument("--interval", type=float, default=5.0)
    p_worker.set_defaults(func=cmd_worker)

    p_import = sub.add_parser("import-targets", help="Import targets from JSON file")
    p_import.add_argument("file", help="Path to JSON file (array or { targets: [...] })")
    p_import.set_defaults(func=cmd_import_targets)

    p_qp = sub.add_parser("queue-profile", help="Queue profiling job for target")
    p_qp.add_argument("target_id", help="Target ID")
    p_qp.set_defaults(func=cmd_queue_profile)

    p_gt = sub.add_parser("generate-trap", help="Queue trap generation job")
    p_gt.add_argument("target_id", help="Target ID")
    p_gt.set_defaults(func=cmd_generate_trap)

    p_dt = sub.add_parser("deploy-trap", help="Queue deploy job for trap")
    p_dt.add_argument("trap_id", help="Trap ID")
    p_dt.set_defaults(func=cmd_deploy_trap)

    args = ap.parse_args()
    if not args.command:
        ap.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
