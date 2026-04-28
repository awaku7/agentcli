# tools/generate_image_tool.py
# -*- coding: utf-8 -*-
"""generate_image tool

Purpose:
- Generate an image from a text prompt, save it as a PNG file, and return the path.
- Opening is handled by the caller (CLI/GUI/Web).

Supported:
- provider: UAGENT_IMG_GENERATE_PROVIDER (fallback: UAGENT_PROVIDER)
- model/deployment: UAGENT_<PROVIDER>_IMG_GENERATE_DEPNAME

Note:
- Image generation APIs depend on provider/SDK support, subscription, and region.
  In case of error, check differences in model/permissions/response format.
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import time
from typing import Any, Dict, List

from ..env_utils import env_get
from ..util_tools import open_image_with_default_app
from .context import get_callbacks
from .i18n_helper import make_tool_translator
from .response_util import make_response

_ = make_tool_translator(__file__)


def _msg(key: str, default: str, **kwargs: Any) -> str:
    return _(key, default=default).format(**kwargs)


BUSY_LABEL = True
STATUS_LABEL = "tool:generate_image"


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


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_image",
        "description": _(
            "tool.description",
            default="Generates an image from a text prompt, saves it as a PNG, and returns the file path. Opening is handled by the caller (CLI/GUI/Web).",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="Generate an image from the provided prompt. Save it as a PNG and return only the saved file path.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": _(
                        "param.prompt.description",
                        default="Instructions (prompt) for the image you want to generate.",
                    ),
                },
                "size": {
                    "type": "string",
                    "description": _(
                        "param.size.description",
                        default="Image size. E.g., 1024x1024 / 1024x1536 / 1536x1024",
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
                        default="Directory to save images (relative or absolute). Defaults to outputs/image_generations if omitted.",
                    ),
                },
                "file_prefix": {
                    "type": "string",
                    "description": _(
                        "param.file_prefix.description",
                        default="Prefix for the saved filename (optional).",
                    ),
                    "default": "img",
                },
                "moderation": {
                    "type": "string",
                    "description": _(
                        "param.moderation.description",
                        default="Image moderation mode (optional).",
                    ),
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
            "required": ["prompt"],
        },
    },
}


def _get_provider() -> str:
    """Select provider for image generation."""
    p = (
        (
            env_get("UAGENT_IMG_GENERATE_PROVIDER")
            or env_get("UAGENT_PROVIDER")
            or "azure"
        )
        .strip()
        .lower()
    )
    if p not in ("azure", "openai", "bedrock", "openrouter", "gemini", "nvidia"):
        raise RuntimeError(
            _msg(
                "err.invalid_provider",
                "invalid provider for image generation: {provider!r} (UAGENT_IMG_GENERATE_PROVIDER/UAGENT_PROVIDER)",
                provider=p,
            )
        )
    return p


def _env_first(keys: List[str], *, required: bool, default: str = "") -> str:
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
    """Resolve image env vars."""
    p = provider.strip().upper()
    m = mode.strip().upper()
    n = name.strip().upper()
    keys = [f"UAGENT_{p}_IMG_{m}_{n}", f"UAGENT_{p}_{n}"]
    return _env_first(keys, required=required, default=default)


def _ssl_verify_enabled() -> bool:
    """Default: no verification. Enable only if UAGENT_SSL_VERIFY=1/true/yes/on."""
    v = (env_get("UAGENT_SSL_VERIFY") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _env_bool(name: str, default: bool = False) -> bool:
    v = (env_get(name) or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


def _urlopen_kwargs() -> Dict[str, Any]:
    """Generate extra args for urllib. Return unverified context if verification is disabled."""
    if _ssl_verify_enabled():
        return {}
    ctx = ssl._create_unverified_context()
    return {"context": ctx}


def _get_image_depname(cb_get_env, provider: str) -> str:
    return _img_env(provider, "generate", "depname", required=True)


def _ensure_dir(p: str) -> str:
    p2 = os.path.expanduser(p)
    os.makedirs(p2, exist_ok=True)
    return p2


def _write_png_bytes(raw: bytes, out_path: str) -> None:
    with open(out_path, "wb") as f:
        f.write(raw)


def _write_png_from_b64(b64_data: str, out_path: str) -> None:
    raw = base64.b64decode(b64_data)
    _write_png_bytes(raw, out_path)


def _sanitize_size_for_provider(size: str) -> str:
    return size


def _is_gpt_image_model(image_model: str) -> bool:
    return image_model.strip().lower().startswith("gpt-image-")


def _save_many(outdir: str, prefix: str, ts: str, b64_list: List[str]) -> List[str]:
    saved: List[str] = []
    for i, b64 in enumerate(b64_list):
        fn = f"{prefix}_{ts}_{i+1}.png" if len(b64_list) > 1 else f"{prefix}_{ts}.png"
        out_path = os.path.join(outdir, fn)
        _write_png_from_b64(b64, out_path)
        saved.append(out_path)
    return saved


def _download_to_png(url: str, out_path: str) -> None:
    from urllib.request import Request, urlopen

    req = Request(url, headers={"User-Agent": "generate_image_tool"})
    with urlopen(req, **_urlopen_kwargs()) as resp:
        raw = resp.read()
    _write_png_bytes(raw, out_path)


def _run_openai_images(
    provider: str,
    image_model: str,
    prompt: str,
    size: str,
    n: int,
    *,
    moderation: str = "",
    quality: str = "",
    background: str = "",
) -> Dict[str, Any]:
    try:
        from openai import AzureOpenAI, OpenAI
    except Exception as e:
        raise RuntimeError(
            _msg(
                "err.openai_import",
                "Failed to import openai package: {err}",
                err=repr(e),
            )
        )

    http_client = None
    try:
        from .. import util_providers as providers  # type: ignore

        http_client = providers.make_httpx_client(verify=_ssl_verify_enabled())
        if http_client is None:
            raise RuntimeError(
                _("err.httpx_unavailable", default="httpx is not available")
            )
    except Exception as e:
        raise RuntimeError(
            _msg("err.httpx_init", "Failed to initialize httpx: {err}", err=repr(e))
        )

    if provider == "azure":
        base_url = _img_env("azure", "generate", "base_url", required=True).rstrip("/")
        api_key = _img_env("azure", "generate", "api_key", required=True)
        api_version = _img_env("azure", "generate", "api_version", required=True)

        try:
            client = AzureOpenAI(
                azure_endpoint=base_url,
                api_key=api_key,
                api_version=api_version,
                http_client=http_client,
            )
        except TypeError:
            client = AzureOpenAI(
                azure_endpoint=base_url,
                api_key=api_key,
                api_version=api_version,
            )
    else:
        if provider == "nvidia":
            api_key = _img_env("nvidia", "generate", "api_key", required=True)
            base_url = _img_env(
                "nvidia",
                "generate",
                "base_url",
                required=False,
                default="https://integrate.api.nvidia.com/v1",
            ).rstrip("/")
        elif provider == "bedrock":
            api_key = _img_env("bedrock", "generate", "api_key", required=True)
            base_url = _img_env(
                "bedrock", "generate", "base_url", required=True
            ).rstrip("/")
        elif provider == "openrouter":
            api_key = _img_env("openrouter", "generate", "api_key", required=True)
            base_url = _img_env(
                "openrouter",
                "generate",
                "base_url",
                required=False,
                default="https://openrouter.ai/api/v1",
            ).rstrip("/")
        else:
            api_key = _img_env("openai", "generate", "api_key", required=True)
            base_url = _img_env(
                "openai",
                "generate",
                "base_url",
                required=False,
                default="https://api.openai.com/v1",
            ).rstrip("/")

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        except TypeError:
            client = OpenAI(api_key=api_key, base_url=base_url)

    gen_kwargs: Dict[str, Any] = {
        "model": image_model,
        "prompt": prompt,
        "size": size,
        "n": n,
    }
    if moderation:
        gen_kwargs["moderation"] = moderation
    if _is_gpt_image_model(image_model):
        gen_kwargs["output_format"] = "png"
        gen_kwargs["quality"] = quality or "auto"
        gen_kwargs["background"] = background or "auto"
    else:
        gen_kwargs["response_format"] = "b64_json"

    try:
        resp = client.images.generate(**gen_kwargs)
    except Exception:
        raise
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

    if not b64_list and not url_list:
        raise RuntimeError(
            _(
                "err.empty_data",
                default="Image data was empty (resp.data is empty or b64_json/url is missing)",
            )
        )

    return {"b64_list": b64_list, "url_list": url_list, "items": items}


def _run_gemini_images(
    image_model: str,
    prompt: str,
    size: str,
    n: int,
) -> List[str]:
    try:
        from google import genai
        from google.genai import types as gemini_types
    except Exception as e:
        raise RuntimeError(
            _msg(
                "err.gemini_import",
                "Failed to import google-genai package: {err}",
                err=repr(e),
            )
        )

    api_key = _img_env("gemini", "generate", "api_key", required=True)

    kwargs: Dict[str, Any] = {}
    try:
        from .. import util_providers as providers  # type: ignore

        httpx_client = providers.make_httpx_client(verify=_ssl_verify_enabled())
        if httpx_client is not None:
            kwargs["http_options"] = {"httpx_client": httpx_client}
    except Exception:
        pass

    try:
        client = genai.Client(api_key=api_key, **kwargs)
    except TypeError:
        client = genai.Client(api_key=api_key)

    config_kwargs: Dict[str, Any] = {
        "number_of_images": n,
        "output_mime_type": "image/png",
    }
    if size == "1024x1024":
        config_kwargs["aspect_ratio"] = "1:1"
    elif size == "1024x1536":
        config_kwargs["aspect_ratio"] = "2:3"
    elif size == "1536x1024":
        config_kwargs["aspect_ratio"] = "3:2"
    else:
        config_kwargs["image_size"] = size

    resp = client.models.generate_images(
        model=image_model,
        prompt=prompt,
        config=gemini_types.GenerateImagesConfig(**config_kwargs),
    )

    b64_list: List[str] = []
    gen_list = (
        getattr(resp, "generated_images", None) or getattr(resp, "images", None) or []
    )
    for item in gen_list:
        img = getattr(item, "image", None)
        if img is None:
            continue
        raw = getattr(img, "image_bytes", None)
        if raw:
            b64_list.append(base64.b64encode(bytes(raw)).decode("ascii"))

    if not b64_list:
        raise RuntimeError(
            _msg(
                "err.empty_data",
                "Image data was empty (generated_images is empty or image_bytes is missing)",
            )
        )

    return b64_list


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        return _(
            "err.prompt_empty",
            default="[generate_image] prompt is empty",
        )

    size = str(args.get("size") or "1024x1024")
    n = int(args.get("n") or 1)
    n = max(1, min(4, n))

    from uagent.utils.paths import get_image_generations_dir

    default_output_dir = str(get_image_generations_dir())
    output_dir = str(args.get("output_dir") or default_output_dir)
    file_prefix = str(args.get("file_prefix") or "img")
    provider = _get_provider()
    try:
        image_model = _get_image_depname(cb.get_env, provider)
    except RuntimeError:
        return _(
            "err.depname_missing",
            default=(
                "[generate_image] Image model (deployment name) is not set.\n"
                "Please set the environment variable UAGENT_<PROVIDER>_IMG_GENERATE_DEPNAME."
            ),
        )

    try:
        outdir = os.path.abspath(_ensure_dir(output_dir))
    except Exception as e:
        return _msg(
            "err.mkdir_fail",
            "[generate_image] Failed to create output_dir: {err}",
            err=e,
        )

    ts = time.strftime("%Y%m%d_%H%M%S")
    saved: List[str] = []
    spinner = _StatusSpinner(cb, STATUS_LABEL)
    debug = _env_bool("UAGENT_IMG_GENERATE_DEBUG", False)
    save_meta = debug or _env_bool("UAGENT_IMG_GENERATE_SAVE_META", False)
    moderation_raw = str(
        args.get("moderation") or env_get("UAGENT_IMG_GENERATE_MODERATION") or ""
    ).strip()
    moderation = moderation_raw.lower()
    if moderation in ("safe", "standard", "default"):
        moderation = "auto"
    quality = str(
        args.get("quality") or env_get("UAGENT_IMG_GENERATE_QUALITY") or ""
    ).strip()
    background = str(
        args.get("background") or env_get("UAGENT_IMG_GENERATE_BACKGROUND") or ""
    ).strip()
    meta_payload: Dict[str, Any] = {
        "provider": provider,
        "model": image_model,
        "prompt": prompt,
        "size": size,
        "n": n,
        "timestamp": ts,
        "debug": debug,
        "save_meta": save_meta,
        "moderation": moderation or None,
        "quality": quality or None,
        "background": background or None,
    }
    try:
        if debug:
            spinner.start()
        size2 = _sanitize_size_for_provider(size)
        meta_payload["size"] = size2
        if provider in ("openai", "azure", "bedrock", "openrouter", "nvidia"):
            res = _run_openai_images(
                provider=provider,
                image_model=image_model,
                prompt=prompt,
                size=size2,
                n=n,
                moderation=moderation,
                quality=quality,
                background=background,
            )
            b64_list = res.get("b64_list") or []
            url_list = res.get("url_list") or []
            meta_payload["items"] = res.get("items") or []
            if b64_list:
                saved.extend(_save_many(outdir, file_prefix, ts, b64_list))
            if url_list:
                meta_payload["downloaded_urls"] = []
                for i, url in enumerate(url_list):
                    fn = (
                        f"{file_prefix}_{ts}_url_{i+1}.png"
                        if len(url_list) > 1
                        else f"{file_prefix}_{ts}_url.png"
                    )
                    out_path = os.path.join(outdir, fn)
                    _download_to_png(url, out_path)
                    saved.append(out_path)
                    meta_payload["downloaded_urls"].append(url)

        elif provider == "gemini":
            b64_list = _run_gemini_images(
                image_model=image_model,
                prompt=prompt,
                size=size2,
                n=n,
            )
            saved = _save_many(outdir, file_prefix, ts, b64_list)
            meta_payload["items"] = [
                {"index": i + 1, "has_b64_json": True} for i in range(len(b64_list))
            ]
        else:
            return _msg(
                "err.unsupported_provider",
                "[generate_image] Unsupported provider={provider!r}",
                provider=provider,
            )

    except Exception as e:
        return _msg(
            "err.gen_fail",
            "[generate_image] Image generation failed.\nprovider={provider} model={model} size={size} n={n}\n{err}",
            provider=provider,
            model=image_model,
            size=size,
            n=n,
            err=repr(e),
        )
    finally:
        if debug:
            try:
                spinner.stop()
            except Exception:
                pass

    if save_meta:
        meta_payload["saved_files"] = saved
        meta_path = os.path.abspath(os.path.join(outdir, f"{file_prefix}_{ts}.json"))
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_payload, f, ensure_ascii=False, indent=2, default=str)
                f.write("\n")
        except Exception:
            pass

    if not saved:
        return _(
            "err.no_saved",
            default="[generate_image] Image data was empty",
        )

    attachments = []
    for idx, path in enumerate(saved):
        att = {
            "type": "image",
            "mime": "image/png",
            "name": os.path.basename(path),
            "path": path,
        }
        if idx < len(url_list):
            att["url"] = url_list[idx]
            att["source_url"] = url_list[idx]
        attachments.append(att)
    data: Dict[str, Any] = {
        "provider": provider,
        "model": image_model,
        "prompt": prompt,
        "size": size2,
        "n": n,
        "output_dir": outdir,
        "saved_files": saved,
        "attachments": attachments,
    }
    if save_meta:
        data["meta_path"] = meta_path

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
            print(
                "[INFO] Opened image file with the default app.",
                file=sys.stderr,
            )

    return make_response(True, _msg("ok.generated", "[OK] generated"), data=data)
