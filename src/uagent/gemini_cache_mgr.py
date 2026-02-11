import json
import os
import hashlib
from typing import Any, Dict, List, Optional

try:
    from google.genai import types as gemini_types
except ImportError:
    gemini_types = None

# キャッシュメタデータの保存先を決定
# 優先順位:
# 1. 環境変数 UAGENT_CACHE_DIR
# 2. 環境変数 UAGENT_LOG_DIR (設定されている場合)
# 3. デフォルト: ~/.scheck
_env_cache = os.environ.get("UAGENT_CACHE_DIR")
_env_log = os.environ.get("UAGENT_LOG_DIR")

if _env_cache:
    CACHE_META_DIR = _env_cache
elif _env_log:
    # ログディレクトリが指定されている場合は同じ場所を使う
    CACHE_META_DIR = _env_log
else:
    # デフォルトは ~/.scheck/cache
    CACHE_META_DIR = os.path.join(os.path.expanduser("~"), ".scheck", "cache")

CACHE_META_FILE = os.path.join(CACHE_META_DIR, "gemini_cache_meta.json")


def get_file_hash(path: str) -> str:
    """ファイルのSHA256ハッシュを取得"""
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def get_string_hash(text: str) -> str:
    """文字列のハッシュを取得"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_message_sequence(messages: List[Dict[str, Any]]) -> bool:
    """Geminiのターン順序を検証：function_callの直後にtool応答が来ているかチェック"""
    expecting_tool = False
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role == "assistant":
            tool_calls = m.get("tool_calls", [])
            if tool_calls:
                if expecting_tool:
                    return False  # toolを期待しているのにassistant
                expecting_tool = True
        elif role == "tool":
            if not expecting_tool:
                return False  # toolを期待していない
            expecting_tool = False
        # userは順序をリセットしない
    return (
        not expecting_tool
    )  # 最後にtoolを期待していない（未解決のfunction_callがない）


class GeminiCacheManager:
    def __init__(self, model: str):
        self.model = model
        self.meta_data = self._load_meta()

    def _load_meta(self) -> Dict[str, Any]:
        if os.path.exists(CACHE_META_FILE):
            try:
                with open(CACHE_META_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "cache_name": None,
            "model": self.model,
            "system_instruction_hash": None,
            "tools_hash": None,
            "files": {},  # path -> hash
            "discovered_files": [],  # 読み込まれたがまだキャッシュに反映されていないファイル
        }

    def _save_meta(self):
        os.makedirs(CACHE_META_DIR, exist_ok=True)
        with open(CACHE_META_FILE, "w", encoding="utf-8") as f:
            json.dump(self.meta_data, f, ensure_ascii=False, indent=2)

    def record_file_access(self, path: str):
        """ツール等でファイルが読み込まれたことを記録する"""
        if not os.path.exists(path) or os.path.isdir(path):
            return

        # 小さいファイルはキャッシュ更新のコストに見合わないため除外
        # デフォルト 32KB (約32,768バイト) 以上のみキャッシュ対象とする
        min_size = int(os.environ.get("UAGENT_GEMINI_CACHE_MIN_FILE_SIZE", "32768"))
        if os.path.getsize(path) < min_size:
            return

        abs_path = os.path.abspath(path)
        if (
            abs_path not in self.meta_data["files"]
            and abs_path not in self.meta_data["discovered_files"]
        ):
            self.meta_data["discovered_files"].append(abs_path)
            self._save_meta()

    def is_cache_valid(self, system_instruction: str, tools_spec: List[Any]) -> bool:
        """現在のキャッシュが有効（同期されている）か確認"""
        if not self.meta_data["cache_name"]:
            return False

        # モデル一致確認
        if self.meta_data.get("model") != self.model:
            return False

        # システムプロンプト/ツールの変更確認
        if self.meta_data["system_instruction_hash"] != get_string_hash(
            system_instruction
        ):
            return False
        if self.meta_data["tools_hash"] != get_string_hash(
            json.dumps(tools_spec, sort_keys=True)
        ):
            return False

        # ファイルの同期確認（変更があったら無効）
        for path, old_hash in self.meta_data["files"].items():
            if not os.path.exists(path) or get_file_hash(path) != old_hash:
                # print(f"[Gemini Cache] 同期外れを検出: {path}") # ログ抑制
                return False

        # 新しく発見されたファイルがある場合は、作り直したほうが良いので無効とする
        # if self.meta_data["discovered_files"]:
        #     return False

        return True

    def get_cache_name(self) -> Optional[str]:
        return self.meta_data["cache_name"]

    def clear_cache(self, client: Any):
        """メタデータに記録されているキャッシュを削除し、メタデータをリセットする"""
        if self.meta_data.get("cache_name"):
            cache_name = self.meta_data["cache_name"]
            try:
                client.caches.delete(name=cache_name)
                # print(f"[Gemini] Context Cache を削除しました: {cache_name}") # ログ抑制
            except Exception:
                pass
        self.meta_data["cache_name"] = None
        self.meta_data["files"] = {}
        self.meta_data["discovered_files"] = []
        self._save_meta()

    def create_cache(
        self,
        client: Any,
        system_instruction: str,
        func_decls: List[Any],
        initial_messages: List[Dict[str, Any]],
    ) -> str:
        """新しいキャッシュを作成し、メタデータを更新する"""

        # メッセージ順序の検証
        if not _validate_message_sequence(initial_messages):
            raise ValueError(
                "Invalid message sequence: function_call must be followed by tool response immediately."
            )

        # 古いキャッシュがあれば削除試行（任意）
        if self.meta_data["cache_name"]:
            try:
                client.caches.delete(name=self.meta_data["cache_name"])
            except Exception:
                pass

        # キャッシュに含めるコンテンツの構築
        contents = []

        def _append(role: str, part) -> None:
            if contents and getattr(contents[-1], "role", None) == role:
                try:
                    contents[-1].parts.append(part)
                    return
                except Exception:
                    pass
            contents.append(gemini_types.Content(role=role, parts=[part]))

        # 1. 履歴メッセージ
        for m in initial_messages:
            if not isinstance(m, dict):
                continue

            role = m.get("role")
            content = (m.get("content") or "").strip()

            if role == "system":
                continue

            if role == "user":
                if content:
                    _append("user", gemini_types.Part(text=content))
                continue

            if role == "assistant":
                if content:
                    _append("model", gemini_types.Part(text=content))

                tool_calls = m.get("tool_calls") or []
                if isinstance(tool_calls, list):
                    for tc in tool_calls:
                        if not isinstance(tc, dict):
                            continue
                        fnc = tc.get("function") or {}
                        if not isinstance(fnc, dict):
                            continue
                        fc_name = fnc.get("name")
                        if not isinstance(fc_name, str) or not fc_name:
                            continue
                        args_str = fnc.get("arguments") or "{}"
                        try:
                            parsed = (
                                json.loads(args_str)
                                if isinstance(args_str, str)
                                else args_str
                            )
                            args_obj = parsed if isinstance(parsed, dict) else {}
                        except Exception:
                            args_obj = {}

                        try:
                            part_fc = gemini_types.Part(
                                function_call={"name": fc_name, "args": args_obj},
                                thought_signature="skip_thought_signature_validator",
                            )
                        except Exception:
                            part_fc = gemini_types.Part(
                                function_call={"name": fc_name, "args": args_obj}
                            )

                        _append("model", part_fc)
                continue

            if role == "tool":
                tool_name = m.get("name") or "tool"
                if not isinstance(tool_name, str) or not tool_name:
                    tool_name = "tool"

                resp_obj: Dict[str, Any]
                if content:
                    try:
                        parsed = json.loads(content)
                        resp_obj = (
                            parsed if isinstance(parsed, dict) else {"content": content}
                        )
                    except Exception:
                        resp_obj = {"content": content}
                else:
                    resp_obj = {"content": ""}

                try:
                    part = gemini_types.Part.from_function_response(
                        name=tool_name,
                        response=resp_obj,
                    )
                    _append("tool", part)
                except Exception:
                    if content:
                        _append(
                            "tool",
                            gemini_types.Part(text=f"[Tool:{tool_name}] {content}"),
                        )
                continue

            if content:
                _append("user", gemini_types.Part(text=f"{role}:\n{content}"))

        # 2. 蓄積されたファイル群を投入
        new_files_meta = {}
        # 既存＋新規発見
        all_paths = (
            list(self.meta_data["files"].keys()) + self.meta_data["discovered_files"]
        )

        # 重複排除と存在確認
        unique_paths = sorted(list(set(p for p in all_paths if os.path.exists(p))))

        for path in unique_paths:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                    file_hash = get_string_hash(text)
                    contents.append(
                        gemini_types.Content(
                            role="user",
                            parts=[
                                gemini_types.Part(text=f"--- FILE: {path} ---\n{text}")
                            ],
                        )
                    )
                    new_files_meta[path] = file_hash
            except Exception:
                pass  # print(f"[Gemini Cache] ファイル読み込み失敗: {path} {e}") # ログ抑制

        # キャッシュ作成
        cache = client.caches.create(
            model=self.model,
            config=gemini_types.CreateCachedContentConfig(
                system_instruction=system_instruction if system_instruction else None,
                tools=(
                    [gemini_types.Tool(function_declarations=func_decls)]
                    if func_decls
                    else None
                ),
                contents=contents if contents else None,
                ttl="3600s",  # 1時間（ロングランニング）
            ),
        )

        # メタデータ更新
        self.meta_data.update(
            {
                "cache_name": cache.name,
                "system_instruction_hash": get_string_hash(system_instruction),
                "tools_hash": get_string_hash(
                    json.dumps(
                        [fd.__dict__ for fd in func_decls], default=str, sort_keys=True
                    )
                ),
                "files": new_files_meta,
                "discovered_files": [],
            }
        )
        self._save_meta()

        return cache.name
