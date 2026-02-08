"""
Run autonomous agent from CLI.
  python -m holespawn.agent run --goal "..." --criteria '{}' --data operation_data.json
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from holespawn.agent.cli import main

if __name__ == "__main__":
    sys.exit(main())
