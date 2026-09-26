import pytest

import uagent.runtime.observability.content_capture as cc
from uagent.runtime.observability.content_capture import (
    CaptureCandidate,
    CaptureCandidateMeta,
    ContentCaptureBuffer,
    ContentCapturePolicy,
    ProvenanceNode,
    REDACTED,
    make_text_candidate,
    prepare_content_event,
)
from uagent.runtime.observability.settings import ObservabilitySettings


def _policy(*categories: str, field: int = 2048, span: int = 8192):
    settings = ObservabilitySettings(
        enabled=True,
        capture_content=True,
        capture_categories=frozenset(categories),
        capture_max_field_chars=field,
        capture_max_span_chars=span,
    )
    return ContentCapturePolicy.from_settings(settings)


def test_content_gates_and_closed_carrier():
    candidate = make_text_candidate(
        category="user_input",
        value="hello",
        ordinal=1,
    )
    disabled = ContentCapturePolicy.from_settings(
        ObservabilitySettings(
            enabled=False,
            capture_content=True,
            capture_categories=frozenset({"user_input"}),
        )
    )
    assert prepare_content_event(candidate, disabled) is None

    event = prepare_content_event(candidate, _policy("user_input"))
    assert event is not None
    assert event.is_trusted()
    assert event.attributes() == {
        "uag.content.category": "user_input",
        "uag.content.value": "hello",
        "uag.content.ordinal": 1,
    }


@pytest.mark.parametrize(
    "value",
    [
        "jwt=aaa.bbb.ccc!",
        "jwt=aaa.bbb.ccc?",
        "jwt=aaa.bbb.ccc,",
        "jwt=aaa.bbb.ccc)",
        "jwt=aaa.bbb.ccc.",
        "jwt=aaa.bbb.ccc. next",
        "access_token=aaa.bbb.ccc",
        "jwt:aaa.bbb.ccc",
    ],
)
def test_jwt_boundary_corpus_redacts(value):
    event = prepare_content_event(
        make_text_candidate(category="user_input", value=value, ordinal=1),
        _policy("user_input"),
    )
    assert event is not None
    assert event.value == REDACTED


@pytest.mark.parametrize(
    "value",
    [
        "aaa.bbb.ccc.ddd",
        "aaa.bbb.ccc.d",
        ".aaa.bbb.ccc",
    ],
)
def test_jwt_near_misses_are_not_prefix_matched(value):
    event = prepare_content_event(
        make_text_candidate(category="user_input", value=value, ordinal=1),
        _policy("user_input"),
    )
    assert event is not None
    assert event.value == value


@pytest.mark.parametrize(
    "value",
    [
        "api_key=sk-proj-example",
        "api-key: sk-example",
        '"api_key":"sk-example"',
        'OPENAI_API_KEY="sk-example"',
        "UAGENT_OPENAI_API_KEY=sk-example",
        "UAGENT_CLAUDE_API_KEY: example",
        "access_token=example",
        'client_secret : "example"',
    ],
)
def test_credential_assignments_are_redacted(value):
    event = prepare_content_event(
        make_text_candidate(category="user_input", value=value, ordinal=1),
        _policy("user_input"),
    )
    assert event is not None
    assert event.value == REDACTED


@pytest.mark.parametrize(
    "value",
    [
        "api_key=",
        'api_key=""',
        "api_key_name=demo",
        "input_tokens=42",
        "monkey=value",
    ],
)
def test_assignment_near_misses_remain_visible(value):
    event = prepare_content_event(
        make_text_candidate(category="user_input", value=value, ordinal=1),
        _policy("user_input"),
    )
    assert event is not None
    assert event.value == value


