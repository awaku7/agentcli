import json
import random
import re
from typing import Any, Dict, List


def _compute_retry_wait_seconds(
    *,
    attempt: int,
    retry_after_header: Any,
    base: float = 2.0,
    cap: float = 120.0,
) -> float:
    """429 等のリトライ待機秒を決める。

    優先順位:
    1) Retry-After / x-ms-retry-after-ms などが取れればそれ
    2) Azure の x-ratelimit-reset-requests / x-ratelimit-reset-tokens を解釈できればそれ
    3) 指数バックオフ + jitter

    注意: reset 系は「秒数」か「UNIX時刻(秒)」のどちらかで返ることがあるため、
    両方を試し、妥当な待機秒(0..cap)に丸める。
    """

    def _parse_retry_after(v: Any) -> float | None:
        try:
            if v is None:
                return None
            if isinstance(v, (int, float)):
                fv = float(v)
                return fv if fv >= 0 else None
            if isinstance(v, str):
                fv = float(v.strip())
                return fv if fv >= 0 else None
        except Exception:
            return None
        return None

    # 1) plain Retry-After like value
    ra = _parse_retry_after(retry_after_header)
    if ra is not None:
        return min(ra, cap)

    # 2) Azure reset headers (may come as dict)
    try:
        if isinstance(retry_after_header, dict):
            # keys might already be normalized to lower-case
            reset_candidates: list[Any] = []
            for k in (
                "x-ratelimit-reset-requests",
                "x-ratelimit-reset-tokens",
                "ratelimit-reset",
                "x-ratelimit-reset",
            ):
                if k in retry_after_header:
                    reset_candidates.append(retry_after_header.get(k))

            # take the maximum (most conservative) among provided resets
            waits: list[float] = []
            for raw in reset_candidates:
                fv = _parse_retry_after(raw)
                if fv is None:
                    continue

                # Heuristic: if it's a large number, treat as epoch seconds.
                # If it's small, treat as delta seconds.
                if fv > 10_000:  # epoch-ish
                    import time

                    delta = fv - time.time()
                    if delta >= 0:
                        waits.append(delta)
                else:
                    waits.append(fv)

            if waits:
                # small jitter to avoid thundering herd
                w = max(waits)
                w = min(cap, w)
                w += random.uniform(0.0, min(1.0, w * 0.05))
                return min(cap, w)
    except Exception:
        pass

    # 3) exponential backoff
    exp = min(cap, base * (2 ** max(0, attempt - 1)))
    jitter = random.uniform(0.0, min(1.0, exp * 0.1))
    return min(cap, exp + jitter)


def _is_rate_limit_error(e: Exception) -> bool:
    """例外が 429(rate limit) 相当かを雑に判定する。"""
    status = getattr(e, "status_code", None) or getattr(e, "status", None)
    if status == 429:
        return True

    resp = getattr(e, "response", None)
    if resp is not None:
        try:
            rstatus = getattr(resp, "status_code", None) or getattr(
                resp, "status", None
            )
            if rstatus == 429:
                return True
        except Exception:
            pass

    s = f"{type(e).__name__}: {e}".lower()
    if "rate limit" in s or "too many requests" in s or "http 429" in s:
        return True

    if "resource exhausted" in s:
        return True

    return False


def _extract_status_code_from_exception(e: Exception) -> Any:
    status = getattr(e, "status_code", None) or getattr(e, "status", None)
    if status is not None:
        return status

    resp = getattr(e, "response", None)
    if resp is not None:
        try:
            rstatus = getattr(resp, "status_code", None) or getattr(
                resp, "status", None
            )
            if rstatus is not None:
                return rstatus
        except Exception:
            pass

    return None


def _extract_headers_from_exception(e: Exception) -> Dict[str, Any]:
    """例外から取得できる範囲でHTTPヘッダを集めて返す（小文字キーで正規化）。"""

    headers: Dict[str, Any] = {}

    resp = getattr(e, "response", None)
    if resp is not None:
        h = getattr(resp, "headers", None)
        if h is not None:
            try:
                for k in getattr(h, "keys", lambda: [])():
                    try:
                        headers[str(k).lower()] = h.get(k)
                    except Exception:
                        pass
            except Exception:
                try:
                    if isinstance(h, dict):
                        for k, v in h.items():
                            headers[str(k).lower()] = v
                except Exception:
                    pass

    h2 = getattr(e, "headers", None)
    if h2 is not None:
        try:
            if isinstance(h2, dict):
                for k, v in h2.items():
                    headers[str(k).lower()] = v
            else:
                for k in getattr(h2, "keys", lambda: [])():
                    try:
                        headers[str(k).lower()] = h2.get(k)
                    except Exception:
                        pass
        except Exception:
            pass

    return headers


def _extract_body_snippet_from_exception(e: Exception, max_chars: int = 800) -> str:
    """例外からレスポンス本文っぽいものを最大 max_chars だけ取り出す（安全のため短く）。"""

    resp = getattr(e, "response", None)
    if resp is not None:
        try:
            t = getattr(resp, "text", None)
            if isinstance(t, str) and t:
                t2 = t.replace("\r", " ").replace("\n", " ")
                return t2[:max_chars]
        except Exception:
            pass

        try:
            c = getattr(resp, "content", None)
            if isinstance(c, (bytes, bytearray)) and c:
                try:
                    t3 = bytes(c).decode("utf-8", errors="replace")
                except Exception:
                    t3 = repr(c)
                t3 = t3.replace("\r", " ").replace("\n", " ")
                return t3[:max_chars]
        except Exception:
            pass

    try:
        b = getattr(e, "body", None)
        if b is not None:
            if isinstance(b, (dict, list)):
                s = json.dumps(b, ensure_ascii=False)
            else:
                s = str(b)
            s = s.replace("\r", " ").replace("\n", " ")
            return s[:max_chars]
    except Exception:
        pass

    return ""


