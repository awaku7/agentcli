from uagent.computer_use.transports.bedrock import BedrockTransport


def test_bedrock_transport_builds_anthropic_request():
    request = BedrockTransport().build_request(
        model_id="us.anthropic.claude-opus-4-7",
        tool={"type": "computer_20251124", "name": "computer"},
        beta_header="computer-use-2025-11-24",
        messages=[{"role": "user", "content": "inspect"}],
        max_tokens=1024,
    )
    assert request["modelId"] == "us.anthropic.claude-opus-4-7"
    assert request["body"]["anthropic_version"] == "bedrock-2023-05-31"
    assert request["body"]["anthropic_beta"] == ["computer-use-2025-11-24"]
    assert request["body"]["tools"][0]["type"] == "computer_20251124"


def test_bedrock_transport_supports_mantle_headers():
    headers = BedrockTransport().headers("computer-use-2025-11-24")
    assert headers["anthropic-beta"] == "computer-use-2025-11-24"
