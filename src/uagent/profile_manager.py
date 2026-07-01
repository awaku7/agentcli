"""User profiling and smart merge manager for scheck_profile.jsonl."""

from __future__ import annotations

import json
import os
import threading
from typing import Any

from .env_utils import env_get
from .i18n import _


def _get_profile_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(env_get(name, str(default))))
    except Exception:
        return default


PROFILE_MAX_ITEMS = _get_profile_int_env("UAGENT_PROFILE_MAX_ITEMS", 20)
PROFILE_MAX_TEXT_CHARS = _get_profile_int_env("UAGENT_PROFILE_MAX_TEXT_CHARS", 160)
PROFILE_SUMMARY_TRIGGER_CHARS = _get_profile_int_env(
    "UAGENT_PROFILE_SUMMARY_TRIGGER_CHARS", 160
)
PROFILE_ENV_KEYS = ("os", "shell", "editor")


# Environment variable to control the profiling feature
# UAGENT_ENABLE_PROFILING=1 (default: 1 / enabled)
def is_profiling_enabled() -> bool:
    return env_get("UAGENT_ENABLE_PROFILING", "1").lower() in ("1", "true", "yes", "on")


def _get_base_log_dir() -> str:
    from uagent.utils.paths import get_log_dir

    return str(get_log_dir())


def get_profile_file_path() -> str:
    base_log_dir = _get_base_log_dir()
    return env_get("UAGENT_PROFILE_FILE") or os.path.join(
        base_log_dir, "scheck_profile.jsonl"
    )


