# OpenTelemetry Phase 4 Trace Name and Structured Traversal Contract

Status: Normative Phase 4 companion  
Parent scope: `docs/UAG_OPENTELEMETRY_PHASE4_SCOPE.md`  
Security contract: `docs/UAG_OPENTELEMETRY_PHASE4_SECURITY_CONTRACT.md`  
Scalar/timing contract: `docs/UAG_OPENTELEMETRY_PHASE4_SCALAR_AND_TIMING_CONTRACT.md`  
Applies to: Phase 4A content traversal/rendering and Phase 4D ordinary-user trace-name projection

This document is the sole normative owner for the initial Phase 4 rules covering safe span-name projection, controlled-content structure traversal, content candidate admission, canonical content rendering, and cumulative per-span content accounting. Parent or sibling documents may summarize these rules but must not define a conflicting order, limit, renderer, or vocabulary.

## 1. Ordinary-user span names use a closed UAG-owned vocabulary

The `name` field in `uag.trace_view.v1` must never copy or sanitize an arbitrary backend, provider-SDK, model, tool, agent, URL, request, exception, or vendor span name.

The initial closed vocabulary is exactly:

```text
AGENT
LLM
TOOL
PROVIDER_SDK
INTERNAL
UNKNOWN
```

Mapping is performed only from trusted UAG-local semantic ownership established before backend export/query projection:

- UAG canonical `invoke_agent ...` logical operation -> `AGENT`;
- UAG canonical `chat ...` logical operation -> `LLM`;
- UAG canonical `execute_tool ...` logical operation -> `TOOL`;
- a locally owned, selected-call-scoped provider instrumentation child that passed the Phase 4C guard -> `PROVIDER_SDK`;
- a reviewed UAG-local diagnostic/internal span class with no user/provider-derived name component -> `INTERNAL`;
- any other authorized local span whose safe class cannot be proven -> `UNKNOWN`.

The projection must not derive the enum by parsing or pattern-matching backend `span.name`. Trusted local span-ownership metadata supplies the safe class. Backend span-name text is ignored for ordinary-user v1.

Unknown or malformed local class values map to `UNKNOWN`; there is no bounded/sanitized backend-name fallback.

### Required regressions

Tests must prove that:

- `invoke_agent secret-user-name` projects only `AGENT`;
- `chat https://example.invalid/private?q=secret` projects only `LLM` when the trusted local class is LLM;
- `execute_tool tool-name-containing-user-data` projects only `TOOL`;
- provider instrumentor names containing URLs, model names, request IDs, prompt fragments, or exception text project only `PROVIDER_SDK` when the span is a trusted selected-call child;
- arbitrary/unknown backend names project `UNKNOWN` or are omitted by ownership policy, never copied;
- no model/tool/agent/endpoint/request/vendor text is recoverable from v1 `name`.

## 2. Initial controlled-content carrier is closed

Initial Phase 4A controlled content is emitted only through a UAG-owned span event:

```text
event name: uag.content
attributes:
  uag.content.category  # closed semantic category
  uag.content.value     # final canonical rendered content string
  uag.content.ordinal   # trusted positive integer creation ordinal
```

No other event attributes are permitted on `uag.content` in the initial release.

The category vocabulary is exactly:

```text
user_input
assistant_output
tool_arguments
tool_result
```

Rules:

- `uag.content.category` is selected by trusted UAG code, never copied from payload data;
- `uag.content.ordinal` is assigned by trusted UAG-local instrumentation when the candidate is created;
- `uag.content.value` is the only content-bearing field and contains the exact final representation defined in this contract;
- content is never exported by inventing arbitrary attribute/event keys from user/tool/provider data;
- provider SDK child spans never emit `uag.content` directly in the initial Phase 4 release; SDK-native prompt/response capture remains disabled and UAG-owned canonical spans remain the only content-capture surface;
- ordinary-user `uag.trace_view.v1` does not expose events, so `uag.content` never appears in that response schema.

The normal generic metadata sanitizer must not gain a broad `capture_content=True` bypass. Controlled content reaches the `uag.content` carrier only after every gate in this contract succeeds.

## 3. Structured content traversal has fixed hard limits

The initial constants are exactly:

```text
MAX_CAPTURE_DEPTH = 8
MAX_COLLECTION_ITEMS = 64
MAX_CAPTURE_NODES = 256
MAX_CAPTURE_CANDIDATES_PER_SPAN = 32
```

