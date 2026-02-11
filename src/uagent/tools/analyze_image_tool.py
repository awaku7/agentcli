# tools/analyze_image_tool.py
import base64
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

# OpenAI / Azure OpenAI
try:
    from openai import AzureOpenAI, OpenAI
except Exception:
    AzureOpenAI = None  # type: ignore[assignment]
    OpenAI = None  # type: ignore[assignment]

from .context import get_callbacks

BUSY_LABEL = True
STATUS_LABEL = "tool:analyze_image"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "analyze_image",
        "description": "画像ファイルを読み込み、その内容をAI（Vision）に説明させます。スクリーンショットの解析や図表の読み取りに使用します。",
        "system_prompt": """このツールは次の目的で使われます: 画像ファイルを読み込み、その内容をAIに説明させます。スクリーンショットの解析や図表の読み取りに使用します。""",
        "parameters": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "解析する画像ファイルのパス。",
                },
                "prompt": {
                    "type": "string",
                    "description": "画像について何を知りたいか（例: 'この画像のエラーメッセージを読み取って', 'UIの配置を説明して'）。省略時は 'この画像を詳細に説明してください' になります。",
                },
            },
            "required": ["image_path"],
        },
    },
}

# Responses API モード（UAGENT_RESPONSES=1/true）では、LLM 本体へのマルチモーダル入力を優先するため、
# analyze_image ツールをロード対象から除外する。
# tools/__init__.py のローダは TOOL_SPEC が dict でない場合に登録しない。
if (os.environ.get("UAGENT_RESPONSES", "") or "").strip().lower() in ("1", "true"):
    TOOL_SPEC = None  # type: ignore[assignment]


def _detect_provider() -> str:
    """UAGENT_PROVIDER から利用プロバイダを判定する。

    - gemini / openai / azure を許可
    - 未指定/未知は gemini にフォールバック（従来挙動を優先）
    """

    p = (os.environ.get("UAGENT_PROVIDER") or "gemini").strip().lower()
    if p not in ("gemini", "openai", "azure", "nvidia"):
        p = "openai"
    return p


def _data_url_from_image_bytes(image_bytes: bytes, mime_type: str) -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{b64}"


def _guess_mime_type(path: Path) -> str:
    mt, _ = mimetypes.guess_type(str(path))
    if mt:
        return mt
    # fallback
    ext = path.suffix.lower().lstrip(".")
    if ext == "jpg":
        return "image/jpeg"
    if ext:
        return f"image/{ext}"
    return "image/png"


def _run_gemini(image_bytes: bytes, mime_type: str, prompt: str) -> str:
    if genai is None or types is None:
        return "[analyze_image error] google-genai がインストールされていません。"

    cb = get_callbacks()
    if cb.get_env is None:
        return "[analyze_image error] get_env コールバックが初期化されていません。"

    try:
        api_key = cb.get_env("UAGENT_GEMINI_API_KEY")
    except SystemExit:
        return "[analyze_image error] 環境変数 UAGENT_GEMINI_API_KEY が設定されていません。"
    except Exception as e:
        return (
            f"[analyze_image error] APIキー取得に失敗しました: {type(e).__name__}: {e}"
        )

    model_name = os.environ.get("UAGENT_GEMINI_VISION_MODEL", "gemini-3.0-flash")
    import sys

    print(f"[analyze_image] provider='gemini', model='{model_name}'", file=sys.stderr)

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        types.Part(text=str(prompt)),
                    ],
                )
            ],
        )

        if response.text:
            return f"[analyze_image] 以下の応答が得られました:\n{response.text}"
        return "[analyze_image] 解析は完了しましたが、テキスト応答が空でした。"

    except Exception as e:
        return f"[analyze_image error] Gemini API 呼び出し中にエラーが発生しました: {e}"


