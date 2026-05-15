# -*- coding: utf-8 -*-
"""img2img tool

Purpose:
- Edit an input image with a text prompt and save the result as PNG.
- Optional mask support for partial replacement.

Supported:
- provider: UAGENT_IMG_EDIT_PROVIDER (fallback: UAGENT_PROVIDER)
- model/deployment: UAGENT_<PROVIDER>_IMG_EDIT_DEPNAME
  Fallback to UAGENT_<PROVIDER>_IMG_GENERATE_DEPNAME when EDIT_DEPNAME is not set.

Notes:
- Designed as a lightweight img2img wrapper for OpenAI / Azure OpenAI image edit APIs.
- Gemini / Vertex AI are supported for image+prompt editing.
- Mask editing is supported only for OpenAI / Azure OpenAI in this tool.
"""

from __future__ import annotations

import base64
import os
import ssl
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.request import Request, urlopen

from ..env_utils import env_get
from .context import get_callbacks
from .i18n_helper import make_tool_translator
from .openers import open_image_with_default_app
from .response_util import make_response

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:img2img"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "img2img",
        "description": _(
            "tool.description",
            default=(
                "Edit an input image using a text prompt, save the result as a PNG, and return the saved path."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Edit the provided image according to the prompt. Save the result as a PNG and return only the saved file path."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": _(
                        "param.image_path.description",
                        default="Path to the source image to edit.",
                    ),
                },
                "prompt": {
                    "type": "string",
                    "description": _(
                        "param.prompt.description",
                        default="Instructions for how to edit the image.",
                    ),
                },
                "mask_path": {
                    "type": "string",
                    "description": _(
                        "param.mask_path.description",
                        default=(
                            "Optional path to a mask image. Transparent areas are treated as editable in many APIs."
                        ),
                    ),
                },
                "size": {
                    "type": "string",
                    "description": _(
                        "param.size.description",
                        default="Image size. E.g., 1024x1024 / 1024x1536 / 1536x1024 / auto",
                    ),
                    "default": "1024x1024",
                },
                "n": {
                    "type": "integer",
                    "description": _(
                        "param.n.description",
                        default="Number of images to generate (currently 1 is recommended).",
                    ),
                    "default": 1,
                    "minimum": 1,
                    "maximum": 4,
                },
                "output_dir": {
                    "type": "string",
                    "description": _(
                        "param.output_dir.description",
                        default=(
                            "Directory to save images (relative or absolute). Defaults to outputs/image_generations if omitted."
                        ),
                    ),
                },
                "file_prefix": {
                    "type": "string",
                    "description": _(
                        "param.file_prefix.description",
                        default="Prefix for the saved filename (optional).",
                    ),
                    "default": "img2img",
                },
                "quality": {
                    "type": "string",
                    "description": _(
                        "param.quality.description",
                        default="Image quality (optional; e.g. auto/high/medium/low).",
                    ),
                },
                "background": {
                    "type": "string",
                    "description": _(
                        "param.background.description",
                        default="Image background (optional; e.g. auto/transparent).",
                    ),
                },
            },
            "required": ["image_path", "prompt"],
        },
    },
}


class _StatusSpinner:
    def __init__(self, cb: Any, base_label: str) -> None:
        self._cb = cb
        self._base_label = base_label

    def start(self) -> None:
        if not self._cb or not getattr(self._cb, "set_status", None):
            return
        try:
            self._cb.set_status(True, self._base_label)
        except Exception:
            pass

    def stop(self) -> None:
        pass


def _msg(key: str, default: str, **kwargs: Any) -> str:
    return _(key, default=default).format(**kwargs)


def _env_first(keys: List[str], *, required: bool = False, default: str = "") -> str:
    for k in keys:
        v = (env_get(k) or "").strip()
        if v:
            return v
    if required:
        raise RuntimeError(
            _msg(
                "err.required_env_vars_missing",
                "required env var is missing (tried: {keys})",
                keys=", ".join(keys),
            )
        )
    return default


def _img_env(
    provider: str, mode: str, name: str, *, required: bool, default: str = ""
) -> str:
    p = provider.strip().upper()
    m = mode.strip().upper()
    n = name.strip().upper()
    keys = [f"UAGENT_{p}_IMG_{m}_{n}", f"UAGENT_{p}_{n}"]
    return _env_first(keys, required=required, default=default)


