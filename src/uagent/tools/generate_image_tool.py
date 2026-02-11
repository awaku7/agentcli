# tools/generate_image_tool.py
# -*- coding: utf-8 -*-
"""generate_image tool

目的:
- テキストプロンプトから画像を生成し、PNGファイルとして保存してパスを返す。
- 生成後、自動的に画像を開く（環境変数 UAGENT_IMAGE_OPEN=0 で無効化可能）。

対応:
- UAGENT_PROVIDER=azure / openai / gemini
- 画像用デプロイ名(またはモデル名)は環境変数 UAGENT_IMAGE_DEPNAME

注意:
- 画像生成APIはプロバイダ/SDKの対応状況・契約・リージョンに依存します。
  エラーになった場合は、モデル/権限/レスポンス形式の差を確認してください。
"""

from __future__ import annotations

import base64
import os
import ssl
import subprocess
import time
from typing import Any, Dict, List

from .context import get_callbacks

BUSY_LABEL = True
STATUS_LABEL = "tool:generate_image"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_image",
        "description": "テキストプロンプトから画像を生成し、PNGで保存してファイルパスを返します。生成後、自動で画像を開きます（UAGENT_IMAGE_OPEN=0 で無効化可能）。",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "生成したい画像の指示（プロンプト）",
                },
                "size": {
                    "type": "string",
                    "description": "画像サイズ。例: 1024x1024 / 1024x1536 / 1536x1024",
                    "default": "1024x1024",
                },
                "n": {
                    "type": "integer",
                    "description": "生成枚数（現状は1推奨）",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 4,
                },
                "output_dir": {
                    "type": "string",
                    "description": "保存先ディレクトリ（相対/絶対）。省略時は outputs/image_generations",
                },
                "file_prefix": {
                    "type": "string",
                    "description": "保存ファイル名の接頭辞（省略可）",
                    "default": "img",
                },
            },
            "required": ["prompt"],
        },
    },
}


def _get_provider() -> str:
    # nvidia は OpenAI互換として扱う（images.generate が使える場合）
    return (os.environ.get("UAGENT_PROVIDER") or "azure").lower()


def _ssl_verify_enabled() -> bool:
    """既定は検証なし。

    UAGENT_SSL_VERIFY=1/true/yes/on の場合のみ検証を有効化。
    """

    v = (os.environ.get("UAGENT_SSL_VERIFY") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _urlopen_kwargs() -> Dict[str, Any]:
    """urllib 用の追加引数を生成。検証無効のときは unverified context を渡す。"""

    if _ssl_verify_enabled():
        return {}
    ctx = ssl._create_unverified_context()
    return {"context": ctx}


def _get_image_depname(cb_get_env, provider: str) -> str:
    # ユーザ要望: UAGENT_IMAGE_DEPNAME
    # （Azureの場合はデプロイ名、OpenAI/Geminiの場合はモデル名として扱う）
    v = (os.environ.get("UAGENT_IMAGE_DEPNAME") or "").strip()
    if not v:
        raise RuntimeError("環境変数 UAGENT_IMAGE_DEPNAME が未設定です")
    return v


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


def _open_image(file_path: str) -> None:
    """OS標準のビューアーで画像を開く。"""
    try:
        if os.name == "nt":  # Windows
            os.startfile(file_path)
        elif os.uname().sysname == "Darwin":  # macOS
            subprocess.run(["open", file_path], check=False)
        else:  # Linux
            subprocess.run(["xdg-open", file_path], check=False)
    except Exception:
        pass


def _run_openai_images(
    provider: str, image_model: str, prompt: str, size: str, n: int
) -> Dict[str, Any]:
    try:
        from openai import AzureOpenAI, OpenAI
    except Exception as e:
        raise RuntimeError("openai パッケージの import に失敗しました: " + repr(e))

    http_client = None
    try:
        import httpx  # type: ignore

        http_client = httpx.Client(verify=_ssl_verify_enabled())
    except Exception as e:
        raise RuntimeError("httpx の初期化に失敗しました: " + repr(e))

    if provider == "azure":
        base_url = (os.environ.get("UAGENT_AZURE_BASE_URL") or "").strip().rstrip("/")
        api_key = (os.environ.get("UAGENT_AZURE_API_KEY") or "").strip()
        api_version = (os.environ.get("UAGENT_AZURE_API_VERSION") or "").strip()
        if not base_url or not api_key or not api_version:
            raise RuntimeError(
                "Azure用の環境変数(UAGENT_AZURE_BASE_URL/UAGENT_AZURE_API_KEY/UAGENT_AZURE_API_VERSION)が不足しています"
            )

        client = AzureOpenAI(
            azure_endpoint=base_url,
            api_key=api_key,
            api_version=api_version,
            http_client=http_client,
        )
    else:
        # OpenAI互換 (openai / nvidia)
        if provider == "nvidia":
            api_key = (os.environ.get("UAGENT_NVIDIA_API_KEY") or "").strip()
            base_url = (
                (
                    os.environ.get(
                        "UAGENT_NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
                    )
                    or ""
                )
                .strip()
                .rstrip("/")
            )
            if not api_key:
                raise RuntimeError(
                    "NVIDIA用の環境変数 UAGENT_NVIDIA_API_KEY が不足しています"
                )
        else:
            api_key = (os.environ.get("UAGENT_OPENAI_API_KEY") or "").strip()
            base_url = (
                (
                    os.environ.get(
                        "UAGENT_OPENAI_BASE_URL", "https://api.openai.com/v1"
                    )
                    or ""
                )
                .strip()
                .rstrip("/")
            )
            if not api_key:
                raise RuntimeError(
                    "OpenAI用の環境変数 UAGENT_OPENAI_API_KEY が不足しています"
                )

        client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)

    resp = client.images.generate(
        model=image_model,
        prompt=prompt,
        size=size,
        n=n,
    )

    b64_list: List[str] = []
    url_list: List[str] = []

    data_list = getattr(resp, "data", None) or []
    for item in data_list:
        b64 = getattr(item, "b64_json", None)
        if b64:
            b64_list.append(b64)
            continue
        url = getattr(item, "url", None)
        if url:
            url_list.append(url)

    if not b64_list and not url_list:
        raise RuntimeError(
            "画像データが空でした（resp.data が空、または b64_json/url が無い）"
        )

    return {"b64_list": b64_list, "url_list": url_list}


def _run_gemini_images(image_model: str, prompt: str) -> List[str]:
    """Gemini 画像生成。

    google-genai SDK はバージョン差分が大きいので、複数の戻り形式をサポートする。
    """
    try:
        from google import genai  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "google-genai の import に失敗しました（pip install google-genai）: "
            + repr(e)
        )

    api_key = (os.environ.get("UAGENT_GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("環境変数 UAGENT_GEMINI_API_KEY が不足しています")

    client = genai.Client(api_key=api_key)

    # try 1: client.models.generate_images (Imagen 3/4 等)
    if hasattr(client, "models") and hasattr(client.models, "generate_images"):
        try:
            resp = client.models.generate_images(model=image_model, prompt=prompt)
            b64_list: List[str] = []
            for gi in getattr(resp, "generated_images", []) or []:
                img = getattr(gi, "image", None)
                if img is None:
                    continue

                # SDK v1.62+ では image_bytes (bytes) に格納される
                raw_bytes = getattr(img, "image_bytes", None)
                if raw_bytes:
                    b64 = base64.b64encode(raw_bytes).decode("utf-8")
                else:
                    # 旧SDK互換
                    b64 = getattr(img, "bytes_base64_encoded", None) or getattr(
                        img, "data", None
                    )

                if b64:
                    b64_list.append(str(b64))
            if b64_list:
                return b64_list
        except Exception:
            pass

    # try 2: client.models.generate_content (Multimodal モデル等)
    if hasattr(client, "models") and hasattr(client.models, "generate_content"):
        resp = client.models.generate_content(model=image_model, contents=prompt)
        b64_list2: List[str] = []
        cands = getattr(resp, "candidates", None) or []
        for cand in cands:
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                inline = getattr(part, "inline_data", None)
                if inline is None:
                    continue
                data = getattr(inline, "data", None)
                if data:
                    b64_list2.append(str(data))
        if b64_list2:
            return b64_list2

    raise RuntimeError(
        "Geminiで画像生成結果を取得できませんでした。モデルが画像生成に対応していないか、SDKの戻り形式が想定外です。"
    )


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        return "[generate_image] prompt が空です"

    size = str(args.get("size") or "1024x1024")
    n = int(args.get("n") or 1)
    n = max(1, min(4, n))

    default_output_dir = os.path.join(
        os.path.expanduser("~"), ".scheck", "outputs", "image_generations"
    )
    output_dir = str(args.get("output_dir") or default_output_dir)
    file_prefix = str(args.get("file_prefix") or "img")

    provider = _get_provider()

    try:
        image_model = _get_image_depname(cb.get_env, provider)
    except Exception:
        return (
            "[generate_image] 画像モデル(デプロイ名)が未設定です。\n"
            "環境変数 UAGENT_IMAGE_DEPNAME を設定してください。"
        )

    try:
        outdir = _ensure_dir(output_dir)
    except Exception as e:
        return f"[generate_image] output_dir 作成に失敗しました: {e}"

    ts = time.strftime("%Y%m%d_%H%M%S")

    try:
        size2 = _sanitize_size_for_provider(size)

        if provider in ("openai", "azure"):
            res = _run_openai_images(
                provider=provider,
                image_model=image_model,
                prompt=prompt,
                size=size2,
                n=n,
            )
            b64_list = res.get("b64_list") or []
            url_list = res.get("url_list") or []

            saved: List[str] = []
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

        elif provider == "gemini":
            b64_list = _run_gemini_images(image_model=image_model, prompt=prompt)
            saved = _save_many(outdir, file_prefix, ts, b64_list)
        else:
            return f"[generate_image] 未対応 provider={provider!r}"

    except Exception as e:
        return (
            "[generate_image] 画像生成に失敗しました。\n"
            f"provider={provider} model={image_model} size={size} n={n}\n" + repr(e)
        )

    if not saved:
        return "[generate_image] 画像データが空でした"

    # 生成後、デフォルトで開く。環境変数 UAGENT_IMAGE_OPEN=0/false 等で無効化可能。
    env_val = (os.environ.get("UAGENT_IMAGE_OPEN") or "").strip().lower()
    should_open = env_val not in ("0", "false", "no", "off")

    if should_open:
        for p in saved:
            _open_image(p)

    if len(saved) == 1:
        return "[OK] generated: " + saved[0]
    return "[OK] generated:\n" + "\n".join(saved)
