"""Secure storage for the pybitchat long-lived identity.

Prefer the operating system credential store. Fall back to the same AES-GCM
file encryption used by ``.env.sec`` when no native backend is available.
"""

from __future__ import annotations

import getpass
import os
import subprocess
from pathlib import Path

_SERVICE = "uag.bitchat.identity"
_ACCOUNT = getpass.getuser() or "default"


def _run_security(args: list[str], *, input_text: str | None = None) -> str | None:
    try:
        result = subprocess.run(
            args,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.rstrip("\r\n")


def _native_load() -> str | None:
    if os.name == "nt":
        try:
            import win32cred

            cred = win32cred.CredRead(_SERVICE, win32cred.CRED_TYPE_GENERIC, 0)
            blob = cred.get("CredentialBlob", b"")
            return bytes(blob).decode("utf-8") if blob else None
        except Exception:
            return None
    if sys_platform() == "darwin":
        return _run_security(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-a",
                _ACCOUNT,
                "-s",
                _SERVICE,
                "-w",
            ]
        )
    if sys_platform() == "linux":
        return _run_security(
            ["secret-tool", "lookup", "service", _SERVICE, "account", _ACCOUNT]
        )
    return None


def _native_save(plaintext: str) -> bool:
    if os.name == "nt":
        try:
            import win32cred

            win32cred.CredWrite(
                {
                    "Type": win32cred.CRED_TYPE_GENERIC,
                    "TargetName": _SERVICE,
                    "UserName": _ACCOUNT,
                    "CredentialBlob": plaintext.encode("utf-8"),
                    "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
                },
                0,
            )
            return True
        except Exception:
            return False
    if sys_platform() == "darwin":
        return (
            _run_security(
                [
                    "/usr/bin/security",
                    "add-generic-password",
                    "-a",
                    _ACCOUNT,
                    "-s",
                    _SERVICE,
                    "-w",
                    plaintext,
                    "-U",
                ]
            )
            is not None
        )
    if sys_platform() == "linux":
        try:
            result = subprocess.run(
                [
                    "secret-tool",
                    "store",
                    "--label",
                    _SERVICE,
                    "service",
                    _SERVICE,
                    "account",
                    _ACCOUNT,
                ],
                input=plaintext,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False
    return False


def sys_platform() -> str:
    import sys

    return sys.platform


def load_identity(*, fallback_path: str | Path) -> str | None:
    """Load identity JSON from native storage or the .env.sec-style fallback."""
    native = _native_load()
    if native:
        return native
    path = Path(fallback_path)
    if not path.exists():
        return None
    try:
        from uag_envsec.secret_core import decrypt_text

        return decrypt_text(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def save_identity(plaintext: str, *, fallback_path: str | Path) -> str:
    """Save identity to native storage, falling back to AES-GCM file storage."""
    if _native_save(plaintext):
        return "native"
    from uag_envsec.secret_core import encrypt_text, ensure_key_file

    ensure_key_file()
    path = Path(fallback_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(encrypt_text(plaintext) + "\n", encoding="utf-8", newline="\n")
        tmp.replace(path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return "envsec"


def delete_legacy(path: str | Path) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass
