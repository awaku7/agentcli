#!/usr/bin/env python3
"""Inspect Ollama/OpenAI-compatible models and probe whether they accept image input.

Environment variables:
  - UAGENT_OLLAMA_BASE_URL
  - UAGENT_OLLAMA_DEPNAME

Endpoints:
  - GET /v1/models
  - GET /api/tags
  - POST /api/show
  - POST /api/chat

Default probe image: Scripts/test.jpg next to this script.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or default).strip()


def _normalize_base_url(url: str) -> str:
    url = (url or "http://localhost:11434").strip().rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]
    return url or "http://localhost:11434"


DEFAULT_BASE_URL = _normalize_base_url(
    _env("UAGENT_OLLAMA_BASE_URL", "http://localhost:11434")
)
DEFAULT_MODEL = ""  # ignore UAGENT_OLLAMA_DEPNAME; use --model only
DEFAULT_IMAGE = Path(__file__).with_name("test.jpg")


@dataclass
class ModelInfo:
    name: str
    family: str = ""
    parameter_size: str = ""
    quantization_level: str = ""
    digest: str = ""
    modified_at: str = ""
    source: str = ""
    probe_ok: Optional[bool] = None
    probe_error: str = ""


def http_json(
    method: str, url: str, payload: Optional[dict] = None, timeout: int = 30
) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def list_models_v1(base_url: str, timeout: int) -> List[Dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/v1/models"
    print(f"[INFO] trying endpoint: {url}")
    data = http_json("GET", url, timeout=timeout)
    items = data.get("data", [])
    if not isinstance(items, list):
        raise RuntimeError("Unexpected /v1/models response: data is not a list")
    models: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            models.append(
                {
                    "name": str(item.get("id", "")),
                    "digest": str(item.get("id", "")),
                    "modified_at": str(item.get("created", "")),
                    "source": "v1",
                }
            )
    print(f"[INFO] /v1/models returned {len(models)} models")
    return models


def list_models_native(base_url: str, timeout: int) -> List[Dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/api/tags"
    print(f"[INFO] trying endpoint: {url}")
    data = http_json("GET", url, timeout=timeout)
    items = data.get("models", [])
    if not isinstance(items, list):
        raise RuntimeError("Unexpected /api/tags response: models is not a list")
    models: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            models.append(
                {
                    "name": str(item.get("name", "")),
                    "digest": str(item.get("digest", "")),
                    "modified_at": str(item.get("modified_at", "")),
                    "source": "native",
                }
            )
    print(f"[INFO] /api/tags returned {len(models)} models")
    return models


def get_models(base_url: str, timeout: int) -> List[Dict[str, Any]]:
    errors: List[str] = []
    for choice in ("v1", "native"):
        try:
            if choice == "v1":
                return list_models_v1(base_url, timeout)
            return list_models_native(base_url, timeout)
        except Exception as e:
            print(f"[WARN] {choice} model list failed: {e}", file=sys.stderr)
            errors.append(f"{choice}: {e}")
    raise RuntimeError("; ".join(errors))


def get_model_details(base_url: str, model_name: str, timeout: int) -> Dict[str, Any]:
    return http_json(
        "POST",
        f"{base_url.rstrip('/')}/api/show",
        payload={"name": model_name},
        timeout=timeout,
    )


def load_image_b64(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode("ascii")


def probe_image_support(
    base_url: str, model_name: str, timeout: int, image_path: Path
) -> tuple[bool, str]:
    prompt = (
        "Can you analyze images and transcribe audio? Reply only one JSON object with boolean values "
        'for both keys: {"can_analyze_images": true/false, "can_transcribe_audio": true/false}.'
    )
    if not image_path.exists():
        return False, f"image not found: {image_path}"
    if not image_path.is_file():
        return False, f"image path is not a file: {image_path}"

    print(f"[INFO]   sending text-only probe: {prompt}")
    text_payload = {
        "model": model_name,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }
    text_reply = ""
    text_can_analyze: Optional[bool] = None
    text_can_transcribe: Optional[bool] = None

    def _parse_bool(value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("true", "yes", "ok", "1"):
                return True
            if lowered in ("false", "no", "ng", "0"):
                return False
        return None

    try:
        data = http_json(
            "POST",
            f"{base_url.rstrip('/')}/api/chat",
            payload=text_payload,
            timeout=timeout,
        )
        message = data.get("message", {})
        text_reply = message.get("content", "") if isinstance(message, dict) else ""
        text_reply = text_reply.strip()
        print(f"[INFO]   text-only response: {text_reply or '(empty)'}")
        try:
            parsed = json.loads(text_reply)
            if isinstance(parsed, dict):
                text_can_analyze = _parse_bool(parsed.get("can_analyze_images"))
                text_can_transcribe = _parse_bool(parsed.get("can_transcribe_audio"))
        except Exception:
            text_can_analyze = None
            text_can_transcribe = None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = str(e)
        print(f"[WARN]   text-only probe HTTP error: {body.strip()}", file=sys.stderr)
        text_reply = body.strip()
    except Exception as e:
        print(f"[WARN]   text-only probe failed: {e}", file=sys.stderr)
        text_reply = str(e)

    if text_can_analyze is False:
        print("[INFO]   text-only probe says false; skipping image probe")
        return False, (
            f"text_only={text_reply or '(empty)'}; "
            f"can_analyze_images={text_can_analyze}; can_transcribe_audio={text_can_transcribe}; image=skipped"
        )
    if text_can_analyze is None:
        print(
            "[INFO]   text-only probe did not return valid JSON; skipping image probe"
        )
        return False, (
            f"text_only={text_reply or '(empty)'}; "
            f"can_analyze_images={text_can_analyze}; can_transcribe_audio={text_can_transcribe}; image=skipped_invalid_json"
        )

    print(f"[INFO]   sending image probe: {image_path}")
    image_payload = {
        "model": model_name,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [load_image_b64(image_path)],
            }
        ],
    }
    try:
        data = http_json(
            "POST",
            f"{base_url.rstrip('/')}/api/chat",
            payload=image_payload,
            timeout=timeout,
        )
        message = data.get("message", {})
        content = message.get("content", "") if isinstance(message, dict) else ""
        content = content.strip()
        print(f"[INFO]   image response: {content or '(empty)'}")
        if content.upper() == "OK":
            return True, (
                f"text_only={text_reply or '(empty)'}; "
                f"can_analyze_images={text_can_analyze}; can_transcribe_audio={text_can_transcribe}; image={content}"
            )
        return False, (
            f"text_only={text_reply or '(empty)'}; "
            f"can_analyze_images={text_can_analyze}; can_transcribe_audio={text_can_transcribe}; "
            f"image={content or 'unexpected response'}"
        )
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = str(e)
        print(f"[WARN]   image probe HTTP error: {body.strip()}", file=sys.stderr)
        return False, (
            f"text_only={text_reply or '(empty)'}; "
            f"can_analyze_images={text_can_analyze}; can_transcribe_audio={text_can_transcribe}; "
            f"image_error={body.strip()}"
        )
    except Exception as e:
        print(f"[WARN]   image probe failed: {e}", file=sys.stderr)
        return False, (
            f"text_only={text_reply or '(empty)'}; "
            f"can_analyze_images={text_can_analyze}; can_transcribe_audio={text_can_transcribe}; image_error={e}"
        )


def to_model_info(model: Dict[str, Any], details: Dict[str, Any]) -> ModelInfo:
    model_obj = (
        details.get("model", {}) if isinstance(details.get("model", {}), dict) else {}
    )
    return ModelInfo(
        name=str(model.get("name", "")),
        family=str(model_obj.get("family", "")),
        parameter_size=str(model_obj.get("parameter_size", "")),
        quantization_level=str(model_obj.get("quantization_level", "")),
        digest=str(model.get("digest", "")),
        modified_at=str(model.get("modified_at", "")),
        source=str(model.get("source", "")),
    )


def print_table(rows: List[ModelInfo]) -> None:
    headers = ["model", "source", "family", "size", "quant", "probe_ok", "probe_info"]
    widths = [
        max(len(headers[0]), *(len(r.name) for r in rows)) if rows else len(headers[0]),
        (
            max(len(headers[1]), *(len(r.source) for r in rows))
            if rows
            else len(headers[1])
        ),
        (
            max(len(headers[2]), *(len(r.family) for r in rows))
            if rows
            else len(headers[2])
        ),
        (
            max(len(headers[3]), *(len(r.parameter_size) for r in rows))
            if rows
            else len(headers[3])
        ),
        (
            max(len(headers[4]), *(len(r.quantization_level) for r in rows))
            if rows
            else len(headers[4])
        ),
        len(headers[5]),
        (
            max(
                len(headers[6]),
                *(len((r.probe_error or "").replace("\\n", " ")) for r in rows),
            )
            if rows
            else len(headers[6])
        ),
    ]

    def fmt(val: str, width: int) -> str:
        return val.ljust(width)

    print("  ".join(fmt(h, w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        probe_ok = "" if row.probe_ok is None else ("yes" if row.probe_ok else "no")
        probe_info = (row.probe_error or "").replace("\\n", " ")
        print(
            "  ".join(
                [
                    fmt(row.name, widths[0]),
                    fmt(row.source, widths[1]),
                    fmt(row.family, widths[2]),
                    fmt(row.parameter_size, widths[3]),
                    fmt(row.quantization_level, widths[4]),
                    fmt(probe_ok, widths[5]),
                    fmt(probe_info, widths[6]),
                ]
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Model API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Optional model filter; only inspect this model if set",
    )
    parser.add_argument(
        "--image",
        default=str(DEFAULT_IMAGE),
        help=f"Probe image path (default: {DEFAULT_IMAGE})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="HTTP timeout seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--probe", action="store_true", help="Try an image request for every model"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output JSON instead of a text table"
    )
    args = parser.parse_args()

    base_url = _normalize_base_url(args.base_url)
    image_path = Path(args.image)
    print(f"[INFO] base_url = {base_url}")
    print(f"[INFO] probe_image = {image_path}")

    try:
        models = get_models(base_url, args.timeout)
    except Exception as e:
        print(
            f"[ERROR] Failed to fetch model list from {base_url}: {e}", file=sys.stderr
        )
        return 1

    print(f"[INFO] models found = {len(models)}")

    if args.model:
        models = [m for m in models if str(m.get("name", "")) == args.model]
        print(f"[INFO] models after filter = {len(models)}")
        if not models:
            print(
                f"[WARN] model {args.model!r} was not found in the selected endpoint",
                file=sys.stderr,
            )

    results: List[ModelInfo] = []
    for index, model in enumerate(models, start=1):
        name = str(model.get("name", ""))
        print(f"[INFO] ({index}/{len(models)}) inspecting {name}")
        try:
            details = get_model_details(base_url, name, args.timeout)
            print(f"[INFO]   show ok: {name}")
        except Exception as e:
            print(f"[WARN]   show failed: {name}: {e}", file=sys.stderr)
            details = {}
            info = ModelInfo(name=name, probe_error=f"show failed: {e}")
            results.append(info)
            continue

        info = to_model_info(model, details)
        if args.probe:
            print(f"[INFO]   probing {name}")
            ok, probe_text = probe_image_support(
                base_url, name, args.timeout, image_path
            )
            info.probe_ok = ok
            info.probe_error = probe_text
        results.append(info)

    if args.json:
        payload = [
            {
                "name": r.name,
                "source": r.source,
                "family": r.family,
                "parameter_size": r.parameter_size,
                "quantization_level": r.quantization_level,
                "digest": r.digest,
                "modified_at": r.modified_at,
                "probe_ok": r.probe_ok,
                "probe_info": r.probe_error,
            }
            for r in results
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print_table(results)
    if not results:
        print()
        print("No models found.")
    elif not args.probe:
        print()
        print("Hint: use --probe to test image input on every model.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
