from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print("[INFO] Interrupted. Exiting...")
        raise SystemExit(130)
