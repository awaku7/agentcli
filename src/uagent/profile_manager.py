"""User profiling and smart merge manager for scheck_profile.jsonl."""

from __future__ import annotations

import json
import os
import threading
from typing import Any

from ..env_utils import env_get


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
    """Load the latest profile from scheck_profile.jsonl."""
    profile_file = get_profile_file_path()
    default_profile = {"environment": {}, "preferences": [], "constraints": []}
    if not os.path.exists(profile_file):
        return default_profile

    try:
        with open(profile_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if not lines:
                return default_profile
            # Read the last valid line as the latest profile state
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if isinstance(data, dict):
                        # Ensure basic structure exists
                        for key in ("environment", "preferences", "constraints"):
                            if key not in data:
                                data[key] = [] if key != "environment" else {}
                        return data
                except Exception:
                    continue
    except Exception:
        pass
    return default_profile


def save_profile(profile: dict[str, Any]) -> None:
    """Append the updated profile to scheck_profile.jsonl."""
    profile_file = get_profile_file_path()
    try:
        dirpath = os.path.dirname(profile_file)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(profile_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(profile, ensure_ascii=False) + "\n")
    except Exception:
        pass


def smart_merge_profiles(
    old_profile: dict[str, Any], new_profile: dict[str, Any]
) -> dict[str, Any]:
    """Merge new profile findings into the old profile with smart rules.

    Rules:
    - environment: Overwrite with latest values.
    - preferences: Append and deduplicate.
    - constraints: Append and deduplicate.
    """
    merged = {
        "environment": dict(old_profile.get("environment") or {}),
        "preferences": list(old_profile.get("preferences") or []),
        "constraints": list(old_profile.get("constraints") or []),
    }

    # 1) Environment: Overwrite
    new_env = new_profile.get("environment")
    if isinstance(new_env, dict):
        for k, v in new_env.items():
            if v:
                merged["environment"][k] = v

    # 2) Preferences: Deduplicate and append
    new_prefs = new_profile.get("preferences")
    if isinstance(new_prefs, list):
        for p in new_prefs:
            p_str = str(p).strip()
            if p_str and p_str not in merged["preferences"]:
                merged["preferences"].append(p_str)

    # 3) Constraints: Deduplicate and append
    new_consts = new_profile.get("constraints")
    if isinstance(new_consts, list):
        for c in new_consts:
            c_str = str(c).strip()
            if c_str and c_str not in merged["constraints"]:
                merged["constraints"].append(c_str)

    return merged


def _sanitize_log_for_profiling(messages: list[dict[str, Any]]) -> str:
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

        cleaned_lines.append(f"{role.upper()}: {content}")

    return "\n".join(cleaned_lines)


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
        target=_profile_worker, args=(messages_copy, core), daemon=True
    )
    thread.start()


def _profile_worker(messages: list[dict[str, Any]], core: Any) -> None:
    """Background worker to analyze log, extract profile, and merge."""
    try:
        # 1) Initialize LLM Client
        from .. import util_providers

        provider, client, model_name = util_providers.make_client(core)
        if not client:
            return

        # 2) Sanitize conversation log
        sanitized_log = _sanitize_log_for_profiling(messages)

        # 3) Call LLM to extract profile
        system_prompt = (
            "You are a user profiling agent. Analyze the conversation log and extract the user's:\n"
            "1. Environment (OS, shell, editor, etc.)\n"
            "2. Preferences (coding style, preferred tools, verbosity preference, etc.)\n"
            "3. Constraints (security rules, offline requirements, etc.)\n\n"
            "Do NOT include temporary questions, chit-chat, or sensitive credentials.\n"
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
        merged_profile = smart_merge_profiles(old_profile, new_profile)
        save_profile(merged_profile)

    except Exception:
        # Fail silently in background thread to avoid interrupting the user
        pass
