# QUICKSTART (uag / Windows)

This document explains how to install a distributed `uag` wheel (`uag-<VERSION>-py3-none-any.whl`) with **pip**, and verify the minimum setup using the CLI (`uag`).

Target OS: Windows

---

## 0. Documentation (`uag docs`)

After installation, bundled documents are available via `uag docs`.

```bat
uag docs
uag docs webinspect
uag docs develop
uag docs --open webinspect
```

---

## 1. Prerequisites

- Python **3.11+** (`requires-python = ">=3.11"` in `pyproject.toml`)
- (Recommended) Use a virtual environment (venv)
- After installation, start with `uag` (or `python -m uagent` if `uag` is not found)

---

## 2. Prepare a working folder

- Place the distributed `uag-<VERSION>-py3-none-any.whl` into a working folder
- Run the commands below in that folder

---

## 3. Create a virtual environment (recommended)

Run in the working folder:

```bat
python -m venv .venv
.\\.venv\\Scripts\\activate
```

(If you use PowerShell, you may need to update the execution policy and then re-run `activate`.)

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

## 4. Install the wheel with pip

Check the wheel file name:

```bat
dir *.whl
```

Install specifying the file name:

```bat
python -m pip install .\\uag-<VERSION>-py3-none-any.whl
```

(If there is only one wheel file, this is also fine.)

```bat
python -m pip install .\\uag-*.whl
```

---

## 5. Verify installation

```bat
uag --help
where uag
python -c \"import uagent; print(getattr(uagent, '__version__', 'ok'))\" 
```

If `where uag` does not find the command, you can start with:

```bat
python -m uagent --help
```

---
