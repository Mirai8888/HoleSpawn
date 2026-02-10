"""Run build_site for every handle in data/apify_handles (one-off batch)."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "data" / "apify_handles" / "index.json"
CORPUS = ROOT / "data" / "apify_handles"

def main():
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    handles = [d["handle"] for d in data if isinstance(d, dict) and d.get("handle")]
    for handle in handles:
        txt = CORPUS / f"{handle}.txt"
        if not txt.is_file():
            continue
        print(f"=== build_site @{handle} ===", flush=True)
        subprocess.run(
            [
                "python",
                "-m",
                "holespawn.build_site",
                str(txt),
                "--consent-acknowledged",
                "--profile-only",
            ],
            cwd=str(ROOT),
            check=False,
        )

if __name__ == "__main__":
    main()