These are fixed hard maxima in the initial release and are not configurable through CLI, environment, browser/tool/provider payloads, baggage, A2A/MCP input, or remote configuration.

A future change may add configurability only through a separately reviewed contract with equal-or-lower safe maxima unless the privacy/security design is explicitly revised.

### 3.1 Candidate admission and root gates

A canonical span may record at most 32 controlled-content candidate records. Candidate ordinal is assigned at creation and is monotonically increasing within that span. A 33rd or later candidate is dropped before inspecting/traversing its value and emits only a normalized content-free diagnostic.

For an admitted candidate, evaluate these root gates using trusted UAG-local metadata before any value traversal:

```text
trusted root provenance forbidden?
  -> yes: omit without traversing the value
content master gate enabled?
  -> no: omit without traversing the value
semantic category explicitly allowed?
  -> no: omit without traversing the value
root source/category combination allowed?
  -> no: omit without traversing the value
carrier/owner is the approved UAG canonical span/event surface?
  -> no: omit without traversing the value
otherwise
  -> begin bounded traversal
```

No container enumeration, scalar normalization, secret scanning, string conversion, serialization, or provider/custom hook runs before those root gates pass.

### 3.2 Initial supported runtime shapes are closed

The initial traversal accepts only exact built-in forms, not subclasses or protocol-compatible custom objects:

```text
containers: dict, list, tuple
scalars:    str, int, float, bool, None
```

`bool` is treated as boolean rather than integer. Numeric rules are further restricted by the scalar/timing contract.

Initial mapping keys must be exact built-in `str` values. Numeric, boolean, null, bytes, tuple, custom, symbolic, or other mapping-key types cause whole-candidate omission. This avoids implementation-specific key coercion and custom conversion hooks.

`dict` subclasses, list/tuple subclasses, custom `Mapping`/`Sequence` objects, generators, iterators, streams, file-like objects, byte arrays/buffers, body-wrapper objects, and other unreviewed shapes are not traversed or consumed for telemetry.

### 3.3 Depth definition

Depth is counted from the capture-candidate root:

```text
root scalar/container = depth 0
child of root         = depth 1
...
```

No node deeper than depth 8 may be visited. Before descending to depth 9, omit the entire candidate. Never export a partial structural prefix.

### 3.4 Collection width definition

Each accepted `dict`, `list`, or `tuple` may contain at most 64 immediate logical children:

- list/tuple: one element = one logical child;
- dict: one key/value pair = one logical child for the width limit.

A container with 65 or more entries/elements causes whole-candidate omission. Do not consume an opaque iterator to discover size and do not keep only the first 64 items.

### 3.5 Total-node budget and deterministic accounting

At most 256 node occurrences, including the root, may be examined for one candidate.

Accounting is occurrence-based:

- root counts as one;
- each list/tuple element occurrence counts as one;
- each dict key occurrence counts as one;
- each dict value occurrence counts as one;
- a dict with `N` scalar pairs therefore consumes `1 + 2N` occurrences before descendants;
- repeated aliases count again at every occurrence;
- object identity never reduces the budget.

Traversal order is deterministic:

- list/tuple: index order;
- dict: built-in insertion order;
- each dict entry: key occurrence first, then value occurrence.

The walker maintains an active-ancestor identity set for containers. Encountering a container already on the active ancestor path is a cycle and causes whole-candidate omission. A completed container referenced again later is an alias, not a cycle, and is traversed/counts again.

The node counter increments before secret scanning, normalization, rendering, or child descent. The 257th occurrence causes whole-candidate omission.

### 3.6 Child provenance is checked before child value work

For an eligible container, each child occurrence is handled in this order:

1. node/depth admission;
2. trusted child provenance gate;
3. exact supported type/shape check;
4. width/cycle check if a container;
5. native scalar preflight if a scalar;
6. recurse or continue to bounded redaction.

Forbidden or security-opaque child provenance is handled according to the parent/security provenance contract without scanning the child body.

## 4. Scalar preflight happens before redaction

Secret scanning is allowed only on already-bounded scalar values.

For strings:

