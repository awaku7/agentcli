"""Metadata-only observability for Auto Pilot judgment strategies."""

from __future__ import annotations

from typing import Any

from .bootstrap import get_observability_backend


def record_auto_pilot_judgment(
    *,
    source: str,
    round_number: int,
    answer: str | None = None,
    fallback: bool = False,
    provider: str = "",
    model: str = "",
    confidence: float | None = None,
    latency_ms: float | None = None,
    error_type: str = "",
    additional_call: bool = True,
) -> None:
    """Record one Auto Pilot judgment attempt without prompt or response content."""

    try:
        backend = get_observability_backend()
        if not backend.enabled:
            return

        status = (
            "ok" if not error_type and answer in {"COMPLETE", "CONTINUE"} else "error"
        )
        attributes: dict[str, Any] = {
            "uag.decision.site": "auto_pilot_review",
            "uag.auto.judgment.source": str(source or "unknown"),
            "uag.auto.judgment.status": status,
            "uag.auto.judgment.round": max(0, int(round_number)),
            "uag.auto.judgment.fallback": bool(fallback),
            "uag.auto.judgment.additional_call": bool(additional_call),
        }
        if answer:
            attributes["uag.auto.judgment.answer"] = str(answer)
        if provider:
            attributes["uag.auto.judgment.provider"] = str(provider)
        if model:
            attributes["uag.auto.judgment.model"] = str(model)
        if confidence is not None:
            attributes["uag.auto.judgment.confidence"] = float(confidence)
        if latency_ms is not None:
            attributes["uag.auto.judgment.latency_ms"] = max(0.0, float(latency_ms))
        if error_type:
            attributes["uag.auto.judgment.error_type"] = str(error_type)

        backend.record_event("uag.auto.judgment", attributes)

        metric_attributes = {
            "uag.decision.site": "auto_pilot_review",
            "uag.auto.judgment.source": attributes["uag.auto.judgment.source"],
            "uag.auto.judgment.status": status,
            "uag.auto.judgment.fallback": bool(fallback),
            "uag.auto.judgment.provider": str(provider or ""),
        }
        if answer:
            metric_attributes["uag.auto.judgment.answer"] = str(answer)
        backend.record_counter("uag.auto.judgment.attempts", 1, metric_attributes)
        if status == "ok":
            backend.record_counter("uag.auto.judgments", 1, metric_attributes)
        else:
            backend.record_counter("uag.auto.judgment.failures", 1, metric_attributes)
        if latency_ms is not None:
            backend.record_histogram(
                "uag.auto.judgment.latency_ms",
                max(0.0, float(latency_ms)),
                metric_attributes,
            )
    except Exception:
        pass


def record_auto_pilot_run_finished(
    *,
    reason: str,
    rounds: int,
    judgment_source: str = "",
    max_rounds_reached: bool = False,
) -> None:
    """Record one terminal Auto Pilot outcome using metadata only."""

    try:
        backend = get_observability_backend()
        if not backend.enabled:
            return

        attributes: dict[str, Any] = {
            "uag.auto.run.reason": str(reason or "unknown"),
            "uag.auto.run.followup_rounds": max(0, int(rounds)),
            "uag.auto.run.max_rounds_reached": bool(max_rounds_reached),
        }
        if judgment_source:
            attributes["uag.auto.run.judgment_source"] = str(judgment_source)

        backend.record_event("uag.auto.run.finished", attributes)
        metric_attributes = {
            "uag.auto.run.reason": attributes["uag.auto.run.reason"],
            "uag.auto.run.judgment_source": str(judgment_source or ""),
            "uag.auto.run.max_rounds_reached": bool(max_rounds_reached),
        }
        backend.record_counter("uag.auto.runs", 1, metric_attributes)
        backend.record_histogram(
            "uag.auto.followup_rounds",
            max(0, int(rounds)),
            metric_attributes,
        )
    except Exception:
        pass


__all__ = [
    "record_auto_pilot_judgment",
    "record_auto_pilot_run_finished",
]
