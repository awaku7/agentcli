# tools/fetch_url.py
from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)

from typing import Any, Dict
import ssl
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from .context import get_callbacks

BUSY_LABEL = True
STATUS_LABEL = "tool:fetch_url"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "fetch_url",
        "description": "指定した URL に HTTP GET でアクセスし、レスポンスの先頭部分をテキストとして返します。HTML や JSON の内容を取得・解析したいときに使います。",
        "system_prompt": """このツールは次の目的で使われます: 指定した URL に HTTP GET でアクセスし、レスポンスの先頭部分をテキストとして返します。HTML や JSON の内容を取得・解析したいときに使います。""",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "アクセスする URL（http:// または https://）。",
                }
            },
            "required": ["url"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    """URL から内容を取得する。"""

    cb = get_callbacks()

    url = args.get("url", "")
    if not url:
        return (
            "[fetch_url error] url が空です。\n"
            "このツールは必須引数 url を要求します。次は必ず JSON オブジェクトで url を渡してください。\n"
            '例: {"url": "https://wttr.in/?format=j1"}\n'
            "目的が『今日の天気』なら、地域指定も可能です（例: https://wttr.in/Tokyo?format=j1）。"
        )

    import sys

    print("[url] " + url, file=sys.stderr)
    req = Request(url, headers={"User-Agent": "curl/7.79.1"})

    def do_request(unverified: bool = False):
        ctx = ssl._create_unverified_context() if unverified else None
        with urlopen(
            req, timeout=cb.url_fetch_timeout_ms / 1000.0, context=ctx
        ) as resp:
            raw = resp.read(cb.url_fetch_max_bytes + 1)
            status = resp.getcode()
            ct = resp.headers.get("Content-Type", "")
        return raw, status, ct

    note = ""
    raw = b""
    status = "N/A"
    ct = ""

    try:
        try:
            raw, status, ct = do_request(False)
        except HTTPError as e:
            status = getattr(e, "code", "N/A")
            try:
                ct = (
                    e.headers.get("Content-Type", "")
                    if getattr(e, "headers", None)
                    else ""
                )
            except Exception:
                ct = ""
            meta = f"[fetch_url] url={url}, status={status}, content-type={ct}\n"
            return meta + f"[fetch_url error] HTTPError {e.code}: {e.reason}"
        except URLError as e:
            if isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError):
                try:
                    raw, status, ct = do_request(True)
                    note = (
                        "[fetch_url warning] SSL 証明書の検証に失敗したため、"
                        "このリクエストでは証明書検証を無効化してアクセスしました。\n"
                    )
                except Exception as e2:
                    status = "N/A"
                    meta = (
                        f"[fetch_url] url={url}, status={status}, content-type={ct}\n"
                    )
                    return meta + f"[fetch_url error] {type(e2).__name__}: {e2}"
            else:
                status = "N/A"
                meta = f"[fetch_url] url={url}, status={status}, content-type={ct}\n"
                return meta + f"[fetch_url error] URLError: {e.reason}"
    except Exception as e:
        status = "N/A"
        meta = f"[fetch_url] url={url}, status={status}, content-type={ct}\n"
        return meta + f"[fetch_url error] {type(e).__name__}: {e}"

    truncated_note = ""
    if len(raw) > cb.url_fetch_max_bytes:
        raw = raw[: cb.url_fetch_max_bytes]
        truncated_note = f"\n[fetch_url truncated: response truncated to {cb.url_fetch_max_bytes} bytes]"

    lower_ct = (ct or "").lower()
    charset = "utf-8"
    if "charset=" in lower_ct:
        for part in ct.split(";"):
            part = part.strip()
            if part.lower().startswith("charset="):
                charset = part.split("=", 1)[1].strip()
                break

    try:
        text = raw.decode(charset, errors="replace")
    except Exception:
        text = raw.decode("utf-8", errors="replace")

    meta = f"[fetch_url] url={url}, status={status}, content-type={ct}\n"
    return note + meta + text + truncated_note
