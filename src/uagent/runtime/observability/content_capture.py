"""Phase 4A controlled-content policy and bounded rendering."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass

from .settings import ObservabilitySettings

CONTENT_EVENT_NAME = "uag.content"
REDACTED = "[REDACTED]"
_PREPARED_EVENT_TOKEN = object()

CONTENT_CATEGORIES = (
    "user_input",
    "assistant_output",
    "tool_arguments",
    "tool_result",
)
_CATEGORY_ORDER = {name: index for index, name in enumerate(CONTENT_CATEGORIES)}

PROVENANCE_VALUES = frozenset(
    {
        "user_message",
        "assistant_message",
        "tool_argument",
        "ordinary_tool_result",
        "authentication",
        "session",
        "credential",
        "memory",
        "retrieval",
        "file",
        "artifact",
        "reasoning",
        "system_instruction",
        "developer_instruction",
        "security_sensitive_unknown",
    }
)
HARD_DENIED_PROVENANCE = frozenset(
    {
        "authentication",
        "session",
        "credential",
        "memory",
        "retrieval",
        "file",
        "artifact",
        "reasoning",
        "system_instruction",
        "developer_instruction",
        "security_sensitive_unknown",
    }
)
_ALLOWED_ROOT_PAIR = {
    "user_input": "user_message",
    "assistant_output": "assistant_message",
    "tool_arguments": "tool_argument",
    "tool_result": "ordinary_tool_result",
}
_ALLOWED_OWNER = {
    "user_input": "invoke_agent",
    "assistant_output": "invoke_agent",
    "tool_arguments": "execute_tool",
    "tool_result": "execute_tool",
}

MAX_CAPTURE_DEPTH = 8
MAX_COLLECTION_ITEMS = 64
MAX_CAPTURE_NODES = 256
MAX_CAPTURE_CANDIDATES_PER_SPAN = 32

_REVIEWED_ADAPTERS = {
    "user_message.text.v1": ("user_input", "user_message", "invoke_agent"),
    "assistant_message.visible_text.v1": (
        "assistant_output",
        "assistant_message",
        "invoke_agent",
    ),
}

_BLOCKED_FRAGMENTS = (
    "authorization",
    "cookie",
    "password",
    "passwd",
    "secret",
    "client_secret",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "principal_id",
    "subject",
    "display_name",
    "email",
    "group",
    "room_id",
    "project_id",
    "session_id",
)
_CREDENTIAL_LABELS = frozenset(
    {
        "api_key",
        "apikey",
        "access_key",
        "access_key_id",
        "secret_key",
        "client_secret",
        "private_key",
        "access_token",
        "refresh_token",
        "id_token",
        "authorization",
        "password",
        "passwd",
        "cookie",
    }
)
_CREDENTIAL_SUFFIXES = (
    "_api_key",
    "_access_key",
    "_secret_key",
    "_client_secret",
    "_private_key",
    "_access_token",
    "_refresh_token",
)
_PEM_HEADERS = (
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN ENCRYPTED PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN DSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
)
_BARE_KEY_PREFIXES = (
    "sk-",
    "sk-ant-",
    "xai-",
    "gsk_",
    "AIza",
    "ghp_",
    "github_pat_",
)
_URI_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]{0,31}://")
_LABEL_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-/"
)
_BARE_TOKEN_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"
)


class _OmitCandidate(Exception):
    pass


@dataclass(frozen=True)
class ProvenanceNode:
    provenance: str
    children: tuple["ProvenanceNode", ...] = ()
    entries: tuple[tuple["ProvenanceNode", "ProvenanceNode"], ...] = ()


@dataclass(frozen=True)
class CaptureCandidateMeta:
    category: str
    root_provenance: str
    owner_kind: str
    source_adapter_id: str
    root: ProvenanceNode


@dataclass(frozen=True)
class CaptureCandidate:
    ordinal: int
    value: object
    meta: CaptureCandidateMeta


@dataclass(frozen=True)
class PreparedContentEvent:
    category: str
    value: str
    ordinal: int
    _token: object

    def is_trusted(self) -> bool:
        return self._token is _PREPARED_EVENT_TOKEN

    def attributes(self) -> dict[str, object]:
        if not self.is_trusted():
            return {}
        return {
            "uag.content.category": self.category,
            "uag.content.value": self.value,
            "uag.content.ordinal": self.ordinal,
        }


@dataclass(frozen=True)
class ContentCapturePolicy:
    enabled: bool
    categories: frozenset[str]
    max_field_chars: int
    max_span_chars: int

    @classmethod
    def from_settings(cls, settings: ObservabilitySettings) -> "ContentCapturePolicy":
        return cls(
            enabled=bool(settings.enabled and settings.capture_content),
            categories=frozenset(settings.capture_categories),
            max_field_chars=settings.capture_max_field_chars,
            max_span_chars=settings.capture_max_span_chars,
        )


class ContentCaptureBuffer:
    """Admit candidates without inspecting values, then render deterministically."""

    def __init__(self, policy: ContentCapturePolicy) -> None:
        self._policy = policy
        self._admitted: list[CaptureCandidate] = []
        self._seen_ordinals: set[int] = set()
        self._candidate_count = 0

    def admit(self, candidate: CaptureCandidate) -> bool:
        """Perform only candidate-count/ordinal admission before value inspection."""

        self._candidate_count += 1
        if self._candidate_count > MAX_CAPTURE_CANDIDATES_PER_SPAN:
            return False
        if type(candidate) is not CaptureCandidate:
            return False
        ordinal = candidate.ordinal
        if type(ordinal) is not int or not 1 <= ordinal <= 32:
            return False
        if ordinal in self._seen_ordinals:
            return False
        self._seen_ordinals.add(ordinal)
        self._admitted.append(candidate)
        return True

    def prepared_events(self) -> tuple[PreparedContentEvent, ...]:
        if not self._policy.enabled:
            return ()

        orderable: list[tuple[int, int, CaptureCandidate]] = []
        for candidate in self._admitted:
            try:
                meta = candidate.meta
                if type(meta) is not CaptureCandidateMeta:
                    continue
                category = meta.category
                ordinal = candidate.ordinal
                if type(category) is not str:
                    continue
                if type(ordinal) is not int or not 1 <= ordinal <= 32:
                    continue
                orderable.append(
                    (
                        _CATEGORY_ORDER.get(category, len(_CATEGORY_ORDER)),
                        ordinal,
                        candidate,
                    )
                )
            except Exception:
                continue

        ordered = [
            candidate
            for _, _, candidate in sorted(
                orderable,
                key=lambda item: (item[0], item[1]),
            )
        ]
        used_chars = 0
        events: list[PreparedContentEvent] = []
        for candidate in ordered:
            event = prepare_content_event(candidate, self._policy)
            if event is None:
                continue
            cost = len(event.value)
            if used_chars + cost > self._policy.max_span_chars:
                continue
            used_chars += cost
            events.append(event)
        return tuple(events)

    def emit_to(self, span: object) -> int:
        """Emit through the dedicated trusted carrier when supported.

        A backend lacking ``add_content_event`` is treated as unsupported rather
        than falling back to generic ``add_event``.
        """

        emitted = 0
        try:
            add_content_event = getattr(span, "add_content_event")
        except Exception:
            return 0
        for event in self.prepared_events():
            try:
                add_content_event(event)
            except Exception:
                continue
            emitted += 1
        return emitted


def make_text_candidate(
    *,
    category: str,
    value: str,
    ordinal: int,
) -> CaptureCandidate:
    """Create one of the two initial reviewed plain-text candidate shapes."""

    if category == "user_input":
        provenance = "user_message"
        owner = "invoke_agent"
        adapter = "user_message.text.v1"
    elif category == "assistant_output":
        provenance = "assistant_message"
        owner = "invoke_agent"
        adapter = "assistant_message.visible_text.v1"
    else:
        raise ValueError("only initial reviewed text adapters are supported")
    return CaptureCandidate(
        ordinal=ordinal,
        value=value,
        meta=CaptureCandidateMeta(
            category=category,
            root_provenance=provenance,
            owner_kind=owner,
            source_adapter_id=adapter,
            root=ProvenanceNode(provenance=provenance),
        ),
    )


def prepare_content_event(
    candidate: CaptureCandidate,
    policy: ContentCapturePolicy,
) -> PreparedContentEvent | None:
    """Apply the normative Phase 4A fail-closed policy to one admitted candidate."""

    try:
        if type(candidate) is not CaptureCandidate:
            raise _OmitCandidate
        if not policy.enabled:
            raise _OmitCandidate

        meta = candidate.meta
        if type(meta) is not CaptureCandidateMeta:
            raise _OmitCandidate
        if meta.category not in CONTENT_CATEGORIES:
            raise _OmitCandidate
        if meta.category not in policy.categories:
            raise _OmitCandidate
        if meta.root_provenance not in PROVENANCE_VALUES:
            raise _OmitCandidate
        if _ALLOWED_ROOT_PAIR.get(meta.category) != meta.root_provenance:
            raise _OmitCandidate
        if meta.root_provenance in HARD_DENIED_PROVENANCE:
            raise _OmitCandidate
        if _ALLOWED_OWNER.get(meta.category) != meta.owner_kind:
            raise _OmitCandidate

        reviewed = _REVIEWED_ADAPTERS.get(meta.source_adapter_id)
        if reviewed != (meta.category, meta.root_provenance, meta.owner_kind):
            raise _OmitCandidate
        if (
            meta.source_adapter_id
            in {
                "user_message.text.v1",
                "assistant_message.visible_text.v1",
            }
            and type(candidate.value) is not str
        ):
            raise _OmitCandidate
        if type(meta.root) is not ProvenanceNode:
            raise _OmitCandidate
        if meta.root.provenance != meta.root_provenance:
            raise _OmitCandidate

        traversal = _Traversal(policy)
        safe_value = traversal.walk(candidate.value, meta.root, depth=0)
        rendered = _render_value(safe_value)
        _check_post_redaction_tokens(safe_value, policy.max_field_chars)
        return PreparedContentEvent(
            category=meta.category,
            value=rendered,
            ordinal=candidate.ordinal,
            _token=_PREPARED_EVENT_TOKEN,
        )
    except Exception:
        return None


class _Traversal:
    def __init__(self, policy: ContentCapturePolicy) -> None:
        self.policy = policy
        self.nodes = 0
        self.active_value_containers: set[int] = set()
        self.active_meta_nodes: set[int] = set()

    def _enter_occurrence(
        self, value: object, node: ProvenanceNode, depth: int
    ) -> None:
        if depth > MAX_CAPTURE_DEPTH:
            raise _OmitCandidate
        self.nodes += 1
        if self.nodes > MAX_CAPTURE_NODES:
            raise _OmitCandidate
        if type(node) is not ProvenanceNode:
            raise _OmitCandidate
        if node.provenance not in PROVENANCE_VALUES:
            raise _OmitCandidate
        if node.provenance in HARD_DENIED_PROVENANCE:
            raise _OmitCandidate

        value_type = type(value)
        if value_type not in {dict, list, tuple, str, int, float, bool, type(None)}:
            raise _OmitCandidate

    def walk(self, value: object, node: ProvenanceNode, *, depth: int) -> object:
        self._enter_occurrence(value, node, depth)
        value_type = type(value)

        if value_type is str:
            if node.children or node.entries:
                raise _OmitCandidate
            return _sanitize_string(value, self.policy.max_field_chars)

        if value_type is bool or value is None:
            if node.children or node.entries:
                raise _OmitCandidate
            return value

        if value_type is int:
            if node.children or node.entries:
                raise _OmitCandidate
            if value < -(2**63) or value > 2**63 - 1:
                raise _OmitCandidate
            return value

        if value_type is float:
            if node.children or node.entries:
                raise _OmitCandidate
            if not math.isfinite(value):
                raise _OmitCandidate
            return value

        value_id = id(value)
        node_id = id(node)
        if (
            value_id in self.active_value_containers
            or node_id in self.active_meta_nodes
        ):
            raise _OmitCandidate
        self.active_value_containers.add(value_id)
        self.active_meta_nodes.add(node_id)
        try:
            if value_type in {list, tuple}:
                if node.entries:
                    raise _OmitCandidate
                if len(value) > MAX_COLLECTION_ITEMS:
                    raise _OmitCandidate
                if len(node.children) != len(value):
                    raise _OmitCandidate
                rendered = [
                    self.walk(item, child, depth=depth + 1)
                    for item, child in zip(value, node.children)
                ]
                return tuple(rendered) if value_type is tuple else rendered

            if value_type is dict:
                if node.children:
                    raise _OmitCandidate
                if len(value) > MAX_COLLECTION_ITEMS:
                    raise _OmitCandidate
                if len(node.entries) != len(value):
                    raise _OmitCandidate
                rendered_dict: dict[str, object] = {}
                for (key, item), (key_node, value_node) in zip(
                    value.items(), node.entries
                ):
                    if type(key) is not str:
                        raise _OmitCandidate
                    safe_key = self.walk(key, key_node, depth=depth + 1)
                    if type(safe_key) is not str or _blocked_mapping_key(
                        safe_key, self.policy.max_field_chars
                    ):
                        raise _OmitCandidate
                    rendered_dict[safe_key] = self.walk(
                        item, value_node, depth=depth + 1
                    )
                return rendered_dict
        finally:
            self.active_value_containers.discard(value_id)
            self.active_meta_nodes.discard(node_id)

        raise _OmitCandidate


def _contains_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(char) <= 0xDFFF for char in value)


def _sanitize_string(value: str, max_field_chars: int) -> str:
    if type(value) is not str or len(value) > max_field_chars:
        raise _OmitCandidate
    if _contains_surrogate(value):
        raise _OmitCandidate

    action = _detect_secret(value)
    if action == "omit":
        raise _OmitCandidate
    if action == "redact":
        return REDACTED
    return value


def _blocked_mapping_key(key: str, max_field_chars: int) -> bool:
    if type(key) is not str or len(key) > max_field_chars or _contains_surrogate(key):
        return True

    normalized = key.strip().lower()
    if any(fragment in normalized for fragment in _BLOCKED_FRAGMENTS):
        return True

    canonical = normalized.replace("_", ".").replace("-", ".").replace("/", ".")
    if "token" in {part for part in canonical.split(".") if part}:
        return True

    ascii_trimmed = key.strip(" \t")
    return _is_credential_label(ascii_trimmed)


def _ascii_lower(value: str) -> str:
    chars: list[str] = []
    for char in value:
        code = ord(char)
        chars.append(chr(code + 32) if 65 <= code <= 90 else char)
    return "".join(chars)


def _credential_label_canonical(label: str) -> str | None:
    if not label or any(char not in _LABEL_CHARS for char in label):
        return None
    return _ascii_lower(label).replace("-", "_").replace(".", "_").replace("/", "_")


def _is_credential_label(label: str) -> bool:
    canonical = _credential_label_canonical(label)
    if canonical is None:
        return False
    if canonical in _CREDENTIAL_LABELS:
        return True
    for suffix in _CREDENTIAL_SUFFIXES:
        if canonical.endswith(suffix):
            prefix = canonical[: -len(suffix)]
            if any(char.isascii() and char.isalnum() for char in prefix):
                return True
    return False


def _detect_secret(value: str) -> str | None:
    """Return ``redact``, ``omit``, or ``None`` for one bounded exact string."""

    try:
        if any(header in value for header in _PEM_HEADERS):
            return "omit"
        if _has_credential_uri(value):
            return "omit"
        assignment = _credential_assignment_action(value)
        if assignment == "omit":
            return "omit"
        if _has_authorization_scheme(value):
            return "redact"
        if _has_compact_jwt(value):
            return "redact"
        if assignment == "redact":
            return "redact"
        if _has_bare_api_key(value):
            return "redact"
        return None
    except Exception:
        return "omit"


def _has_authorization_scheme(value: str) -> bool:
    lower = _ascii_lower(value)
    left_boundaries = set(" \t\r\n\"'=:;,( [{")
    stop = set(" \t\r\n\"'<>[]{}(),;")
    for scheme in ("bearer", "basic"):
        start = 0
        while True:
            index = lower.find(scheme, start)
            if index < 0:
                break
            left_ok = index == 0 or value[index - 1] in left_boundaries
            end = index + len(scheme)
            if left_ok and end < len(value) and value[end] in " \t":
                pos = end
                while pos < len(value) and value[pos] in " \t":
                    pos += 1
                if pos < len(value) and value[pos] not in stop:
                    return True
            start = index + 1
    return False


def _is_jwt_segment_char(char: str) -> bool:
    return (
        "A" <= char <= "Z" or "a" <= char <= "z" or "0" <= char <= "9" or char in "_-"
    )


def _has_compact_jwt(value: str) -> bool:
    index = 0
    size = len(value)
    while index < size:
        if not (_is_jwt_segment_char(value[index]) or value[index] == "."):
            index += 1
            continue
        start = index
        while index < size and (
            _is_jwt_segment_char(value[index]) or value[index] == "."
        ):
            index += 1
        run = value[start:index]
        if not run or run.startswith("."):
            continue

        core = run
        if core.endswith("."):
            core = core[:-1]
            if not core or core.endswith("."):
                continue
        parts = core.split(".")
        if len(parts) == 3 and all(
            part and all(_is_jwt_segment_char(char) for char in part) for part in parts
        ):
            return True
    return False


def _has_credential_uri(value: str) -> bool:
    for match in _URI_SCHEME.finditer(value):
        start = match.end()
        end = len(value)
        for delimiter in "/?#":
            pos = value.find(delimiter, start)
            if pos >= 0:
                end = min(end, pos)
        authority = value[start:end]
        at = authority.find("@")
        if at < 0:
            continue
        colon = authority.find(":", 0, at)
        if colon >= 0 and at - colon > 1:
            return True
    return False


def _credential_assignment_action(value: str) -> str | None:
    size = len(value)
    index = 0
    while index < size:
        quoted = value[index] in "\"'"
        quote = value[index] if quoted else ""
        label_start = index + 1 if quoted else index

        if not quoted and index > 0 and value[index - 1] in _LABEL_CHARS:
            index += 1
            continue

        pos = label_start
        while pos < size and value[pos] in _LABEL_CHARS:
            pos += 1
        label = value[label_start:pos]
        if not label:
            index += 1
            continue

        closing_pos = pos
        if quoted:
            if pos >= size or value[pos] != quote:
                if _is_credential_label(label):
                    return "omit"
                index += 1
                continue
            closing_pos = pos + 1

        credential_like = _is_credential_label(label)
        if len(label) > 64:
            if credential_like:
                return "omit"
            index = max(index + 1, pos)
            continue
        if not credential_like:
            index = max(index + 1, closing_pos)
            continue

        cursor = closing_pos
        spaces = 0
        while cursor < size and value[cursor] in " \t" and spaces < 17:
            cursor += 1
            spaces += 1
        if spaces > 16:
            return "omit"
        if cursor >= size or value[cursor] not in "=:":
            index = max(index + 1, closing_pos)
            continue
        cursor += 1
        spaces = 0
        while cursor < size and value[cursor] in " \t" and spaces < 17:
            cursor += 1
            spaces += 1
        if spaces > 16:
            return "omit"
        if cursor >= size:
            return None

        value_quote = value[cursor] if value[cursor] in "\"'" else ""
        if value_quote:
            cursor += 1
            if cursor >= size or value[cursor] == value_quote:
                return None
            if value.find(value_quote, cursor) < 0:
                return "omit"
        return "redact"
    return None


def _has_bare_api_key(value: str) -> bool:
    for index in range(len(value)):
        if index > 0 and value[index - 1] in _BARE_TOKEN_CHARS:
            continue
        for prefix in _BARE_KEY_PREFIXES:
            if not value.startswith(prefix, index):
                continue
            end = index
            while end < len(value) and value[end] in _BARE_TOKEN_CHARS:
                end += 1
            token_length = end - index
            if 20 <= token_length <= 512:
                return True
    return False


def _render_value(value: object) -> str:
    if type(value) is str:
        return value
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=False,
    )


def _check_post_redaction_tokens(value: object, max_field_chars: int) -> None:
    value_type = type(value)
    if value_type is str:
        if len(value) > max_field_chars:
            raise _OmitCandidate
        return
    if value_type in {bool, int, float} or value is None:
        token = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=False,
        )
        if len(token) > max_field_chars:
            raise _OmitCandidate
        return
    if value_type in {list, tuple}:
        for item in value:
            _check_post_redaction_tokens(item, max_field_chars)
        return
    if value_type is dict:
        for key, item in value.items():
            key_token = json.dumps(
                key,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=False,
            )
            if len(key_token) > max_field_chars:
                raise _OmitCandidate
            _check_post_redaction_tokens(item, max_field_chars)
        return
    raise _OmitCandidate


__all__ = [
    "CONTENT_CATEGORIES",
    "CONTENT_EVENT_NAME",
    "CaptureCandidate",
    "CaptureCandidateMeta",
    "ContentCaptureBuffer",
    "ContentCapturePolicy",
    "HARD_DENIED_PROVENANCE",
    "MAX_CAPTURE_CANDIDATES_PER_SPAN",
    "MAX_CAPTURE_DEPTH",
    "MAX_CAPTURE_NODES",
    "MAX_COLLECTION_ITEMS",
    "PROVENANCE_VALUES",
    "PreparedContentEvent",
    "ProvenanceNode",
    "REDACTED",
    "make_text_candidate",
    "prepare_content_event",
]