def _extract_retry_after(e: Exception) -> Any:
    """例外から Retry-After 相当を可能な範囲で取り出す。"""

    headers = _extract_headers_from_exception(e)

    for key in (
        "retry-after",
        "Retry-After",
        "x-retry-after",
    ):
        v = headers.get(str(key).lower())
        if v is not None:
            return v

    # OpenAI 互換の rate limit ヘッダ
    # - x-ratelimit-reset-requests
    # - x-ratelimit-reset-tokens
    # 値は「次のウィンドウまでの秒数」を返すケースが多いが、
    # 実装やゲートウェイ(Azure等)により文字列形式の揺れがあるため
    # ここでは「秒数に解釈できたら秒数(float)を返す」方針にする。
    for key in (
        "x-ratelimit-reset-tokens",
        "x-ratelimit-reset-requests",
    ):
        v = headers.get(str(key).lower())
        if v is None:
            continue

        # Some gateways (including Azure) may return:
        # - seconds until reset (e.g., "10", "10s")
        # - unix epoch seconds (e.g., "1730000000")
        # - RFC3339 timestamp (e.g., "2026-02-24T10:00:00Z")
        try:
            s0 = str(v).strip()
            s = s0
            if s.endswith("s"):
                s = s[:-1].strip()

            # Try numeric first.
            fv = float(s)
            if fv >= 0:
                # Heuristic: very large values are likely unix epoch seconds.
                # (seconds-until-reset is typically small.)
                if fv >= 1_000_000_000:
                    try:
                        import time

                        now = time.time()
                        return max(0.0, fv - now)
                    except Exception:
                        return fv
                return fv
        except Exception:
            pass

        # Try RFC3339 timestamp.
        try:
            import datetime
            import time

            s = s0
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            reset_ts = dt.timestamp()
            return max(0.0, reset_ts - time.time())
        except Exception:
            continue

    for key in (
        "retry-after-ms",
        "x-ms-retry-after-ms",
    ):
        v = headers.get(str(key).lower())
        if v is None:
            continue
        try:
            ms = float(str(v).strip())
            if ms >= 0:
                return ms / 1000.0
        except Exception:
            continue

    # エラーボディ(JSON)の解析を試みる (Gemini / Google API 形式)
    try:
        body_str = _extract_body_snippet_from_exception(e, max_chars=4000)
        if body_str:
            # "retryDelay": "46s" のような形式を検索
            delay_match = re.search(r'"retryDelay":\s*"(\d+(\.\d+)?)s"', body_str)
            if delay_match:
                return float(delay_match.group(1))

            # JSON構造としてパースを試みる
            try:
                data = json.loads(body_str)
                # error.details[] 配下の retryDelay を探す
                details = data.get("error", {}).get("details", [])
                if isinstance(details, list):
                    for det in details:
                        rd = det.get("retryDelay")
                        if isinstance(rd, str) and rd.endswith("s"):
                            try:
                                return float(rd[:-1])
                            except Exception:
                                pass
            except Exception:
                pass
    except Exception:
        pass

    # エラーメッセージテキスト内の "Please retry in ...s" からの抽出
    try:
        msg = str(e)
        m = re.search(r"Please retry in (\d+(\.\d+)?)s", msg)
        if m:
            return float(m.group(1))
    except Exception:
        pass

    return None


def _format_selected_headers(headers: Dict[str, Any]) -> List[str]:
    """デバッグに有用なヘッダのみ抽出して 'k=v' の配列で返す。"""

    out: List[str] = []

    for k in (
        "retry-after",
        "retry-after-ms",
        "x-ms-retry-after-ms",
        "x-ratelimit-reset-tokens",
        "x-ratelimit-reset-requests",
    ):
        if k in headers:
            out.append(f"{k}={headers.get(k)!r}")

    for k, v in sorted(headers.items()):
        if k.startswith("x-ratelimit") or k.startswith("ratelimit"):
            out.append(f"{k}={v!r}")

    for k in (
        "x-request-id",
        "x-ms-request-id",
        "apim-request-id",
    ):
        if k in headers:
            out.append(f"{k}={headers.get(k)!r}")

    return out


def _log_rate_limit_debug(
    *,
    provider: str,
    model: str,
    attempt: int,
    max_retries: int,
    exception: Exception,
    wait_seconds: float,
    retry_after: Any,
) -> None:
    """429/ResourceExhausted時のデバッグ情報を stderr に出す。

    表示は 1 行に抑える（詳細ヘッダ/ボディ/例外全文は出さない）。
    """

    import sys

    status = _extract_status_code_from_exception(exception)

    print(
        f"[RATE_LIMIT] provider={provider} model={model} "
        f"status={status!r} attempt={attempt}/{max_retries} "
        f"wait={wait_seconds:.1f}s retry_after={retry_after!r}",
        file=sys.stderr,
    )
