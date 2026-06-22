import sys
import os

# Add src directory to path to make it recognizable as a package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    from uagent.ws_server import main
except ImportError as e:
    print(f"Error: {e}")
    print(
        "Ensure you are in the project root directory and pip install -e . or set PYTHONPATH=src"
    )
    sys.exit(1)

if __name__ == "__main__":
    sys.exit(main())
