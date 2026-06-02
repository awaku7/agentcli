import sys
import os

# Add src directory to path to make it recognizable as a package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from uagent.checks import check_git_installation

check_git_installation()

# Set GUI mode flag in environment variables
os.environ["UAGENT_GUI_MODE"] = "1"

try:
    from uagent.gui import main
except ImportError as e:
    print(f"Error: {e}")
    print(
        "Ensure you are in the project root directory and the 'src' directory exists."
    )
    sys.exit(1)

if __name__ == "__main__":
    main()
