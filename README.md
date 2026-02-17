# uag (Local Tool-Execution Agent)

uag is an interactive local agent that can execute commands, manipulate files, and read various data formats (PDF/PPTX/Excel, etc.) on your PC.

- CLI: `uag` / `python -m uagent`
- GUI: `uagg` / `python -m uagent.gui`
- Web: `uagw` / `python -m uagent.web`

---

## Documentation (`uag docs`)

Even when installed from a wheel (whl), bundled documents are available via `uag docs`.

```bash
uag docs
uag docs webinspect
uag docs develop
uag docs --path webinspect
uag docs --open webinspect
```

---

## Install (distribution: wheel)

See **`QUICKSTART.md`** for the Windows-oriented installation steps using a distributed `.whl`.

- Distribution: GitHub **Releases** page (Assets: `.whl`)
- Wheel example: `uag-<VERSION>-py3-none-any.whl`

Example:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ./uag-<VERSION>-py3-none-any.whl
```

Notes:
- `uag` requires **Python 3.11+**.
- For development use, `python -m pip install -e .` (or `python -m pip install -e \".[web]\"` if you use the Web UI).

---