def load_profile() -> dict[str, Any]:
    """Load the latest profile from scheck_profile.jsonl.

    If the file is entirely corrupted (all lines fail to parse), auto-repair
    by overwriting it with the default profile.
    """
    profile_file = get_profile_file_path()
    default_profile = {"environment": {}, "preferences": [], "constraints": []}
    if not os.path.exists(profile_file):
        return default_profile

    try:
        with open(profile_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if not lines:
                return default_profile

            found_valid = False
            # Read the last valid line as the latest profile state
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if isinstance(data, dict):
                        found_valid = True
                        # Ensure basic structure exists
                        for key in ("environment", "preferences", "constraints"):
                            if key not in data:
                                data[key] = [] if key != "environment" else {}
                        return _normalize_profile_snapshot(data)
                except Exception:
                    continue

            # All lines failed to parse -> file is corrupted, overwrite with default
            if not found_valid:
                try:
                    with open(profile_file, "w", encoding="utf-8") as f:
                        f.write(
                            json.dumps(
                                default_profile,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                            + "\n"
                        )
                except Exception:
                    pass
    except Exception:
        pass
    return default_profile


def save_profile(profile: dict[str, Any]) -> None:
    """Write the latest compact profile snapshot to scheck_profile.jsonl."""
    profile_file = get_profile_file_path()
    try:
        dirpath = os.path.dirname(profile_file)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        compact_profile = _normalize_profile_snapshot(profile)
        with open(profile_file, "w", encoding="utf-8") as f:
            f.write(
                json.dumps(compact_profile, ensure_ascii=False, separators=(",", ":"))
                + "\n"
            )
    except Exception:
        pass


def _normalize_for_similarity(text: str) -> str:
    """Normalize text for fuzzy comparison: strip backticks/quotes, collapse spaces, lowercase."""
    import re

    s = re.sub(r"[`'\"「」『』]", "", text)
    s = " ".join(s.split()).lower()
    return s


def _char_bigram_jaccard(a: str, b: str) -> float:
    """Compute character bigram Jaccard similarity between two strings."""

    def _bigrams(s: str) -> set[str]:
        return {s[i : i + 2] for i in range(len(s) - 1)}

    big_a = _bigrams(a)
    big_b = _bigrams(b)
    if not big_a or not big_b:
        return 0.0
    intersection = len(big_a & big_b)
    union = len(big_a | big_b)
    return intersection / union if union > 0 else 0.0


def _longest_common_substring_ratio(a: str, b: str) -> float:
    """Compute the ratio of longest common substring length to the shorter string length."""
    if not a or not b:
        return 0.0
    shorter_len = min(len(a), len(b))
    if shorter_len < 4:
        return 0.0

    # Dynamic programming for LCS (substring, not subsequence)
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    longest = 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
                if dp[i][j] > longest:
                    longest = dp[i][j]
            else:
                dp[i][j] = 0
    return longest / shorter_len


def _is_similar_phrase(a: str, b: str) -> bool:
    """Check if two phrases are semantically or textually very similar to avoid redundancy.

    Uses multiple strategies:
    1. Exact match (case-insensitive)
    2. Normalized match (strip backticks/quotes, collapse spaces)
    3. Containment check for medium+ strings
    4. Character bigram Jaccard similarity (threshold: 0.55)
    5. Longest common substring ratio (threshold: 0.5)
    6. Concept-domain matching via keyword pairs
    """
    a_lower = a.lower()
    b_lower = b.lower()
    if a_lower == b_lower:
        return True

    # Normalize: strip backticks, quotes, normalize whitespace
    na = _normalize_for_similarity(a)
    nb = _normalize_for_similarity(b)
    if na == nb:
        return True

    # Containment check: if the shorter string (>= 8 chars) is contained in the longer one
    if len(na) >= 8 and len(nb) >= 8:
        if na in nb or nb in na:
            return True

    # Character bigram Jaccard similarity (threshold: 0.55)
    if len(na) >= 5 and len(nb) >= 5:
        similarity = _char_bigram_jaccard(na, nb)
        if similarity >= 0.55:
            return True

    # Longest common substring ratio (threshold: 0.5)
    if len(na) >= 8 and len(nb) >= 8:
        lcs_ratio = _longest_common_substring_ratio(na, nb)
        if lcs_ratio >= 0.5:
            return True

    # Concept-domain matching: detect shared semantic domain via keyword pairs
    # Each domain is defined by a set of keywords; if both strings match the same
    # domain with sufficient coverage, treat as similar.
    domain_sets = [
        # Dangerous operation confirmation
        {"危険", "確認", "事前", "前に確認"},
        # Secret/password management (negative form)
        {"秘密情報", "しない", "保存しない", "記憶しない", "記録しない"},
        # Offline/local environment
        {"ローカル", "オフライン", "オフライン/ローカル", "ローカル/オフライン"},
        # I18N / internationalization
        {"I18N", "国際化"},
        # Conciseness preference
        {"簡潔"},
        # Markdown-first workflow
        {"Markdown", "要件"},
        # Dynamic commands
        {":skills", "コマンド", "動的"},
    ]

    for domain_kws in domain_sets:
        hits_a = sum(1 for kw in domain_kws if kw in na)
        hits_b = sum(1 for kw in domain_kws if kw in nb)
        # Both strings must hit at least one keyword in the domain
        if hits_a >= 1 and hits_b >= 1:
            # Require a minimum of 2 total hits across both strings
            if hits_a + hits_b >= 2:
                return True

    return False


def _compact_profile_text(value: Any) -> str:
    return " ".join(str(value).split()).strip()


def _summarize_profile_text(
    text: str,
    *,
    provider: str | None = None,
    client: Any = None,
    model_name: str = "",
    kind: str = "item",
) -> str:
    compact = _compact_profile_text(text)
    if not compact:
        return ""
    if len(compact) <= PROFILE_SUMMARY_TRIGGER_CHARS:
        return compact[:PROFILE_MAX_TEXT_CHARS]
    if not provider or client is None or not model_name:
        return compact[:PROFILE_MAX_TEXT_CHARS]

    prompt = (
        f"Shorten the following user {kind} into a concise phrase. "
        f"Keep the meaning, remove examples and filler, and return only the summary. "
        f"Limit it to {PROFILE_MAX_TEXT_CHARS} characters.\n\n"
        f"TEXT: {compact}"
    )

    try:
        if provider in ("gemini", "vertexai"):
            from google.genai import types as gemini_types

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=gemini_types.GenerateContentConfig(
                    system_instruction="Return only the summary text.",
                    temperature=0.0,
                ),
            )
            raw = response.text or ""
        elif provider == "claude":
            response = client.messages.create(
                model=model_name,
                max_tokens=128,
                system="Return only the summary text.",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            raw = response.content[0].text or ""
        else:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "Return only the summary text."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=128,
            )
            raw = response.choices[0].message.content or ""
    except Exception:
        return compact[:PROFILE_MAX_TEXT_CHARS]

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    cleaned = _compact_profile_text(cleaned)
    return (cleaned or compact)[:PROFILE_MAX_TEXT_CHARS]


def _normalize_profile_snapshot(
    profile: dict[str, Any],
    *,
    provider: str | None = None,
    client: Any = None,
    model_name: str = "",
) -> dict[str, Any]:
    normalized = {"environment": {}, "preferences": [], "constraints": []}

    env_data = profile.get("environment")
    if isinstance(env_data, dict):
        env_clean: dict[str, Any] = {}
        for key in PROFILE_ENV_KEYS:
            value = env_data.get(key)
            if value is None:
                continue
            text = _compact_profile_text(value)
            if text:
                env_clean[str(key)] = text[:PROFILE_MAX_TEXT_CHARS]
        normalized["environment"] = env_clean

    for field in ("preferences", "constraints"):
        raw_items = profile.get(field)
        if not isinstance(raw_items, list):
            continue

        items: list[str] = []
        for item in raw_items:
            text = _compact_profile_text(item)
            if not text:
                continue
            text = _summarize_profile_text(
                text,
                provider=provider,
                client=client,
                model_name=model_name,
                kind=field[:-1],
            )
            if not text:
                continue
            if not any(_is_similar_phrase(text, existing) for existing in items):
                items.append(text[:PROFILE_MAX_TEXT_CHARS])

        normalized[field] = items[-PROFILE_MAX_ITEMS:]

    return normalized


def _deduplicate_profile_with_llm(
    profile: dict[str, Any],
    *,
    provider: str | None = None,
    client: Any = None,
    model_name: str = "",
) -> dict[str, Any]:
    """Use LLM to deduplicate and clean up preferences and constraints lists."""
    if not provider or client is None or not model_name:
        return profile

    preferences = profile.get("preferences") or []
    constraints = profile.get("constraints") or []
    if not preferences and not constraints:
        return profile

    prompt = (
        "You are a user profiling assistant. Clean up and deduplicate the following user profile lists.\n"
        "Merge highly similar, redundant, or overlapping items into single concise phrases.\n"
        "Keep the meaning, remove examples and filler, and return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "preferences": ["string"],\n'
        '  "constraints": ["string"]\n'
        "}\n\n"
        f"CURRENT PROFILE:\n"
        f"Preferences:\n{json.dumps(preferences, ensure_ascii=False, indent=2)}\n\n"
        f"Constraints:\n{json.dumps(constraints, ensure_ascii=False, indent=2)}"
    )

    try:
        if provider in ("gemini", "vertexai"):
            from google.genai import types as gemini_types

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=gemini_types.GenerateContentConfig(
                    system_instruction="Return only the cleaned JSON object.",
                    temperature=0.0,
                ),
            )
            raw = response.text or ""
        elif provider == "claude":
            response = client.messages.create(
                model=model_name,
                max_tokens=1000,
                system="Return only the cleaned JSON object.",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            raw = response.content[0].text or ""
        else:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "Return only the cleaned JSON object.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=1000,
            )
            raw = response.choices[0].message.content or ""

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        data = json.loads(cleaned)
        if isinstance(data, dict):
            new_profile = dict(profile)
            if "preferences" in data and isinstance(data["preferences"], list):
                new_profile["preferences"] = [
                    _compact_profile_text(x)[:PROFILE_MAX_TEXT_CHARS]
                    for x in data["preferences"]
                    if _compact_profile_text(x)
                ]
            if "constraints" in data and isinstance(data["constraints"], list):
                new_profile["constraints"] = [
                    _compact_profile_text(x)[:PROFILE_MAX_TEXT_CHARS]
                    for x in data["constraints"]
                    if _compact_profile_text(x)
                ]
            return new_profile
    except Exception:
        pass

    return profile


