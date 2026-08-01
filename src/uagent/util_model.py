"""Model / env capability display (moved from util_tools.py)."""

from __future__ import annotations

import os
import shlex
from typing import Any

from .env_utils import env_get
from .i18n import _
from .util_common import CommandResult
from .uagent_env_keys import _is_placeholder_uagent_key, get_known_uagent_env_keys

# Default translation function used when core.tr is not provided.
tr = _
tr_ = _


def _uagent_env_names(prefix: str = "UAGENT_") -> list[str]:
    keys = set(get_known_uagent_env_keys(prefix))
    keys.update(
        k
        for k in os.environ
        if k.startswith(prefix) and not _is_placeholder_uagent_key(k)
    )
    return sorted(keys, key=str.lower)


def _uagent_format_env_value(name: str, value: str) -> str:
    _upper = name.upper()
    if any(kw in _upper for kw in ("KEY", "TOKEN", "PASSWORD", "SECRET", "CREDENTIAL")):
        return "***"
    return value


def _handle_cmd_env(arg: str, *, tr: Any) -> bool:
    raw = (arg or "").strip()
    if not raw:
        for key in _uagent_env_names():
            print(f"{key}={_uagent_format_env_value(key, os.environ.get(key, ''))}")
        return True

    try:
        items = shlex.split(raw, posix=False)
    except Exception as e:
        print(
            _("[env error] %(etype)s: %(err)s") % {"etype": type(e).__name__, "err": e}
        )
        return True

    if not items:
        for key in _uagent_env_names():
            print(f"{key}={_uagent_format_env_value(key, os.environ.get(key, ''))}")
        return True

    sub = items[0].lower()
    if sub in ("show", "list"):
        if len(items) == 1:
            for key in _uagent_env_names():
                print(f"{key}={_uagent_format_env_value(key, os.environ.get(key, ''))}")
            return True

        query = items[1]
        keys = [k for k in _uagent_env_names() if k.lower() == query.lower()]
        if not keys:
            keys = [
                k for k in _uagent_env_names() if k.lower().startswith(query.lower())
            ]
        if not keys:
            print(_("[env] Not found: %(key)s") % {"key": query})
            return True
        if len(keys) > 1:
            print(_("[env] Ambiguous: %(key)s") % {"key": query})
            for key in keys:
                print(f"{key}={_uagent_format_env_value(key, os.environ.get(key, ''))}")
            return True
        key = keys[0]
        print(f"{key}={_uagent_format_env_value(key, os.environ.get(key, ''))}")
        return True

    if sub == "set":
        if len(items) < 3:
            print(_(":env set KEY VALUE"))
            return True
        key = items[1]
        value = " ".join(items[2:])
        os.environ[key] = value
        print(_("[env] Set %(key)s") % {"key": key})
        return True

    if sub == "unset":
        if len(items) < 2:
            print(_(":env unset KEY"))
            return True
        key = items[1]
        os.environ.pop(key, None)
        print(_("[env] Unset %(key)s") % {"key": key})
        return True

    if sub == "save":
        try:
            from .runtime.runtime_env import save_uagent_envsec

            sec_path = save_uagent_envsec()
            print(_("[env] Saved .env.sec: %(path)s") % {"path": str(sec_path)})
        except Exception as e:
            print(
                _("[env error] %(etype)s: %(err)s")
                % {"etype": type(e).__name__, "err": e}
            )
        return True

    print(_(":env show [KEY] / :env set KEY VALUE / :env unset KEY / :env save"))
    return True


def _get_env(key: str, default: str = "") -> str:
    v = env_get(key)
    if v is None:
        return default
    return v.strip()


