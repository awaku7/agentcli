from __future__ import annotations


def test_skill_system_message_honors_user_selected_skill() -> None:
    from uagent.util_message import _format_skill_system_content

    content = _format_skill_system_content(
        skill={
            "name": "vup-build-release-whl",
            "path": "C:/skills/vup-build-release-whl",
        },
        doc={
            "frontmatter": {},
            "body_markdown": "Build and release the selected package.",
        },
    )

    assert "name=vup-build-release-whl" in content
    assert "The user selected the exact skill identified in this message." in content
    assert "Do not substitute, load, or follow a different skill" in content
    assert "Build and release the selected package." in content