def smart_merge_profiles(
    old_profile: dict[str, Any],
    new_profile: dict[str, Any],
    *,
    provider: str | None = None,
    client: Any = None,
    model_name: str = "",
    skip_llm_dedup: bool = False,
) -> dict[str, Any]:
    """Merge new profile findings into the old profile with size limits."""
    old_profile = _normalize_profile_snapshot(old_profile)
    new_profile = _normalize_profile_snapshot(
        new_profile, provider=provider, client=client, model_name=model_name
    )

    merged = {
        "environment": dict(old_profile.get("environment") or {}),
        "preferences": list(old_profile.get("preferences") or []),
        "constraints": list(old_profile.get("constraints") or []),
    }

    new_env = new_profile.get("environment")
    if isinstance(new_env, dict):
        for k in PROFILE_ENV_KEYS:
            v = new_env.get(k)
            text = _compact_profile_text(v)
            if text:
                merged["environment"][str(k)] = text[:PROFILE_MAX_TEXT_CHARS]

    def _append_limited(dst: list[str], items: Any) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            text = _compact_profile_text(item)
            if not text:
                continue
            text = _summarize_profile_text(
                text,
                provider=provider,
                client=client,
                model_name=model_name,
                kind="item",
            )
            if not text:
                continue
            if not any(_is_similar_phrase(text, existing) for existing in dst):
                dst.append(text[:PROFILE_MAX_TEXT_CHARS])
                if len(dst) >= PROFILE_MAX_ITEMS:
                    break

    _append_limited(merged["preferences"], new_profile.get("preferences"))
    _append_limited(merged["constraints"], new_profile.get("constraints"))

    merged["preferences"] = merged["preferences"][-PROFILE_MAX_ITEMS:]
    merged["constraints"] = merged["constraints"][-PROFILE_MAX_ITEMS:]

    # LLMによる重複排除と整理（skip_llm_dedup=True の場合はスキップ）
    if not skip_llm_dedup:
        merged = _deduplicate_profile_with_llm(
            merged,
            provider=provider,
            client=client,
            model_name=model_name,
        )

    return merged


