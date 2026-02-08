"""
Real-time rabbit hole demo.
Loads social content → builds profile → streams ARG fragments.
Use --ai to feed narrative + profile to Claude/OpenAI and stream AI-generated fragments.
"""

import argparse
import os
import sys
from pathlib import Path

# Allow running as python -m holespawn.demo from repo root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from holespawn.generator import AIRabbitHoleGenerator, RabbitHoleGenerator
from holespawn.ingest import load_from_file, load_from_text
from holespawn.profile import build_profile


def main():
    parser = argparse.ArgumentParser(
        description="HoleSpawn — Ingest social output, spawn a rabbit hole in real time."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Path to text or JSON file with posts (one per line or blank-line blocks). Default: data/sample_posts.txt",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Use AI API (Claude/OpenAI/Google). Set ANTHROPIC_API_KEY or OPENAI_API_KEY or GOOGLE_API_KEY.",
    )
    parser.add_argument(
        "--provider",
        choices=("anthropic", "openai", "google"),
        default=None,
        help="Force provider (default: Anthropic if ANTHROPIC_API_KEY set, else OpenAI, else Google).",
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=None,
        help="Max number of fragments to emit (default: infinite until Ctrl+C).",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=1.8,
        help="Seconds between fragments (default: 1.8).",
    )
    parser.add_argument(
        "--no-delay",
        action="store_true",
        help="Emit all fragments at once (no real-time delay).",
    )
    args = parser.parse_args()

    path = args.input or ROOT / "data" / "sample_posts.txt"
    if Path(path).exists():
        content = load_from_file(path)
    else:
        print("No input file found. Using minimal sample.", file=sys.stderr)
        content = load_from_text(
            "I keep thinking about the same thing. The days blur. Memory is a trap. Nobody really knows anyone."
        )

    if not list(content.iter_posts()) and not content.raw_text:
        print("No content to analyze. Add posts to the file or pass a path.", file=sys.stderr)
        sys.exit(1)

    profile = build_profile(content)

    if args.ai:
        if (
            not os.getenv("ANTHROPIC_API_KEY")
            and not os.getenv("OPENAI_API_KEY")
            and not os.getenv("GOOGLE_API_KEY")
            and not os.getenv("GEMINI_API_KEY")
        ):
            print(
                "AI mode requires an API key. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY in your environment.",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            gen = AIRabbitHoleGenerator(
                content,
                profile,
                provider=args.provider,
            )
        except ValueError as e:
            print(e, file=sys.stderr)
            sys.exit(1)
        print("--- HoleSpawn (AI) — Ctrl+C to stop ---")
        print("Profile: themes =", [t[0] for t in profile.themes[:8]], "\n")
        interval = 0.0 if args.no_delay else args.interval
        try:
            for token in gen.stream(interval_sec=interval, max_fragments=args.count):
                if token == "\n\n":
                    print("\n")
                else:
                    print(token, end="", flush=True)
        except KeyboardInterrupt:
            print("\n--- end ---")
        return

    gen = RabbitHoleGenerator(profile)
    print("--- HoleSpawn (Ctrl+C to stop) ---")
    print("Profile: themes =", [t[0] for t in profile.themes[:8]], "\n")
    interval = 0.0 if args.no_delay else args.interval
    try:
        for fragment in gen.stream(interval_sec=interval, max_fragments=args.count):
            print(fragment)
            print()
    except KeyboardInterrupt:
        print("\n--- end ---")


if __name__ == "__main__":
    main()