@pytest.mark.parametrize(
    "value",
    [
        "https://user:password@example.com/path",
        "https://:password@example.com/path",
        "-----BEGIN PRIVATE KEY-----\nsecret",
        "-----BEGIN ENCRYPTED PRIVATE KEY-----\nsecret",
        "-----BEGIN RSA PRIVATE KEY-----\nsecret",
        "-----BEGIN DSA PRIVATE KEY-----\nsecret",
        "-----BEGIN EC PRIVATE KEY-----\nsecret",
        "-----BEGIN OPENSSH PRIVATE KEY-----\nsecret",
    ],
)
def test_uri_passwords_and_private_keys_omit_whole_candidate(value):
    event = prepare_content_event(
        make_text_candidate(category="user_input", value=value, ordinal=1),
        _policy("user_input"),
    )
    assert event is None


@pytest.mark.parametrize(
    "value",
    [
        "Bearer abcdef",
        "prefix Basic abcdef",
        "OPENAI_API_KEY=abcdefghijklmnopqrstuvwxyz",
        "ghp_abcdefghijklmnopqrstuvwxyz",
    ],
)
def test_high_confidence_secret_forms_never_pass_unchanged(value):
    event = prepare_content_event(
        make_text_candidate(category="assistant_output", value=value, ordinal=1),
        _policy("assistant_output"),
    )
    assert event is not None
    assert event.value == REDACTED


def test_duplicate_ordinal_and_candidate_33_are_rejected_before_value_inspection():
    class Exploding:
        def __getattribute__(self, name):
            raise AssertionError(
                "candidate value must not be inspected during admission"
            )

    buffer = ContentCaptureBuffer(_policy("user_input"))
    assert buffer.admit(
        make_text_candidate(category="user_input", value="first", ordinal=1)
    )
    duplicate = CaptureCandidate(
        ordinal=1,
        value=Exploding(),
        meta=make_text_candidate(
            category="user_input",
            value="unused",
            ordinal=2,
        ).meta,
    )
    assert buffer.admit(duplicate) is False

    for ordinal in range(2, 32):
        assert buffer.admit(
            make_text_candidate(
                category="user_input",
                value=f"value-{ordinal}",
                ordinal=ordinal,
            )
        )
    candidate_33 = CaptureCandidate(
        ordinal=32,
        value=Exploding(),
        meta=make_text_candidate(
            category="user_input",
            value="unused",
            ordinal=2,
        ).meta,
    )
    assert buffer.admit(candidate_33) is False


def test_span_budget_is_deterministic_and_later_smaller_candidate_can_fit():
    policy = _policy("user_input", "assistant_output", field=64, span=7)
    buffer = ContentCaptureBuffer(policy)
    buffer.admit(
        make_text_candidate(category="assistant_output", value="b", ordinal=2)
    )
    buffer.admit(
        make_text_candidate(category="user_input", value="12345678", ordinal=1)
    )
    buffer.admit(
        make_text_candidate(category="assistant_output", value="cc", ordinal=3)
    )

    events = buffer.prepared_events()
    assert [(event.category, event.ordinal, event.value) for event in events] == [
        ("assistant_output", 2, "b"),
        ("assistant_output", 3, "cc"),
    ]


def test_wrong_root_owner_and_unreviewed_adapter_fail_closed():
    policy = _policy("user_input")
    cases = [
        CaptureCandidate(
            ordinal=1,
            value="hello",
            meta=CaptureCandidateMeta(
                category="user_input",
                root_provenance="assistant_message",
                owner_kind="invoke_agent",
                source_adapter_id="user_message.text.v1",
                root=ProvenanceNode("assistant_message"),
            ),
        ),
        CaptureCandidate(
            ordinal=1,
            value="hello",
            meta=CaptureCandidateMeta(
                category="user_input",
                root_provenance="user_message",
                owner_kind="execute_tool",
                source_adapter_id="user_message.text.v1",
                root=ProvenanceNode("user_message"),
            ),
        ),
        CaptureCandidate(
            ordinal=1,
            value="hello",
            meta=CaptureCandidateMeta(
                category="user_input",
                root_provenance="user_message",
                owner_kind="invoke_agent",
                source_adapter_id="payload-selected",
                root=ProvenanceNode("user_message"),
            ),
        ),
    ]
    assert all(prepare_content_event(case, policy) is None for case in cases)


