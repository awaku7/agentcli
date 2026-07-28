#!/usr/bin/env python
import os
import sys

# Add src directory to path to make it recognizable as a package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

MODES = {
    "cli": "uagent.cli",
    "a2a": "uagent.a2a.server",
    "gui": "uagent.gui",
    "web": "uagent.web",
    "ws": "uagent.ws_server",
    "setup": "uagent.setup_cli",
}


def main():
    mode = "cli"
    args = sys.argv[1:]
    if args and args[0] in MODES:
        mode = args[0]
        args = args[1:]

    # -- git check (a2a, gui, web)
    if mode in ("a2a", "gui", "web"):
        from uagent.checks import check_git_installation

        check_git_installation()

    # -- env vars (gui)
    if mode == "gui":
        os.environ["UAGENT_GUI_MODE"] = "1"

    # -- i18n (setup)
    if mode == "setup":
        from uagent.i18n import detect_lang, set_thread_lang

        set_thread_lang(detect_lang())

    # -- a2a token warning
    if mode == "a2a":
        if not (os.environ.get("UAGENT_A2A_TOKEN") or "").strip():
            print(
                "Warning: UAGENT_A2A_TOKEN is not set "
                "(A2A authenticated endpoints will reject requests)."
            )

    module_path = MODES[mode]
    try:
        mod = __import__(module_path, fromlist=["main"])
    except ImportError as e:
        print(f"Error: {e}")
        print(
            "Ensure you are in the project root directory "
            "and the 'src' directory exists."
        )
        sys.exit(1)

    if mode in ("ws", "setup"):
        sys.exit(mod.main())
    elif mode == "a2a":
        mod.main(args)
    else:
        mod.main()


if __name__ == "__main__":
    main()
