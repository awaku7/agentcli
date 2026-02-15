from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# Ensure local src has priority over site-packages installations.
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
