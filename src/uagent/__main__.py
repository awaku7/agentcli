from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print()
        print("[INFO] Interrupted. Exiting...")
        raise SystemExit(130)