def _provider() -> str:
    # 1. Try dedicated env vars
    p = (
        (
            env_get("UAGENT_IMG_EDIT_PROVIDER")
            or env_get("UAGENT_IMG_GENERATE_PROVIDER")
            or ""
        )
        .strip()
        .lower()
    )
    if p:
        return p

    # 2. Try global detect_provider logic
    try:
        from ..util_providers import detect_provider

        p = detect_provider().lower()
    except Exception:
        # 3. Fallback to common env var or default
        p = (env_get("UAGENT_PROVIDER") or "openai").strip().lower()

    if p not in ("openai", "azure", "gemini", "vertexai"):
        # If global detection returned something else (e.g. bedrock), fallback to openai for this tool
        return "openai"
    return p


def _ssl_verify_enabled() -> bool:
    v = (env_get("UAGENT_SSL_VERIFY") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _urlopen_kwargs() -> Dict[str, Any]:
    if _ssl_verify_enabled():
        return {}
    return {"context": ssl._create_unverified_context()}


def _ensure_dir(p: str) -> str:
    p2 = os.path.expanduser(p)
    os.makedirs(p2, exist_ok=True)
    return p2


def _is_gpt_image_model(image_model: str) -> bool:
    return image_model.strip().lower().startswith("gpt-image-")


def _save_many(outdir: str, prefix: str, ts: str, b64_list: List[str]) -> List[str]:
    saved: List[str] = []
    for i, b64 in enumerate(b64_list):
        fn = f"{prefix}_{ts}_{i+1}.png" if len(b64_list) > 1 else f"{prefix}_{ts}.png"
        out_path = os.path.join(outdir, fn)
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(b64))
        saved.append(out_path)
    return saved


def _download_to_png(url: str, out_path: str) -> None:
    req = Request(url, headers={"User-Agent": "img2img_tool"})
    with urlopen(req, **_urlopen_kwargs()) as resp:
        raw = resp.read()
    with open(out_path, "wb") as f:
        f.write(raw)


def _make_client(provider: str):
    try:
        from openai import AzureOpenAI, OpenAI
    except Exception as exc:
        raise RuntimeError(
            _msg(
                "err.openai_import",
                "Failed to import openai package: {err}",
                err=repr(exc),
            )
        )

    if provider == "azure":
        base_url = _img_env("azure", "edit", "base_url", required=True).rstrip("/")
        api_key = _img_env("azure", "edit", "api_key", required=True)
        api_version = _img_env("azure", "edit", "api_version", required=True)
        try:
            return AzureOpenAI(
                azure_endpoint=base_url,
                api_key=api_key,
                api_version=api_version,
            )
        except TypeError:
            return AzureOpenAI(
                azure_endpoint=base_url,
                api_key=api_key,
                api_version=api_version,
            )

    api_key = _img_env("openai", "edit", "api_key", required=True)
    base_url = _img_env(
        "openai",
        "edit",
        "base_url",
        required=False,
        default="https://api.openai.com/v1",
    ).rstrip("/")
    try:
        return OpenAI(api_key=api_key, base_url=base_url)
    except TypeError:
        return OpenAI(api_key=api_key, base_url=base_url)


def _make_gemini_client(provider: str):
    try:
        from google import genai
    except Exception as exc:
        raise RuntimeError(
            _msg(
                "err.gemini_import",
                "Failed to import google-genai package: {err}",
                err=repr(exc),
            )
        )

    kwargs: Dict[str, Any] = {}
    try:
        from .. import util_providers as providers  # type: ignore

        httpx_client = providers.make_httpx_client(verify=_ssl_verify_enabled())
        if httpx_client is not None:
            kwargs["http_options"] = {"httpx_client": httpx_client}
    except Exception:
        pass

    if provider == "vertexai":
        api_key = _img_env("vertexai", "edit", "api_key", required=False)
        return genai.Client(vertexai=True, api_key=api_key, **kwargs)

    api_key = _img_env("gemini", "edit", "api_key", required=True)
    return genai.Client(api_key=api_key, **kwargs)


