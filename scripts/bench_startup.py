"""Measure uag startup costs: imports, tool plugin loading, catalog search.

Each probe runs in a fresh Python subprocess with ``src/`` first on
``sys.path``, so the numbers reflect the working tree even when an older
``uagent`` is installed in site-packages. The first run of each probe is a
warm-up (it may compile ``.pyc`` files) and is discarded; the median of the
remaining runs is reported.

Usage:
    python scripts/bench_startup.py            # 5 runs per probe
    python scripts/bench_startup.py --runs 9
    python scripts/bench_startup.py --json     # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"

# Optional third-party packages that should NOT be imported just by loading
# the tool plugins. Reported so a regression is visible at a glance.
WATCHED_MODULES = (
    "httpx",
    "bs4",
    "docx",
    "odf",
    "msoffcrypto",
    "holidays",
    "pyautogui",
    "pygetwindow",
    "numpy",
    "tkinter",
    "cv2",
    "PIL",
)

_PROBE_TEMPLATE = r"""
import json, sys, time
sys.path.insert(0, {src!r})
result = {{}}
t0 = time.perf_counter()
{body}
result["watched_loaded"] = [m for m in {watched!r} if m in sys.modules]
print("BENCH_RESULT=" + json.dumps(result))
"""

PROBES: dict[str, str] = {
    "import uagent.cli": (
        "import uagent.cli\n" "result['ms'] = (time.perf_counter() - t0) * 1000\n"
    ),
    "import uagent.uagent_llm": (
        "import uagent.uagent_llm\n"
        "result['ms'] = (time.perf_counter() - t0) * 1000\n"
    ),
    "tools: load plugins": (
        "import uagent.tools as T\n"
        "t1 = time.perf_counter()\n"
        "T._ensure_loaded()\n"
        "result['ms'] = (time.perf_counter() - t1) * 1000\n"
    ),
    "tools: catalog (en)": (
        "import uagent.tools as T\n"
        "T._ensure_loaded()\n"
        "t1 = time.perf_counter()\n"
        "T.get_tool_catalog(query='read file')\n"
        "result['ms'] = (time.perf_counter() - t1) * 1000\n"
    ),
    "tools: catalog (ja, first)": (
        "import uagent.tools as T\n"
        "T._ensure_loaded()\n"
        "t1 = time.perf_counter()\n"
        "T.get_tool_catalog(query='ファイル 検索')\n"
        "result['ms'] = (time.perf_counter() - t1) * 1000\n"
    ),
}


def _run_probe(body: str) -> dict:
    code = _PROBE_TEMPLATE.format(src=str(SRC_DIR), body=body, watched=WATCHED_MODULES)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONIOENCODING"] = "utf-8"
    # Tool warmup and auto-install must not skew or block the measurement.
    env["UAGENT_TOOLS_WARMUP"] = "0"
    env.setdefault("UAGENT_AUTO_INSTALL", "off")
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("BENCH_RESULT="):
            return json.loads(line[len("BENCH_RESULT=") :])
    raise RuntimeError(
        f"probe failed (exit {proc.returncode}):\n{proc.stderr.strip()[-2000:]}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=5, help="measured runs per probe")
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.add_argument(
        "--only", action="append", default=[], help="run only probes containing TEXT"
    )
    args = parser.parse_args()

    report: dict[str, dict] = {}
    for name, body in PROBES.items():
        if args.only and not any(token in name for token in args.only):
            continue
        _run_probe(body)  # warm-up: .pyc compilation, OS file cache
        samples = [_run_probe(body) for _ in range(max(1, args.runs))]
        times = [s["ms"] for s in samples]
        report[name] = {
            "median_ms": round(statistics.median(times), 1),
            "min_ms": round(min(times), 1),
            "max_ms": round(max(times), 1),
            "watched_loaded": samples[-1]["watched_loaded"],
        }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    print(f"python {sys.version.split()[0]}  runs={args.runs}  src={SRC_DIR}")
    print(f"{'probe':30} {'median':>9} {'min':>9} {'max':>9}  watched modules loaded")
    for name, row in report.items():
        watched = ", ".join(row["watched_loaded"]) or "-"
        print(
            f"{name:30} {row['median_ms']:8.1f}ms {row['min_ms']:8.1f}ms "
            f"{row['max_ms']:8.1f}ms  {watched}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