def _format_capa(cap) -> list[str]:
    """Format a llmcapa Capability object into detail lines."""
    lines: list[str] = []
    lines.append(_("    Display Name:  %(value)s") % {"value": cap.display_name})
    lines.append(
        _("    Context Window: %(value)s tokens") % {"value": f"{cap.context_window:,}"}
    )
    lines.append(
        _("    Max Output:    %(value)s tokens")
        % {"value": f"{cap.max_output_tokens:,}"}
    )
    lines.append(
        _("    Tokenizer:     %(value)s") % {"value": cap.tokenizer_name or "?"}
    )
    lines.append(_("    License:       %(value)s") % {"value": cap.license_type or "?"})
    lines.append(
        _("    Knowledge Cutoff: %(value)s") % {"value": cap.knowledge_cutoff or "?"}
    )
    lines.append(_("    Deprecated:    %(value)s") % {"value": cap.deprecated})
    if cap.input_modalities:
        lines.append(
            _("    Input:         %(value)s")
            % {"value": ", ".join(cap.input_modalities)}
        )
    if cap.output_modalities:
        lines.append(
            _("    Output:        %(value)s")
            % {"value": ", ".join(cap.output_modalities)}
        )
    feats = []
    if cap.supports_function_calling:
        feats.append("function_calling")
    if cap.supports_json_mode:
        feats.append("json_mode")
    if cap.supports_streaming:
        feats.append("streaming")
    if cap.supports_vision:
        feats.append("vision")
    if cap.supports_reasoning:
        feats.append("reasoning")
    if cap.supports_chat_completion:
        feats.append("chat_completion")
    if cap.supports_responses_api:
        feats.append("responses_api")
    if cap.supports_reasoning_effort:
        feats.append("reasoning_effort")
    if cap.supports_thinking_budget:
        feats.append("thinking_budget")
    if cap.supports_anthropic_api:
        feats.append("anthropic_api")
    if cap.supports_google_api:
        feats.append("google_api")
    if cap.supports_fim:
        feats.append("fim")
    if feats:
        lines.append(_("    Features:      %(value)s") % {"value": ", ".join(feats)})
    if cap.pricing:
        price = cap.pricing
        inp = price.get("input_per_1m")
        out = price.get("output_per_1m")
        cur = price.get("currency", "USD")
        if inp is not None and out is not None:
            lines.append(
                _(
                    "    Pricing:       $%(inp).2f/%(cur)sM in, "
                    "$%(outp).2f/%(cur)sM out"
                )
                % {"inp": float(inp), "outp": float(out), "cur": cur}
            )
    if cap.reasoning_effort_values:
        lines.append(
            _("    Reasoning Efforts: %(value)s")
            % {"value": ", ".join(cap.reasoning_effort_values)}
        )
    if cap.thinking_budget_values:
        lines.append(
            _("    Thinking Budgets: %(value)s")
            % {"value": ", ".join(str(v) for v in cap.thinking_budget_values)}
        )
    return lines


def _fetch_model_capa(provider: str, model: str) -> list[str]:
    """Fetch llmcapa info for a model. Returns detail lines, or empty if unavailable."""
    try:
        from .llmcapa_util import format_capability_lines, get_capability

        prov = provider if provider not in ("(none)", "") else None
        cap = get_capability(model, prov)
        if cap:
            # Prefer shared formatter (includes provider/cost); fall back to local.
            lines = format_capability_lines(cap)
            return (
                lines
                if lines
                else [f"    model_id: {cap.model_id}"] + _format_capa(cap)
            )
    except Exception:
        pass
    return []


def _model_provider_note(
    explicit_key: str, *, fallback_key: str = "UAGENT_PROVIDER"
) -> str:
    """Annotate provider line when value comes from a fallback env key."""
    if _get_env(explicit_key):
        return ""
    if fallback_key and _get_env(fallback_key):
        return _("  (fallback: %(key)s)") % {"key": fallback_key}
    return _("  (fallback)")


def _model_value_note(
    *,
    explicit_keys: list[str],
    used_fallback: bool,
    fallback_label: str,
) -> str:
    """Annotate model line when a default/fallback value is used."""
    if any(_get_env(k) for k in explicit_keys):
        return ""
    if used_fallback and fallback_label:
        return _("  (fallback: %(key)s)") % {"key": fallback_label}
    return ""


def _append_resolved_model_section(
    lines: list[str],
    *,
    label: str,
    explicit_provider_key: str,
    resolved: tuple[str, str] | None,
    model_explicit_keys: list[str] | None = None,
    model_fallback_label: str = "",
    extra_lines: list[str] | None = None,
    verbose: bool = False,
) -> None:
    """Append one capability section, including fallback-resolved results."""
    if not resolved:
        lines.append(_("  %(label)s: (not configured)") % {"label": label})
        return

    provider, model = resolved
    prov_note = _model_provider_note(explicit_provider_key)
    model_note = _model_value_note(
        explicit_keys=model_explicit_keys or [],
        used_fallback=bool(model_fallback_label),
        fallback_label=model_fallback_label,
    )
    lines.append(_("  %(label)s:") % {"label": label})
    lines.append(
        _("    Provider: %(provider)s%(note)s")
        % {"provider": provider, "note": prov_note}
    )
    lines.append(
        _("    Model:    %(model)s%(note)s") % {"model": model, "note": model_note}
    )
    if extra_lines:
        lines.extend(extra_lines)
    if verbose:
        capa_lines = _fetch_model_capa(provider, model)
        if capa_lines:
            lines.extend(capa_lines)


