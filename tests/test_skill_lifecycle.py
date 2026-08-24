from __future__ import annotations

import pytest

from uagent.runtime.skill_lifecycle import SkillLifecycleError, SkillLifecycleManager


def test_skill_requires_review_before_enable(tmp_path):
    manager = SkillLifecycleManager(tmp_path / "skills.json")
    manager.register("demo", version="1.0")

    with pytest.raises(SkillLifecycleError, match="validation"):
        manager.enable("demo", confirmed=True)

    manager.review("demo", validation_ok=True, security_review_ok=True)
    with pytest.raises(SkillLifecycleError, match="confirmation"):
        manager.enable("demo")
    assert manager.enable("demo", confirmed=True).state == "enabled"


def test_skill_usage_and_deprecation_are_persisted(tmp_path):
    path = tmp_path / "skills.json"
    manager = SkillLifecycleManager(path)
    manager.register("demo")
    manager.review("demo", validation_ok=True, security_review_ok=True)
    manager.enable("demo", confirmed=True)
    manager.record_use("demo")
    record = manager.deprecate("demo", reason="replaced", confirmed=True)

    assert record.usage_count == 1
    assert record.state == "deprecated"
    assert record.deprecated_reason == "replaced"
    assert len(SkillLifecycleManager(path).get("demo").history) == 3