def _get_model(provider: str) -> str:
    # 1. Try environment variables first
    p_up = provider.upper()
    v = _env_first(
        [
            f"UAGENT_{p_up}_IMG_EDIT_DEPNAME",
            f"UAGENT_{p_up}_IMG_GENERATE_DEPNAME",
        ],
        required=False,
        default="",
    )
    if v:
        return v

    # 2. Return provider-specific defaults
    p_low = provider.lower()
    if p_low in ("gemini", "vertexai"):
        return "imagen-3.0-capability-001"
    if p_low == "openai":
        return "gpt-image-1"

    # 3. Fallback to error
    raise RuntimeError(f"No default image model for provider: {provider}")


def _extract_image_items(
    resp: Any,
) -> tuple[List[str], List[str], List[Dict[str, Any]]]:
    b64_list: List[str] = []
    url_list: List[str] = []
    items: List[Dict[str, Any]] = []
    data_list = getattr(resp, "data", None) or []
    for idx, item in enumerate(data_list, start=1):
        item_meta: Dict[str, Any] = {"index": idx}
        b64 = getattr(item, "b64_json", None)
        if b64:
            b64_list.append(b64)
            item_meta["has_b64_json"] = True
        url = getattr(item, "url", None)
        if url:
            url_list.append(url)
            item_meta["url"] = url
        revised_prompt = getattr(item, "revised_prompt", None)
        if revised_prompt:
            item_meta["revised_prompt"] = revised_prompt
        items.append(item_meta)
    return b64_list, url_list, items


