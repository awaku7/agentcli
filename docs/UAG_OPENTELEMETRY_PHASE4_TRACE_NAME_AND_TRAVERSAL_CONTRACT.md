# OpenTelemetry Phase 4 Trace Name and Structured Traversal Contract

Status: Normative Phase 4 companion  
Parent scope: `docs/UAG_OPENTELEMETRY_PHASE4_SCOPE.md`  
Security contract: `docs/UAG_OPENTELEMETRY_PHASE4_SECURITY_CONTRACT.md`  
Scalar/timing contract: `docs/UAG_OPENTELEMETRY_PHASE4_SCALAR_AND_TIMING_CONTRACT.md`  
Applies to: Phase 4A content ownership/traversal/rendering and Phase 4D safe span-name projection

This document is the sole normative owner for safe span-name projection, the initial controlled-content carrier and canonical-span ownership, content candidate admission, structured traversal, redaction marker behavior, canonical rendering, and cumulative per-span content accounting.

## 1. Ordinary-user span names use a closed vocabulary

`uag.trace_view.v1.name` never copies/sanitizes arbitrary backend/provider/model/tool/agent/URL/request/exception/vendor span names.

The initial vocabulary is exactly:

```text
AGENT
LLM
TOOL
PROVIDER_SDK
INTERNAL
UNKNOWN
```

Trusted local semantic ownership maps as follows:

- canonical `invoke_agent ...` -> `AGENT`;
- canonical `chat ...` -> `LLM`;
- canonical `execute_tool ...` -> `TOOL`;
- locally owned selected-call provider diagnostic child -> `PROVIDER_SDK`;
- reviewed UAG-local internal diagnostic class with no user/provider-derived name component -> `INTERNAL`;
- other authorized local span without provable safe class -> `UNKNOWN`.

Do not derive the enum by parsing backend `span.name`. Unknown/malformed local class -> `UNKNOWN`; there is no backend-name fallback.

## 2. Initial controlled-content carrier and owner spans are closed

Initial Phase 4A controlled content is emitted only as this UAG-owned span event:

```text
event name: uag.content
attributes:
  uag.content.category
  uag.content.value
  uag.content.ordinal
```

No other attribute is permitted on this event initially.

Category vocabulary and canonical owner span are exactly:

```text
user_input       -> local canonical invoke_agent span
assistant_output -> local canonical invoke_agent span
tool_arguments   -> the matching local canonical execute_tool span
tool_result      -> the matching local canonical execute_tool span
```

Initial rules:

- `chat` spans do not carry `uag.content` events;
- provider-SDK child spans do not carry `uag.content` events;
- internal spans do not carry `uag.content` events;
- user/tool/provider payload data cannot choose the owner span, event name, attribute names, category, or ordinal;
- `uag.content.ordinal` is a trusted positive integer creation ordinal local to the owner span;
- `uag.content.value` is the only content-bearing field and is the exact canonical rendered string from this contract;
- ordinary-user `uag.trace_view.v1` never exposes events.

Provider/model-native prompt/response capture is therefore not a second content path. Initial content capture is only the UAG-owned Agent-turn/tool-operation surface above.

## 3. Fixed traversal and candidate limits

Initial constants are exactly:

```text
MAX_CAPTURE_DEPTH = 8
MAX_COLLECTION_ITEMS = 64
MAX_CAPTURE_NODES = 256
MAX_CAPTURE_CANDIDATES_PER_SPAN = 32
```

They are non-configurable in the initial release.

### 3.1 Candidate admission and root gates

An owner canonical span records at most 32 candidate records. The 33rd/later candidate is omitted before inspecting its value.

For each admitted candidate, trusted metadata gates execute before value work:

```text
root provenance forbidden? -> omit
master gate OFF? -> omit
category not selected? -> omit
source/category not allowed? -> omit
wrong canonical owner/carrier? -> omit
otherwise -> bounded value traversal
```

No container enumeration, secret scan, normalization, conversion, serialization, or custom hook runs before these gates pass.

### 3.2 Supported initial runtime shapes are exact

Only exact built-in forms are accepted:

```text
containers: dict, list, tuple
scalars:    str, int, float, bool, None
mapping keys: exact built-in str only
```

Subclasses and protocol-compatible custom values are not accepted.

Reject without traversal/coercion:

- dict/list/tuple subclasses;
- custom Mapping/Sequence/iterator/generator/stream/file-like objects;
- bytes/bytearray/memoryview/body wrappers;
- numeric/boolean/null/custom mapping keys;
- arbitrary conversion hooks.

Numeric scalar rules are further restricted by the scalar/timing contract.

### 3.3 Depth and width

Depth:

```text
root = 0
child = parent + 1
maximum visited depth = 8
```

Attempting to descend to depth 9 omits the whole candidate.

Width:

- list/tuple: maximum 64 immediate elements;
- dict: maximum 64 key/value pairs.

A 65th immediate element/pair omits the whole candidate. Never keep a prefix only.

### 3.4 Total node accounting

At most 256 node occurrences including root may be examined.

Accounting is occurrence-based:

- root = 1;
- every list/tuple element occurrence = 1;
- every dict key occurrence = 1;
- every dict value occurrence = 1;
- aliases count again on every occurrence;
- object identity never reduces the count.

Traversal order:

- list/tuple index order;
- dict built-in insertion order;
- dict entry key first, then value.

Maintain an active-ancestor container identity set. Encountering an active ancestor is a cycle -> omit whole candidate. A completed container referenced later is an alias and is traversed/counted again.

The node counter increments before secret scan, normalization, rendering, or child descent. The 257th occurrence omits the whole candidate.

### 3.5 Child order

For each child occurrence:

1. node/depth admission;
2. trusted child provenance gate;
3. exact supported type/shape gate;
4. width/cycle gate if container;
5. native scalar preflight if scalar;
6. recurse or proceed to bounded secret handling.

Forbidden/security-opaque child provenance is handled without scanning its body.

## 4. Scalar preflight precedes secret scanning

For exact built-in strings:

- native length must be `<= effective MAX_FIELD_CHARS` before scanning;
- oversize string -> omit whole candidate, no truncation/scan;
- any surrogate `U+D800..U+DFFF` -> omit;
- no Unicode normalization/case folding;
- no UTF-8 encoding, JSON rendering, regex/classifier work, or generic conversion before native bound succeeds.

Mapping keys pass the same bounded-string preflight.

Int/float/bool/null rules are owned by the scalar/timing contract.

## 5. Secret handling is deterministic

The initial replacement marker for a high-confidence secret in an eligible scalar **value** is exactly:

```text
[REDACTED]
```

It is not configurable.

Rules:

- eligible scalar values may replace high-confidence secret matches with exactly `[REDACTED]`;
- a mapping key matching a high-confidence credential/secret pattern causes whole-candidate omission rather than key rewriting;
- secret-wrapper/security ambiguity/redactor exception causes whole-candidate omission;
- rejected raw values are never logged;
- after redaction, every scalar must still satisfy the effective field bound in its final scalar representation; otherwise omit whole candidate.

## 6. Canonical renderer is exact

A candidate is rendered to one final string. That exact string is both counted and exported as `uag.content.value`.

### 6.1 Direct string

Direct string candidate -> exact post-redaction string, no added quotes and no Unicode normalization.

### 6.2 Non-string primitive and structured value

Render as compact JSON text with semantics equivalent to:

```python
json.dumps(
    value,
    ensure_ascii=False,
    allow_nan=False,
    separators=(",", ":"),
    sort_keys=False,
)
```

Normative restrictions:

- no `default=` hook;
- tuple renders as JSON array;
- dict keys are exact built-in strings;
- dict order remains built-in insertion order;
- admitted ints are signed-64-bit only;
- admitted floats are exact built-in finite binary64 only;
- non-ASCII characters remain literal;
- JSON quotes/backslash/C0-control escaping is standard;
- surrogate-containing strings have already failed;
- no trailing newline/insignificant whitespace.

Supported Python 3.11/3.13/3.14 must produce identical output for the reviewed float/escaping conformance corpus. If not, introduce an explicit stable renderer before enabling capture.

### 6.3 Character definition

