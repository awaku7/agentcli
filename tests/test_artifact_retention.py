from __future__ import annotations

from datetime import datetime, timezone

from uagent.runtime.artifact_retention import ArtifactRetentionPolicy


def test_defaults_are_conservative() -> None:
    policy = ArtifactRetentionPolicy()

    assert policy.max_total_bytes == 1024**3
    assert policy.max_artifacts == 10_000
    assert policy.max_artifact_bytes == 100 * 1024**2
    assert policy.auto_delete is False
    assert policy.dry_run is True


def test_plan_keeps_referenced_and_protected_artifacts() -> None:
    policy = ArtifactRetentionPolicy(
        max_total_bytes=10,
        max_artifacts=10,
        max_age_days=30,
    )
    artifacts = [
        {
            "artifact_id": "old",
            "size": 8,
            "created_at": "2020-01-01T00:00:00+00:00",
            "evictable": True,
        },
        {
            "artifact_id": "referenced",
            "size": 8,
            "created_at": "2020-01-02T00:00:00+00:00",
            "evictable": True,
        },
        {
            "artifact_id": "protected",
            "size": 8,
            "created_at": "2020-01-03T00:00:00+00:00",
            "evictable": False,
        },
    ]

    plan = policy.plan(
        artifacts,
        referenced_ids={"referenced"},
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert [item["artifact_id"] for item in plan] == ["old"]