def test_text_adapter_rejects_structured_payload_with_forged_metadata():
    candidate = CaptureCandidate(
        ordinal=1,
        value={"text": "hello"},
        meta=CaptureCandidateMeta(
            category="user_input",
            root_provenance="user_message",
            owner_kind="invoke_agent",
            source_adapter_id="user_message.text.v1",
            root=ProvenanceNode(
                "user_message",
                entries=(
                    (
                        ProvenanceNode("user_message"),
                        ProvenanceNode("user_message"),
                    ),
                ),
            ),
        ),
    )
    assert prepare_content_event(candidate, _policy("user_input")) is None


def test_bounded_traversal_blocks_secret_keys_and_hard_denied_children():
    policy = _policy("tool_arguments")
    value = {"safe": "ok", "api_key": "secret"}
    node = ProvenanceNode(
        "tool_argument",
        entries=(
            (
                ProvenanceNode("tool_argument"),
                ProvenanceNode("tool_argument"),
            ),
            (
                ProvenanceNode("tool_argument"),
                ProvenanceNode("tool_argument"),
            ),
        ),
    )
    with pytest.raises(cc._OmitCandidate):
        cc._Traversal(policy).walk(value, node, depth=0)

    denied = ProvenanceNode(
        "tool_argument",
        entries=(
            (
                ProvenanceNode("tool_argument"),
                ProvenanceNode("credential"),
            ),
        ),
    )
    with pytest.raises(cc._OmitCandidate):
        cc._Traversal(policy).walk({"safe": "ok"}, denied, depth=0)


def test_structural_width_depth_cycle_and_scalar_bounds_fail_closed():
    policy = _policy("tool_arguments", field=64)
    wide = list(range(65))
    wide_node = ProvenanceNode(
        "tool_argument",
        children=tuple(ProvenanceNode("tool_argument") for _ in wide),
    )
    with pytest.raises(cc._OmitCandidate):
        cc._Traversal(policy).walk(wide, wide_node, depth=0)

    deep_value = "leaf"
    deep_node = ProvenanceNode("tool_argument")
    for _ in range(9):
        deep_value = [deep_value]
        deep_node = ProvenanceNode("tool_argument", children=(deep_node,))
    with pytest.raises(cc._OmitCandidate):
        cc._Traversal(policy).walk(deep_value, deep_node, depth=0)

    cyclic = []
    cyclic.append(cyclic)
    cyclic_node = ProvenanceNode("tool_argument")
    object.__setattr__(cyclic_node, "children", (cyclic_node,))
    with pytest.raises(cc._OmitCandidate):
        cc._Traversal(policy).walk(cyclic, cyclic_node, depth=0)

    with pytest.raises(cc._OmitCandidate):
        cc._Traversal(policy).walk(
            "x" * 65,
            ProvenanceNode("tool_argument"),
            depth=0,
        )


def test_exact_runtime_types_integer_and_float_preflight():
    policy = _policy("tool_arguments")

    class CustomStr(str):
        pass

    for value in (CustomStr("x"), 2**63, float("inf")):
        with pytest.raises(cc._OmitCandidate):
            cc._Traversal(policy).walk(
                value,
                ProvenanceNode("tool_argument"),
                depth=0,
            )


def test_emit_requires_dedicated_content_carrier():
    class GenericOnlySpan:
        def __init__(self):
            self.events = []

        def add_event(self, name, attributes=None):
            self.events.append((name, attributes))

    class DedicatedSpan:
        def __init__(self):
            self.events = []

        def add_content_event(self, event):
            self.events.append(event)

    buffer = ContentCaptureBuffer(_policy("user_input"))
    buffer.admit(
        make_text_candidate(category="user_input", value="hello", ordinal=1)
    )

    generic = GenericOnlySpan()
    dedicated = DedicatedSpan()
    assert buffer.emit_to(generic) == 0
    assert generic.events == []
    assert buffer.emit_to(dedicated) == 1
    assert dedicated.events[0].value == "hello"