def _run_azure_openai(image_bytes: bytes, mime_type: str, prompt: str) -> str:
    if AzureOpenAI is None:
        return "[analyze_image error] openai パッケージがインストールされていません（AzureOpenAI が利用不可）。"

    cb = get_callbacks()
    if cb.get_env is None or cb.get_env_url is None:
        return "[analyze_image error] コールバックが初期化されていません。"

    try:
        # 画像解析専用のエンドポイント指定があれば優先
        base_url = cb.get_env_url("UAGENT_AZURE_BASE_URL")

        api_key = cb.get_env("UAGENT_AZURE_API_KEY")
        api_version = cb.get_env("UAGENT_AZURE_API_VERSION")
    except SystemExit as e:
        return f"[analyze_image error] 必要な環境変数が設定されていません: {e}"
    except Exception as e:
        return (
            f"[analyze_image error] 環境変数取得に失敗しました: {type(e).__name__}: {e}"
        )

    # 画像解析専用のモデル(デプロイ名)指定があれば優先
    model = os.environ.get("UAGENT_AZURE_IM_DEPNAME")
    if not model:
        model = os.environ.get("UAGENT_DEPNAME", "gpt-5.2")

    data_url = _data_url_from_image_bytes(image_bytes, mime_type)

    import sys

    print(
        f"[analyze_image] provider='azure', model(deployment)='{model}', base_url='{base_url}', version='{api_version}'",
        file=sys.stderr,
    )

    try:
        client = AzureOpenAI(
            azure_endpoint=base_url,
            api_key=api_key,
            api_version=api_version,
        )

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )

        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return "[analyze_image] 解析は完了しましたが、テキスト応答が空でした。"
        return f"[analyze_image] 以下の応答が得られました:\n{text}"

    except Exception as e:
        return f"[analyze_image error] Azure OpenAI 呼び出し中にエラーが発生しました: {type(e).__name__}: {e}"


def _run_openai_compatible(image_bytes: bytes, mime_type: str, prompt: str) -> str:
    if OpenAI is None:
        return "[analyze_image error] openai パッケージがインストールされていません（OpenAI クライアントが利用不可）。"

    cb = get_callbacks()
    if cb.get_env is None or cb.get_env_url is None:
        return "[analyze_image error] コールバックが初期化されていません。"

    provider = (os.environ.get("UAGENT_PROVIDER") or "openai").strip().lower()

    try:
        if provider == "nvidia":
            api_key = cb.get_env("UAGENT_NVIDIA_API_KEY")
            base_url = cb.get_env_url(
                "UAGENT_NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
            )
        else:
            api_key = cb.get_env("UAGENT_OPENAI_API_KEY")
            base_url = cb.get_env_url(
                "UAGENT_OPENAI_BASE_URL", "https://api.openai.com/v1"
            )
    except SystemExit:
        missing = (
            "UAGENT_NVIDIA_API_KEY" if provider == "nvidia" else "UAGENT_OPENAI_API_KEY"
        )
        return f"[analyze_image error] 環境変数 {missing} が設定されていません。"
    except Exception as e:
        return (
            f"[analyze_image error] APIキー取得に失敗しました: {type(e).__name__}: {e}"
        )

    # 画像解析専用のモデル指定があれば優先
    if provider == "nvidia":
        model = os.environ.get("UAGENT_NVIDIA_IM_DEPNAME")
        if not model:
            model = os.environ.get(
                "UAGENT_NVIDIA_DEPNAME", "nvidia/nemotron-3-nano-30b-a3b"
            )
    else:
        model = os.environ.get("UAGENT_OPENAI_IM_DEPNAME")
        if not model:
            model = os.environ.get("UAGENT_OPENAI_DEPNAME", "gpt-5.2")

    data_url = _data_url_from_image_bytes(image_bytes, mime_type)

    import sys

    print(
        f"[analyze_image] provider='{provider}', model='{model}', base_url='{base_url}'",
        file=sys.stderr,
    )

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return "[analyze_image] 解析は完了しましたが、テキスト応答が空でした。"
        return f"[analyze_image] 以下の応答が得られました:\n{text}"

    except Exception as e:
        return f"[analyze_image error] OpenAI互換 呼び出し中にエラーが発生しました: {type(e).__name__}: {e}"


def run_tool(args: Dict[str, Any]) -> str:
    """画像解析を実行する"""

    image_path = str(args.get("image_path", "")).strip()
    prompt = (
        args.get("prompt", "") or "この画像に何が写っているか詳細に説明してください。"
    )

    if not image_path:
        return "[analyze_image error] image_path が空です。"

    p = Path(image_path)
    if not p.exists():
        return f"[analyze_image error] ファイルが見つかりません: {image_path}"

    # 画像読み込み
    try:
        image_bytes = p.read_bytes()
    except Exception as e:
        return f"[analyze_image error] 画像ファイルの読み込みに失敗しました: {e}"

    mime_type = _guess_mime_type(p)

    provider = _detect_provider()

    # NOTE: 既存の挙動を守るため、デフォルトは gemini
    if provider == "gemini":
        return _run_gemini(image_bytes, mime_type, prompt)

    if provider == "azure":
        return _run_azure_openai(image_bytes, mime_type, prompt)

    if provider == "openai":
        return _run_openai_compatible(image_bytes, mime_type, prompt)

    # fallback
    return _run_gemini(image_bytes, mime_type, prompt)
