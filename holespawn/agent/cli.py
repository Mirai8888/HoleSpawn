"""
CLI for autonomous cognitive warfare agent.
  python -m holespawn.agent.cli run --goal "..." --criteria '{}' --data operation_data.json
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def cmd_run(args: argparse.Namespace) -> int:
    """Run autonomous operation."""
    from holespawn.agent.autonomous import AutonomousOperator

    goal = args.goal or "Profile targets, engage via DM to build rapport, deploy traps, achieve 70+ effectiveness on at least 3 targets."
    criteria = {}
    if args.criteria:
        try:
            criteria = json.loads(args.criteria)
        except json.JSONDecodeError as e:
            print("Invalid --criteria JSON:", e, file=sys.stderr)
            return 1
    data = {}
    if args.data:
        path = Path(args.data)
        if not path.is_file():
            print("Data file not found:", path, file=sys.stderr)
            return 1
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print("Failed to load data file:", e, file=sys.stderr)
            return 1

    if args.model:
        import os
        os.environ["LLM_MODEL"] = args.model

    operator = AutonomousOperator(
        goal=goal,
        success_criteria=criteria,
        model_type=args.model or "claude",
        max_iterations=args.max_iterations,
    )
    result = operator.run(initial_data=data)
    print(json.dumps(result, indent=2))
    return 0 if result.get("completed") else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="python -m holespawn.agent.cli",
        description="Autonomous cognitive warfare agent",
    )
    sub = ap.add_subparsers(dest="command", help="Command")

    run_p = sub.add_parser("run", help="Run autonomous operation")
    run_p.add_argument("--goal", "-g", help="Operational goal")
    run_p.add_argument("--criteria", "-c", help="Success criteria as JSON, e.g. {\"min_effectiveness\": 70, \"min_successful_traps\": 3}")
    run_p.add_argument("--data", "-d", help="Path to operation_data.json (targets, platform, exports)")
    run_p.add_argument("--model", "-m", help="LLM model (claude, gpt-4, or model name)")
    run_p.add_argument("--max-iterations", "-n", type=int, default=20, help="Max iterations (default 20)")
    run_p.set_defaults(func=cmd_run)

    parsed = ap.parse_args()
    if not parsed.command:
        ap.print_help()
        return 0
    return parsed.func(parsed)


if __name__ == "__main__":
    sys.exit(main())