- exact built-in `str` only;
- native character length must be `<= effective MAX_FIELD_CHARS` before scanning;
- strings above that limit omit the whole candidate without redaction or truncation;
- a string containing any Unicode surrogate code point `U+D800..U+DFFF` is rejected before rendering/export;
- no Unicode normalization or case folding is applied to content;
- no UTF-8 re-encoding, regex/classifier scan, JSON rendering, or generic `str()` conversion occurs before the native-length preflight.

Numeric/boolean/null preflight is owned by `UAG_OPENTELEMETRY_PHASE4_SCALAR_AND_TIMING_CONTRACT.md`.

Mapping keys pass the same bounded-string preflight before secret classification.

## 5. Redaction semantics are deterministic

The initial replacement marker for a high-confidence secret in an eligible scalar **value** is exactly:

```text
[REDACTED]
```

It is not configurable.

Rules:

- value-level matches may replace the sensitive matched value/text with exactly `[REDACTED]` according to the reviewed redactor;
- a mapping key that itself matches a high-confidence secret/credential pattern causes whole-candidate omission rather than key rewriting, preventing post-redaction key collisions or ambiguous maps;
- a redactor exception, security ambiguity, or secret-wrapper value that cannot be safely reduced causes whole-candidate omission;
- rejected raw values are never logged;
- after redaction, every scalar is rechecked against the effective field bound using the exact final scalar representation; if redaction/escaping would exceed the field limit, omit the whole candidate.

## 6. Canonical content renderer is exact

All accepted candidates are rendered to one final string before the span ledger decision. That exact string is both counted and exported as `uag.content.value`.

### 6.1 Direct string candidate

A direct string candidate renders as its exact post-redaction string, with no added quote characters and no Unicode normalization.

### 6.2 Non-string primitive and structured candidate

A non-string primitive or structured candidate renders as compact JSON text with semantics equivalent to Python standard-library:

```python
json.dumps(
    value,
    ensure_ascii=False,
    allow_nan=False,
    separators=(",", ":"),
    sort_keys=False,
)
```

with these additional normative restrictions:

- no `default=` conversion hook is permitted;
- tuple renders as a JSON array;
- dict keys are exact built-in strings only;
- dict order is the original built-in insertion order; keys are not re-sorted;
- accepted integers are signed-64-bit only;
- accepted floats are finite reviewed built-in binary64 values only;
- `NaN` and infinities are impossible at this stage;
- non-ASCII characters remain literal because `ensure_ascii=False`;
- JSON quoting/backslash/C0-control escaping follows the standard JSON encoder;
- surrogate-containing strings have already failed preflight;
- no trailing newline or insignificant whitespace is emitted.

For supported Python 3.11/3.13/3.14, conformance tests must prove identical output for the reviewed scalar/escaping corpus. If a future runtime would render an admitted float differently, UAG must introduce an explicit stable float renderer rather than silently changing budget/export bytes.

### 6.3 Character definition

`MAX_FIELD_CHARS` and `MAX_SPAN_CHARS` count Unicode code points in the final Python/UAG string representation, i.e. the result of `len(rendered_text)`, not UTF-8 bytes.

For structured JSON, escape characters that appear in the final string count individually. Example: a newline inside a nested JSON string is rendered as two characters `\` and `n`, and both count.

The exact same rendered string is used for accounting and export; separate estimate and export serializers are forbidden.

## 7. Per-field and cumulative per-span budgets

The configured limits remain:

```text
MAX_FIELD_CHARS default 2048, valid 64..16384
MAX_SPAN_CHARS  default 8192, valid 256..65536
MAX_SPAN_CHARS >= MAX_FIELD_CHARS
```

The security contract owns configuration validation. This contract owns runtime accounting.

### 7.1 Field budget

Every scalar must satisfy the native preflight before redaction and the post-redaction final-scalar bound before candidate rendering. A field is never truncated to fit.

### 7.2 Shared span ledger

`MAX_SPAN_CHARS` is one shared UAG-owned ledger per canonical span. It is not reset per event, category, candidate, argument, result, or message.

The ledger starts at zero. A candidate is fully bounded, redacted, and canonically rendered without mutating the ledger. Candidate cost is:

```text
candidate_cost = len(final_uag.content.value)
```

Only `uag.content.value` counts toward the content ledger. Fixed event name and safe carrier metadata (`uag.content.category`, `uag.content.ordinal`) do not count.

Candidate processing order is deterministic:

```text
user_input
assistant_output
tool_arguments
tool_result
```

Within one category, process candidates by trusted creation ordinal ascending.

For each candidate:

```text
remaining = MAX_SPAN_CHARS - span_content_chars_used

