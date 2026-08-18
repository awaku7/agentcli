from __future__ import annotations

from pathlib import Path

from uagent.util_image import build_multimodal_user_message


def test_llama_cpp_video_input_is_bounded_and_typed(tmp_path: Path) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video-test")

    msg = build_multimodal_user_message(
        "describe this",
        [],
        video_paths=[str(video)],
        provider="llama_cpp",
        use_responses_api=False,
    )

    part = msg["content"][1]
    assert part["type"] == "input_video"
    assert part["input_video"]["url"].startswith("data:video/mp4;base64,")


def test_video_input_is_not_sent_to_other_providers(tmp_path: Path) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video-test")

    msg = build_multimodal_user_message(
        "describe this",
        [],
        video_paths=[str(video)],
        provider="openai",
        use_responses_api=False,
    )

    assert all(part.get("type") != "input_video" for part in msg["content"])
