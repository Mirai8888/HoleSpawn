"""
Ensure no real personal data (PII) in committed data files.
Run on data/ folder before commit.
"""

import re
import sys
from pathlib import Path


def check_for_pii(text: str) -> list[str]:
    """Check for emails, phone numbers, SSN. Returns list of finding names."""
    patterns = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    }
    findings = []
    for name, pattern in patterns.items():
        if re.search(pattern, text):
            findings.append(name)
    return findings


def main() -> int:
    data_dir = Path(__file__).resolve().parent.parent / "data"
    if not data_dir.exists():
        return 0
    failed = False
    for path in sorted(data_dir.rglob("*.txt")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        pii = check_for_pii(text)
        if pii:
            print(f"PII found in {path}: {pii}")
            failed = True
    if failed:
        print("Remove or anonymize PII before committing.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
