"""Safe Artifact quota and cleanup planning."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class ArtifactRetentionPolicy:
    """Defaults are conservative; deletion remains opt-in."""

    max_total_bytes: int = 1 * 1024 * 1024 * 1024
    max_artifacts: int = 10_000
    max_artifact_bytes: int = 100 * 1024 * 1024
    max_age_days: int = 30
    auto_delete: bool = False
    dry_run: bool = True

    @classmethod
    def from_environment(cls) -> "ArtifactRetentionPolicy":
        def integer(name: str, default: int) -> int:
            try:
                return max(0, int(os.environ.get(name, str(default))))
            except (TypeError, ValueError):
                return default

        def boolean(name: str, default: bool) -> bool:
            return os.environ.get(name, str(default)).strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }

        return cls(
            max_total_bytes=integer(
                "UAGENT_ARTIFACT_MAX_TOTAL_BYTES", cls.max_total_bytes
            ),
            max_artifacts=integer("UAGENT_ARTIFACT_MAX_COUNT", cls.max_artifacts),
            max_artifact_bytes=integer(
                "UAGENT_ARTIFACT_MAX_BYTES", cls.max_artifact_bytes
            ),
            max_age_days=integer("UAGENT_ARTIFACT_MAX_AGE_DAYS", cls.max_age_days),
            auto_delete=boolean("UAGENT_ARTIFACT_AUTO_DELETE", cls.auto_delete),
            dry_run=boolean("UAGENT_ARTIFACT_CLEANUP_DRY_RUN", cls.dry_run),
        )

    def plan(
        self,
        artifacts: list[dict[str, Any]],
        *,
        referenced_ids: set[str] | None = None,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Return deletion candidates without deleting anything."""
        referenced = referenced_ids or set()
        current = now or datetime.now(timezone.utc)
        cutoff = current - timedelta(days=self.max_age_days)
        ordered = sorted(
            artifacts,
            key=lambda item: str(item.get("created_at") or ""),
        )
        total = sum(max(0, int(item.get("size") or 0)) for item in ordered)
        candidates: list[dict[str, Any]] = []
        for item in ordered:
            artifact_id = str(item.get("artifact_id") or "")
            if artifact_id in referenced or not bool(item.get("evictable", True)):
                continue
            try:
                created = datetime.fromisoformat(str(item.get("created_at")))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                created = current
            over_quota = (
                total > self.max_total_bytes or len(ordered) > self.max_artifacts
            )
            too_old = created < cutoff
            too_large = int(item.get("size") or 0) > self.max_artifact_bytes
            if over_quota or too_old or too_large:
                candidates.append(item)
                total -= max(0, int(item.get("size") or 0))
                if (
                    len(ordered) - len(candidates) <= self.max_artifacts
                    and total <= self.max_total_bytes
                ):
                    if not too_old and not too_large:
                        break
        return candidates


__all__ = ["ArtifactRetentionPolicy"]