def _image_analysis_model_keys(provider: str) -> tuple[list[str], str]:
    p = provider.upper()
    keys = [
        f"UAGENT_{p}_IMG_ANALYSIS_DEPNAME",
        "UAGENT_IMG_ANALYSIS_DEPNAME",
    ]
    if provider in ("openai", "azure", "ollama"):
        keys.append(f"UAGENT_{p}_DEPNAME")
        return keys, f"UAGENT_{p}_DEPNAME/default"
    if provider in ("gemini", "vertexai"):
        return keys, "default gemini-1.5-flash"
    return keys, "default"


def _image_generation_model_keys(provider: str) -> tuple[list[str], str]:
    p = provider.upper()
    keys = [f"UAGENT_{p}_IMG_GENERATE_DEPNAME", "UAGENT_IMG_GENERATE_DEPNAME"]
    defaults = {
        "openai": "default gpt-image-1",
        "gemini": "default imagen-4.0-generate-001",
        "vertexai": "default imagen-4.0-generate-001",
        "zai": "default glm-image",
        "grok": "default grok-imagine-image",
    }
    return keys, defaults.get(provider, "default")


def _audio_model_keys(provider: str, mode: str) -> tuple[list[str], str]:
    m = mode.upper()
    if provider == "azure":
        return [f"UAGENT_AZURE_{m}_DEPNAME"], f"UAGENT_AZURE_{m}_DEPNAME"
    if provider in ("gemini", "vertexai"):
        return (
            [f"UAGENT_GEMINI_{m}_DEPNAME", "UAGENT_GEMINI_MODEL"],
            "UAGENT_GEMINI_MODEL/default",
        )
    if provider == "grok":
        if mode == "speech":
            return (
                ["UAGENT_GROK_SPEECH_DEPNAME", "UAGENT_GROK_TTS_MODEL"],
                "default grok-tts",
            )
        return (
            ["UAGENT_GROK_TRANSCRIBE_DEPNAME", "UAGENT_GROK_STT_MODEL"],
            "default grok-stt-batch",
        )
    default = "gpt-4o-mini-tts" if mode == "speech" else "gpt-4o-mini-transcribe"
    return [f"UAGENT_OPENAI_{m}_DEPNAME"], f"default {default}"


