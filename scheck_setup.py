#!/usr/bin/env python
import os
import sys

# Add src directory to path to make it recognizable as a package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    from uagent.i18n import detect_lang, set_thread_lang

    set_thread_lang(detect_lang())
    from uagent.setup_cli import main
except ImportError as e:
    print(f"Error: {e}")
    print(
        "Ensure you are in the project root directory and the 'src' directory exists."
    )
    sys.exit(1)

if __name__ == "__main__":
    sys.exit(main())