def _sanitize_log_for_profiling(
    messages: list[dict[str, Any]],
    max_content_chars: int = 5000,
) -> str:
    """Clean up conversation log to remove potential secrets before sending to LLM."""
    import re

    cleaned_lines = []

    # Simple regex to mask potential API keys or passwords in logs
    secret_re = re.compile(
        r"(password|passwd|secret|private_key|token|api_key)\s*[:=]\s*['\" \t]*([a-zA-Z0-9_\-]{8,})['\" \t]*",
        re.IGNORECASE,
    )
    key_re = re.compile(
        r"(AIzaSy[a-zA-Z0-9_\-]{33}|sk-[a-zA-Z0-9]{48}|ghp_[a-zA-Z0-9]{36})"
    )

    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)

        # Mask secrets
        content = secret_re.sub(r"\1=********", content)
        content = key_re.sub("********", content)

        # Trim oversized messages (e.g. image data)
        if max_content_chars > 0 and len(content) > max_content_chars:
            content = content[:max_content_chars] + " ... [TRUNCATED]"

        cleaned_lines.append(f"{role.upper()}: {content}")

    return "\n".join(cleaned_lines)


def _update_profile_in_messages(
    profile: dict[str, Any], live_messages: list[dict[str, Any]]
) -> None:
    """Find and replace the [USER PROFILE] system message in a live messages list."""
    try:
        from .runtime.runtime_memory import _format_profile

        new_content = _format_profile(profile)
        for i, msg in enumerate(live_messages):
            if (
                isinstance(msg, dict)
                and msg.get("role") == "system"
                and isinstance(msg.get("content"), str)
                and msg["content"].startswith("[USER PROFILE]")
            ):
                live_messages[i] = {"role": "system", "content": new_content}
                return
    except Exception:
        pass