def _handle_cmd_model(
    arg: str,
    *,
    core: Any,
    tr: Any,
) -> CommandResult:
    """Show detailed model configuration for all capabilities.

    :model         - show basic configuration
    :model v       - verbose: also show llmcapa details for all configured models

    Optional modalities (image/audio/embedding) use the same effective resolution
    as the startup banner, including UAGENT_PROVIDER / built-in model fallbacks.
    """
    verbose = arg.strip().lower() in ("v", "ver", "verbose")
    provider = _get_env("UAGENT_PROVIDER", "(none)")
    model = _get_env(f"UAGENT_{provider.upper()}_DEPNAME")
    if not model:
        model = _get_env("UAGENT_DEPNAME", "(not set)")

    lines: list[str] = []
    lines.append(_("=== Model Configuration ==="))
    lines.append(_("  Chat (main):"))
    display_provider = _("(none)") if provider == "(none)" else provider
    display_model = _("(not set)") if model == "(not set)" else model
    lines.append(
        _("    Provider: %(provider)s%(note)s")
        % {"provider": display_provider, "note": ""}
    )
    lines.append(
        _("    Model:    %(model)s%(note)s") % {"model": display_model, "note": ""}
    )
    if provider not in ("(none)", ""):
        try:
            from .llmcapa_util import deprecated_model_warning

            warn = deprecated_model_warning(model, provider)
            if warn:
                lines.append(_("    WARN: %(warn)s") % {"warn": warn})
        except Exception:
            pass
    if verbose and provider not in ("(none)", ""):
        capa_lines = _fetch_model_capa(provider, model)
        if capa_lines:
            lines.extend(capa_lines)

    # Resolve optional modalities with the same logic as startup banner.
    try:
        from .runtime.runtime_banner import (
            _audio_model_info,
            _embedding_model_info,
            _image_analysis_model_info,
            _image_generation_model_info,
        )
    except Exception:
        _audio_model_info = None  # type: ignore[assignment]
        _embedding_model_info = None  # type: ignore[assignment]
        _image_analysis_model_info = None  # type: ignore[assignment]
        _image_generation_model_info = None  # type: ignore[assignment]

    def _safe_resolve(fn: Any) -> tuple[str, str] | None:
        if fn is None:
            return None
        try:
            return fn()
        except Exception:
            return None

    ia_resolved = _safe_resolve(_image_analysis_model_info)
    ia_keys: list[str] = []
    ia_fb = ""
    if ia_resolved:
        ia_keys, ia_fb = _image_analysis_model_keys(ia_resolved[0])
    _append_resolved_model_section(
        lines,
        label=_("Image Analysis"),
        explicit_provider_key="UAGENT_IMG_ANALYSIS_PROVIDER",
        resolved=ia_resolved,
        model_explicit_keys=ia_keys,
        model_fallback_label=ia_fb,
        verbose=verbose,
    )

    ig_resolved = _safe_resolve(_image_generation_model_info)
    ig_keys: list[str] = []
    ig_fb = ""
    if ig_resolved:
        ig_keys, ig_fb = _image_generation_model_keys(ig_resolved[0])
    _append_resolved_model_section(
        lines,
        label=_("Image Generation"),
        explicit_provider_key="UAGENT_IMG_GENERATE_PROVIDER",
        resolved=ig_resolved,
        model_explicit_keys=ig_keys,
        model_fallback_label=ig_fb,
        verbose=verbose,
    )

    speech_resolved = _safe_resolve(
        (lambda: _audio_model_info("speech")) if _audio_model_info is not None else None
    )
    speech_keys: list[str] = []
    speech_fb = ""
    if speech_resolved:
        speech_keys, speech_fb = _audio_model_keys(speech_resolved[0], "speech")
    _append_resolved_model_section(
        lines,
        label=_("Audio Speech"),
        explicit_provider_key="UAGENT_AUDIO_SPEECH_PROVIDER",
        resolved=speech_resolved,
        model_explicit_keys=speech_keys,
        model_fallback_label=speech_fb,
        verbose=verbose,
    )

    tr_resolved = _safe_resolve(
        (lambda: _audio_model_info("transcribe"))
        if _audio_model_info is not None
        else None
    )
    tr_keys: list[str] = []
    tr_fb = ""
    if tr_resolved:
        tr_keys, tr_fb = _audio_model_keys(tr_resolved[0], "transcribe")
    _append_resolved_model_section(
        lines,
        label=_("Audio Transcribe"),
        explicit_provider_key="UAGENT_AUDIO_TRANSCRIBE_PROVIDER",
        resolved=tr_resolved,
        model_explicit_keys=tr_keys,
        model_fallback_label=tr_fb,
        verbose=verbose,
    )

    # Translation (requires explicit UAGENT_TRANSLATE_PROVIDER)
    translate_provider = _get_env("UAGENT_TRANSLATE_PROVIDER")
    if translate_provider:
        translate_model = _get_env("UAGENT_TRANSLATE_DEPNAME")
        model_fb = ""
        if not translate_model:
            translate_model = _get_env(f"UAGENT_{translate_provider.upper()}_DEPNAME")
            if translate_model:
                model_fb = f"UAGENT_{translate_provider.upper()}_DEPNAME"
        if translate_model:
            translate_to = _get_env("UAGENT_TRANSLATE_TO_LLM", "?")
            translate_from = _get_env("UAGENT_TRANSLATE_FROM_LLM", "?")
            model_note = (
                _("  (fallback: %(key)s)") % {"key": model_fb} if model_fb else ""
            )
            lines.append(_("  Translation:"))
            lines.append(
                _("    Provider: %(provider)s%(note)s")
                % {"provider": translate_provider, "note": ""}
            )
            lines.append(
                _("    Model:    %(model)s%(note)s")
                % {"model": translate_model, "note": model_note}
            )
            lines.append(
                _("    From→To:  %(src)s → %(dst)s")
                % {"src": translate_from, "dst": translate_to}
            )
            if verbose:
                capa_lines = _fetch_model_capa(translate_provider, translate_model)
                if capa_lines:
                    lines.extend(capa_lines)
        else:
            lines.append(_("  Translation: (not configured)"))
    else:
        lines.append(_("  Translation: (not configured)"))

    emb_resolved = _safe_resolve(_embedding_model_info)
    emb_keys: list[str] = []
    emb_fb = ""
    if emb_resolved:
        emb_keys = [f"UAGENT_{emb_resolved[0].upper()}_EMBEDDING_DEPNAME"]
        emb_fb = emb_keys[0]
    _append_resolved_model_section(
        lines,
        label=_("Embedding"),
        explicit_provider_key="UAGENT_EMBEDDING_PROVIDER",
        resolved=emb_resolved,
        model_explicit_keys=emb_keys,
        model_fallback_label=emb_fb,
        verbose=verbose,
    )

    print("\n".join(lines))
    return CommandResult()