def _mime_type_for_image(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def _run_gemini_img2img(
    provider: str,
    image_model: str,
    src: Path,
    prompt: str,
    n: int,
) -> List[str]:
    try:
        from google.genai import types as gemini_types
    except Exception as exc:
        raise RuntimeError(
            _msg(
                "err.gemini_import",
                "Failed to import google-genai package: {err}",
                err=repr(exc),
            )
        )

    client = _make_gemini_client(provider)
    image_bytes = src.read_bytes()
    mime_type = _mime_type_for_image(src)

    contents = [
        gemini_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        prompt,
    ]

    b64_list: List[str] = []
    for _ in range(max(1, n)):
        try:
            config_cls = getattr(gemini_types, "GenerateContentConfig", None)
            if config_cls is not None:
                resp = client.models.generate_content(
                    model=image_model,
                    contents=contents,
                    config=config_cls(response_modalities=["TEXT", "IMAGE"]),
                )
            else:
                resp = client.models.generate_content(
                    model=image_model,
                    contents=contents,
                )
        except Exception:
            raise

        candidates = getattr(resp, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                inline = getattr(part, "inline_data", None) or getattr(
                    part, "inlineData", None
                )
                raw = getattr(inline, "data", None) if inline is not None else None
                if raw:
                    b64_list.append(base64.b64encode(bytes(raw)).decode("ascii"))

        if len(b64_list) >= n:
            break

    if not b64_list:
        raise RuntimeError("Gemini image edit returned no image data")
    return b64_list[:n]


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    image_path = str(args.get("image_path") or "").strip()
    prompt = str(args.get("prompt") or "").strip()
    mask_path = str(args.get("mask_path") or "").strip()
    if not image_path:
        return _msg("err.image_path_empty", "[img2img] image_path is required")
    if not prompt:
        return _msg("err.prompt_empty", "[img2img] prompt is empty")

    src = Path(image_path)
    if not src.exists() or not src.is_file():
        return _msg(
            "err.image_not_found",
            "[img2img] image file not found: {path}",
            path=image_path,
        )

    mask = Path(mask_path) if mask_path else None
    if mask is not None and (not mask.exists() or not mask.is_file()):
        return _msg(
            "err.mask_not_found",
            "[img2img] mask file not found: {path}",
            path=mask_path,
        )

    size = str(args.get("size") or "1024x1024")
    n = max(1, min(4, int(args.get("n") or 1)))

    from uagent.utils.paths import get_image_generations_dir

    default_output_dir = str(get_image_generations_dir())
    output_dir = str(args.get("output_dir") or default_output_dir)
    file_prefix = str(args.get("file_prefix") or "img2img")
    provider = _provider()
    try:
        image_model = _get_model(provider)
    except RuntimeError:
        return _msg(
            "err.depname_missing",
            "[img2img] Image model (deployment name) is not set.\nPlease set UAGENT_<PROVIDER>_IMG_EDIT_DEPNAME or UAGENT_<PROVIDER>_IMG_GENERATE_DEPNAME.",
        )

    try:
        outdir = os.path.abspath(_ensure_dir(output_dir))
    except Exception as e:
        return _msg(
            "err.mkdir_fail", "[img2img] Failed to create output_dir: {err}", err=e
        )

    quality = str(
        args.get("quality") or env_get("UAGENT_IMG_EDIT_QUALITY") or ""
    ).strip()
    background = str(
        args.get("background") or env_get("UAGENT_IMG_EDIT_BACKGROUND") or ""
    ).strip()

    ts = time.strftime("%Y%m%d_%H%M%S")
    spinner = _StatusSpinner(cb, STATUS_LABEL)
    saved: List[str] = []
    url_list: List[str] = []

    try:
        spinner.start()

        if provider in ("gemini", "vertexai"):
            if mask is not None:
                return _msg(
                    "err.mask_unsupported",
                    "[img2img] mask_path is not supported for Gemini/Vertex AI in this tool.",
                )
            b64_list = _run_gemini_img2img(provider, image_model, src, prompt, n)
            saved.extend(_save_many(outdir, file_prefix, ts, b64_list))
        else:
            client = _make_client(provider)
            gen_kwargs: Dict[str, Any] = {
                "model": image_model,
                "prompt": prompt,
                "size": size,
                "n": n,
            }

            if _is_gpt_image_model(image_model):
                gen_kwargs["output_format"] = "png"
                gen_kwargs["quality"] = quality or "auto"
                gen_kwargs["background"] = background or "auto"
            else:
                gen_kwargs["response_format"] = "b64_json"

            with src.open("rb") as image_fp:
                gen_kwargs["image"] = image_fp
                if mask is not None:
                    with mask.open("rb") as mask_fp:
                        gen_kwargs["mask"] = mask_fp
                        resp = client.images.edit(**gen_kwargs)
                else:
                    resp = client.images.edit(**gen_kwargs)

            b64_list, url_list, _items = _extract_image_items(resp)
            if b64_list:
                saved.extend(_save_many(outdir, file_prefix, ts, b64_list))
            if url_list:
                for i, url in enumerate(url_list):
                    fn = (
                        f"{file_prefix}_{ts}_url_{i+1}.png"
                        if len(url_list) > 1
                        else f"{file_prefix}_{ts}_url.png"
                    )
                    out_path = os.path.join(outdir, fn)
                    _download_to_png(url, out_path)
                    saved.append(out_path)
    except Exception as e:
        return _msg(
            "err.gen_fail",
            "[img2img] Image edit failed.\nprovider={provider} model={model} size={size} n={n}\n{err}",
            provider=provider,
            model=image_model,
            size=size,
            n=n,
            err=repr(e),
        )
    finally:
        try:
            spinner.stop()
        except Exception:
            pass

    if not saved:
        return _msg("err.no_saved", "[img2img] Image data was empty")

    attachments = [
        {
            "type": "image",
            "mime": "image/png",
            "name": os.path.basename(path),
            "path": path,
        }
        for path in saved
    ]

    data: Dict[str, Any] = {
        "provider": provider,
        "model": image_model,
        "image_path": str(src),
        "mask_path": str(mask) if mask is not None else None,
        "prompt": prompt,
        "size": size,
        "n": n,
        "output_dir": outdir,
        "saved_files": saved,
        "attachments": attachments,
    }

    open_flag = (env_get("UAGENT_IMAGE_OPEN") or "").strip().lower()
    should_open = not bool(getattr(cb, "is_gui", False)) and open_flag not in (
        "0",
        "false",
        "no",
        "off",
    )
    if should_open:
        opened_any = False
        for path in saved:
            if open_image_with_default_app(path):
                opened_any = True
        if opened_any:
            print("[INFO] Opened image file with the default app.", file=sys.stderr)

    return make_response(True, _msg("ok.generated", "[OK] generated"), data=data)