def run_profiling_async(messages: list[dict[str, Any]], core: Any) -> None:
    """Run the profiling process in a background thread to avoid blocking the user."""
    if not is_profiling_enabled():
        return

    if not messages:
        return

    # Deep copy messages to avoid thread-safety issues with the main loop
    try:
        messages_copy = json.loads(json.dumps(messages))
    except Exception:
        return

    thread = threading.Thread(
        target=_profile_worker, args=(messages_copy, core, messages), daemon=True
    )
    thread.start()


def _profile_worker(
    messages: list[dict[str, Any]],
    core: Any,
    live_messages: list[dict[str, Any]] | None = None,
) -> None:
    """Background worker to analyze log, extract profile, and merge."""
    try:
        # 1) Initialize LLM Client
        from .providers import util_providers

        provider, client, model_name = util_providers.make_client(core)
        if not client:
            return

        # 2) Sanitize conversation log
        sanitized_log = _sanitize_log_for_profiling(messages)

        # 3) Call LLM to extract profile
        system_prompt = _(
            "You are a user profiling agent. Analyze the conversation log and extract the user's:\n"
            "1. Environment (OS, shell, editor, etc.)\n"
            "2. Preferences (coding style, preferred tools, verbosity preference, etc.)\n"
            "3. Constraints (security rules, offline requirements, etc.)\n\n"
            "Do NOT include temporary questions, chit-chat, or sensitive credentials.\n"
            "Do NOT extract temporary technical limitations, tool availability issues, or one-time constraints.\n"
            "Only extract rules the user explicitly stated and that apply long-term.\n"
            "Record preferences and constraints in the same language as the conversation (matching the user locale).\n"
            "You MUST respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "environment": {"os": "string", "shell": "string", "editor": "string"},\n'
            '  "preferences": ["string"],\n'
            '  "constraints": ["string"]\n'
            "}"
        )

        user_prompt = f"CONVERSATION LOG:\n{sanitized_log}"

        # Call LLM based on provider
        raw_response = ""
        if provider in ("gemini", "vertexai"):
            from google.genai import types as gemini_types

            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=gemini_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.0,  # Deterministic
                ),
            )
            raw_response = response.text or ""
        elif provider == "claude":
            response = client.messages.create(
                model=model_name,
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.0,
            )
            raw_response = response.content[0].text or ""
        else:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
            )
            raw_response = response.choices[0].message.content or ""

        # Cleanup JSON markdown blocks if any
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        # Parse extracted profile
        new_profile = json.loads(cleaned)
        if not isinstance(new_profile, dict):
            return

        # 4) Smart Merge and Save
        old_profile = load_profile()
        merged_profile = smart_merge_profiles(
            old_profile,
            new_profile,
            provider=provider,
            client=client,
            model_name=model_name,
        )
        save_profile(merged_profile)

        # 5) Update in-memory messages with the new profile
        if live_messages is not None:
            _update_profile_in_messages(merged_profile, live_messages)

    except Exception:
        # Fail silently in background thread to avoid interrupting the user
        pass