Character budgets count Unicode code points in the exact final UAG string (`len(rendered_text)`), not UTF-8 bytes.

For structured JSON, escape characters present in final text count individually. The counting and export path must use the exact same rendered string; estimate-only alternate serializers are forbidden.

## 7. Field and span budgets

Configuration validation is owned by the security contract:

```text
MAX_FIELD_CHARS default 2048, valid 64..16384
MAX_SPAN_CHARS  default 8192, valid 256..65536
MAX_SPAN_CHARS >= MAX_FIELD_CHARS
```

### 7.1 Field bound

Every scalar passes both:

1. native preflight before secret handling; and
2. post-redaction final-scalar bound before candidate rendering.

No field is truncated to fit.

### 7.2 One shared per-span ledger

Each canonical owner span has one content ledger starting at zero.

A candidate is fully bounded/redacted/rendered without mutating the ledger. Cost is exactly:

```text
candidate_cost = len(final uag.content.value)
```

Only `uag.content.value` counts. Fixed event/category/ordinal metadata does not.

Candidate processing order is:

```text
user_input
assistant_output
tool_arguments
tool_result
```

Within a category, trusted creation ordinal ascending.

For each candidate:

```text
remaining = MAX_SPAN_CHARS - used

if candidate_cost <= remaining:
    emit whole uag.content event
    used += candidate_cost
else:
    omit whole candidate
    used unchanged
```

No partial candidate is emitted. A later smaller candidate may still fit after an oversized candidate is omitted. Normal metadata attributes do not consume this controlled-content ledger.

## 8. Combined normative execution order

```text
candidate record created
  -> candidate-count admission
  -> root forbidden-provenance
  -> master gate
  -> category gate
  -> source/category gate
  -> exact canonical owner/uag.content carrier gate
  -> exact supported type/shape
  -> node/depth/width/cycle checks
  -> primitive scalar preflight
  -> bounded child traversal with child provenance
  -> bounded secret handling
  -> post-redaction scalar field bound
  -> exact canonical rendering
  -> shared per-span ledger
  -> emit whole event or omit whole candidate
```

No content secret scan occurs before the structural/scalar work required to prove the scan is bounded.

## 9. Required regressions

Tests must prove at least:

- backend/provider arbitrary span names never reach ordinary-user v1 `name`;
- category-owner mapping is exact: user/assistant only on `invoke_agent`, tool args/result only on matching `execute_tool`;
- no `uag.content` on `chat`, provider-SDK, internal, or remote spans;
- 33rd candidate omitted before value traversal;
- exact built-in shapes accepted subject to gates; subclasses/custom protocols fail closed;
- mapping keys string-only with no coercion;
- depth 8 passes, depth 9 fails;
- width 64 passes, 65 fails;
- node 256 passes, 257 fails;
- aliases count per occurrence; active cycles fail;
- oversized/surrogate strings fail before secret/render work;
- secret-bearing mapping key fails whole candidate;
- exact marker is `[REDACTED]`;
- direct string output is unquoted post-redaction text;
- structured output uses exact compact JSON semantics above;
- control/quote/backslash/non-ASCII/numeric/boolean/null/list/tuple/dict renderings are fixed across supported Python versions;
- candidate cost equals exact exported `uag.content.value` length;
- candidates share one span ledger;
- exact remaining-budget candidate passes; +1 character fails whole candidate without ledger mutation;
- later smaller candidate can fit;
- failures never log rejected content or alter runtime execution.

## 10. Fixed Phase 4 decisions

- V1 `name` is a closed UAG-owned enum.
- Initial content carrier, category names, and canonical owner spans are closed.
- Candidate count is capped at 32 per owner span.
- Containers are exact built-in dict/list/tuple and mapping keys are exact built-in strings only.
- Traversal limits are depth 8, width 64, and 256 visited node occurrences per candidate.
- Structural/scalar bounds precede secret scanning.
- Exact redaction marker is `[REDACTED]`; secret-bearing mapping keys fail closed.
- Canonical rendering is exact and shared by accounting/export.
- `MAX_SPAN_CHARS` is one cumulative per-owner-span ledger with atomic whole-candidate emission.