if candidate_cost <= remaining:
    emit whole uag.content event
    span_content_chars_used += candidate_cost
else:
    omit whole candidate
    ledger unchanged
```

Rules:

- no partial/truncated content event is emitted;
- a candidate that fails to fit consumes zero ledger characters;
- earlier accepted candidates remain accepted;
- later smaller candidates may still fit after an oversized candidate is omitted;
- metadata-only Phase 1-3 attributes do not consume this controlled-content ledger;
- ledger state is telemetry-only and never affects Agent/model/tool behavior.

## 8. Combined normative execution order

The exact initial execution order is:

```text
trusted candidate record created
  -> per-span candidate-count admission (<= 32)
  -> root forbidden-provenance gate
  -> content master gate
  -> semantic-category gate
  -> root source/category gate
  -> approved canonical-span/uag.content carrier gate
  -> exact supported root shape/type gate
  -> root node/depth admission
  -> root width/cycle check if container
  -> native scalar preflight if scalar
  -> bounded deterministic traversal
       -> child node/depth admission
       -> child provenance gate
       -> exact child type/shape gate
       -> child width/cycle check if container
       -> child scalar preflight if scalar
  -> value/key secret handling
  -> post-redaction scalar field bound
  -> exact canonical rendering
  -> shared per-span ledger check
  -> emit whole uag.content event or omit whole candidate
```

No secret redaction/classification of content values occurs before the structural/scalar work needed to prove that scanning is bounded.

## 9. Required regressions

Tests must include at least:

- forbidden provenance, master OFF, and unselected category reject roots without traversing values;
- the 33rd candidate on one canonical span is omitted before value traversal;
- exact built-in container/scalar types are accepted subject to all gates while subclasses/custom protocols fail closed;
- dict keys must be exact built-in strings; numeric/custom keys omit the candidate without conversion;
- depth exactly 8 succeeds; depth 9 omits whole candidate;
- 64-item container succeeds; 65-item container omits whole candidate;
- a 64-pair dict is width-valid and node-counts root + 64 keys + 64 values before descendants;
- repeated aliases count per occurrence; active-path cycles omit whole candidate;
- exactly 256 occurrences succeeds; the 257th omits whole candidate;
- oversized strings are omitted before secret scanning;
- string exactly at `MAX_FIELD_CHARS` may proceed;
- surrogate-containing strings fail before rendering;
- secret-bearing mapping keys omit whole candidate;
- the replacement marker is exactly `[REDACTED]`;
- direct string output is unquoted post-redaction text;
- structured output uses compact JSON with `ensure_ascii=False`, no spaces/newlines, insertion-order dict keys, and no custom conversion hooks;
- quotes, backslashes, control characters, non-ASCII text, integers, finite floats, booleans, nulls, lists, tuples, and dicts have fixed expected renderings across supported Python versions;
- accounting uses the exact exported `uag.content.value` string;
- multiple candidates share one cumulative span ledger;
- a candidate exactly filling the remaining span budget is emitted;
- a candidate exceeding remaining budget by one character is omitted whole without ledger mutation;
- later smaller candidate can still fit;
- provider SDK child spans emit no `uag.content` event;
- no overflow/redaction failure logs rejected content or changes runtime behavior.

## 10. Fixed Phase 4 decisions from this companion

- Ordinary-user `uag.trace_view.v1.name` is a closed UAG-owned enum.
- Initial content uses only the closed `uag.content` event schema.
- Controlled-content candidate count is capped at 32 per canonical span.
- Initial accepted containers are exact built-in `dict`, `list`, and `tuple`; initial dict keys are exact built-in strings only.
- Traversal is bounded by depth 8, width 64, and 256 visited node occurrences per candidate.
- Structural/scalar bounds are proved before value-level secret scanning.
- The exact redaction marker is `[REDACTED]`; secret-bearing mapping keys fail closed.
- Canonical content rendering is explicitly defined and the exact rendered string is used for both counting and export.
- `MAX_SPAN_CHARS` is one cumulative per-span ledger; candidates are emitted or omitted atomically in deterministic order.
- Opaque/streaming/custom iterables and conversion hooks are never consumed for telemetry.