def profile_from_logs(
    core: Any,
    max_log_files: int | None = None,
) -> dict[str, Any] | None:
    """Synchronously analyze past logs, extract profile, merge, and save."""
    # 1) Gather messages from past logs
    from uagent.utils.paths import get_log_dir

    log_dir = get_log_dir()
    if not os.path.exists(log_dir):
        return None

    log_files = sorted(
        [
            f
            for f in os.listdir(log_dir)
            if f.startswith("scheck_log_") and f.endswith(".jsonl")
        ]
    )
    if not log_files:
        return None

    # Limit to most recent N files if max_log_files is set
    if max_log_files is not None and max_log_files > 0:
        log_files = log_files[-max_log_files:]

    # 2) Initialize LLM Client
    from .providers import util_providers

    provider, client, model_name = util_providers.make_client(core)
    if not client:
        raise RuntimeError(_("Failed to initialize LLM client."))

    # 3) Process logs in chunks chronologically (oldest to newest)
    total_files = len(log_files)
    print(
        _("Found %(total_files)d log files. Starting incremental profiling...")
        % {"total_files": total_files}
    )

    current_profile = {"environment": {}, "preferences": [], "constraints": []}
    message_buffer = []
    chunk_size_limit = 500  # Process up to 500 messages per LLM call

    system_prompt = _(
        "You are a user profiling agent. Analyze the conversation log and extract:\n"
        "1. Environment (OS, shell, editor) — only if clearly evident from the log.\n"
        "2. Preferences — specific, actionable traits observed from the user's actual requests and corrections:\n"
        "   - Response style: concise or verbose? Code-heavy or prose-heavy? Bullet points or paragraphs?\n"
        "   - Language: prefers Japanese, English, or mixed?\n"
        "   - Tool usage: which tools/commands does the user frequently reach for?\n"
        "   - Quality standard: tolerates quick workarounds or insists on proper solutions?\n"
        "   - Confirmation: wants explicit approval before file operations, or prefers to skip prompts?\n"
        "   - Any other recurring pattern in how the user gives instructions.\n"
        "3. Constraints — explicit rules the user stated (e.g. 'must be offline', 'no external APIs', 'keep it simple', 'no extra dependencies').\n\n"
        "Do NOT infer preferences from a single request; only extract patterns that appear repeatedly.\n"
        "Do NOT include temporary questions, chit-chat, or sensitive credentials.\n"
        "Do NOT extract temporary technical limitations, tool availability issues, or one-time constraints.\n"
        "Only extract rules the user explicitly stated and that apply long-term.\n"
        "Record preferences and constraints in the same language as the conversation (matching the user locale).\n"
        "You MUST respond ONLY with a valid JSON object matching this schema:\n"
        "{\n"
        '  "environment": {"os": "string", "shell": "string", "editor": "string"},\n'
        '  "preferences": ["string"],\n'
        '  "constraints": ["string"]\n'
        "}"
    )

    def process_chunk(
        messages_chunk: list[dict[str, Any]], step_info: str
    ) -> dict[str, Any] | None:
        if not messages_chunk:
            return None
        sanitized_log = _sanitize_log_for_profiling(messages_chunk)
        user_prompt = f"CONVERSATION LOG:\n{sanitized_log}"

        raw_response = ""
        try:
            if provider in ("gemini", "vertexai"):
                from google.genai import types as gemini_types

                response = client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=gemini_types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.0,
                    ),
                )
                raw_response = response.text or ""
            elif provider == "claude":
                response = client.messages.create(
                    model=model_name,
                    max_tokens=2000,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=0.0,
                )
                raw_response = response.content[0].text or ""
            else:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,
                )
                raw_response = response.choices[0].message.content or ""

            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()

            new_prof = json.loads(cleaned)
            if isinstance(new_prof, dict):
                return new_prof
        except Exception as e:
            print("  " + _("[Warning] Failed to process chunk (%(step)s): %(err)s") % {"step": step_info, "err": e})
        return None

    # Iterate through all files in chronological order
    for idx, lf in enumerate(log_files):
        p = os.path.join(log_dir, lf)
        file_messages = []
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if "role" in data and "content" in data:
                            file_messages.append(data)
                    except Exception:
                        pass
        except Exception:
            continue

        message_buffer.extend(file_messages)

        # If buffer exceeds limit, or we are at the last file, process the chunk
        if len(message_buffer) >= chunk_size_limit or idx == total_files - 1:
            progress = int((idx + 1) / total_files * 100)
            step_info = f"File {idx+1}/{total_files} ({progress}%)"
            print(
                f"Processing chunk up to {step_info} (messages: {len(message_buffer)})..."
            )

            extracted_prof = process_chunk(message_buffer, step_info)
            if extracted_prof:
                current_profile = smart_merge_profiles(
                    current_profile,
                    extracted_prof,
                    provider=provider,
                    client=client,
                    model_name=model_name,
                    skip_llm_dedup=True,
                )

            # Clear buffer
            message_buffer = []

    # Final LLM dedup: run once on the complete merged profile
    if provider and client is not None and model_name:
        current_profile = _deduplicate_profile_with_llm(
            current_profile,
            provider=provider,
            client=client,
            model_name=model_name,
        )

    # Save the final merged profile
    save_profile(current_profile)
    return current_profile
