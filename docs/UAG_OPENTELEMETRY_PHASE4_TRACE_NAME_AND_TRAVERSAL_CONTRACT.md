# OpenTelemetry Phase 4 Trace Name and Structured Traversal Contract

Status: Normative Phase 4 companion  
Parent scope: `docs/UAG_OPENTELEMETRY_PHASE4_SCOPE.md`  
Security contract: `docs/UAG_OPENTELEMETRY_PHASE4_SECURITY_CONTRACT.md`  
Applies to: Phase 4A content traversal and Phase 4D ordinary-user trace projection

This document closes two remaining implementation ambiguities from Phase 4 review. Where the parent scope or security contract uses the phrases `canonical/supported span name`, `cap recursion depth`, or `cap collection item counts`, the rules below are normative for the initial Phase 4 implementation.

## 1. Ordinary-user span names use a closed UAG-owned vocabulary

The `name` field in `uag.trace_view.v1` must never copy or sanitize an arbitrary backend, provider-SDK, model, tool, agent, URL, request, exception, or vendor span name.

The initial closed vocabulary is:

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
- a reviewed UAG-local diagnostic/internal span class that contains no user/provider-derived name component -> `INTERNAL`;
- any other authorized local span whose safe class cannot be proven -> `UNKNOWN`.

The projection must not derive the enum by parsing or pattern-matching the backend `span.name`. The local trace authorization/ownership metadata or other trusted UAG-local semantic record supplies the safe span class. Backend `span.name` is ignored for ordinary-user v1 output.

Unknown or malformed values always map to `UNKNOWN`. The implementation must never fall back to a bounded or sanitized backend name.

This means the ordinary-user v1 `name` field is effectively a safe span-class enum, not an exported OTel span-name string.

### Required regressions

Tests must prove that:

- `invoke_agent secret-user-name` projects only `AGENT`;
- `chat https://example.invalid/private?q=secret` projects only `LLM` when its trusted UAG-local class is LLM;
- `execute_tool tool-name-containing-user-data` projects only `TOOL`;
- a provider instrumentor name containing a URL, model name, request identifier, prompt fragment, or exception text projects only `PROVIDER_SDK` when the span is a trusted selected-call child;
- an arbitrary/unknown backend span name projects `UNKNOWN` or is omitted according to ownership policy, never copied;
- no model name, tool name, agent name, endpoint, URL, request ID, exception text, or vendor string is recoverable from `uag.trace_view.v1.name`.

## 2. Structured content traversal has fixed hard limits

Character ceilings alone are insufficient because provenance/redaction traversal occurs before final rendering. Initial Phase 4A therefore uses fixed traversal limits that are enforced while walking structured content.

The initial constants are:

```text
MAX_CAPTURE_DEPTH = 8
MAX_COLLECTION_ITEMS = 64
MAX_CAPTURE_NODES = 256
```

These are hard maxima and defaults for the initial implementation. They are not configurable through CLI, environment, browser input, tool payloads, provider payloads, baggage, or remote configuration in the initial Phase 4 release.

A future change may add configurability only through a separately reviewed configuration contract that preserves equal-or-lower safe maxima unless the privacy/security design is explicitly revised.

### 2.1 Depth definition

Depth is counted from the capture candidate root:

```text
root scalar/container = depth 0
child of root container = depth 1
...
```

No node deeper than depth 8 may be visited for capture purposes.

Before descending into a child that would exceed the depth limit, the entire capture candidate is rejected and omitted. The implementation must not partially serialize the prefix of an over-deep value.

### 2.2 Collection width definition

Each mapping, list, tuple, or other explicitly reviewed finite structured container may contain at most 64 immediate children for capture traversal.

If a container contains more than 64 entries/elements, the entire capture candidate is rejected and omitted. The implementation must not capture only the first 64 items because doing so can produce misleading or security-sensitive partial structures.

Opaque/custom iterators, generators, file-like objects, streaming values, and unreviewed container types are not traversed. They fail closed to omission rather than being consumed to discover their size.

### 2.3 Total node budget

At most 256 nodes, including the root, may be examined for one capture candidate.

The node counter increments before provenance inspection, redaction, string conversion, or child traversal for each visited scalar/container node.

If visiting the next node would exceed 256, the entire capture candidate is rejected and omitted.

The total-node budget is independent of the per-container 64-item limit and depth-8 limit; all limits must pass.

### 2.4 Enforcement order

Resource bounds are checked during traversal, before unbounded normalization or serialization:

```text
candidate
  -> supported finite structure?
     -> no: omit
  -> node budget available?
     -> no: omit whole candidate
  -> depth within limit?
     -> no: omit whole candidate
  -> collection width within limit?
     -> no: omit whole candidate
  -> trusted field/node provenance gate
  -> category eligibility
  -> value-level secret redaction
  -> existing per-field/per-span character budgets
  -> export
```

No overflow condition may truncate into an apparently valid partial content value. Overflow omits the whole content candidate and leaves normal Agent/model/tool execution unaffected.

### 2.5 Existing character budgets remain cumulative

These traversal limits are additional to the existing content character limits:

```text
MAX_FIELD_CHARS default 2048, valid 64..16384
MAX_SPAN_CHARS  default 8192, valid 256..65536
MAX_SPAN_CHARS >= MAX_FIELD_CHARS
```

Passing traversal limits does not bypass character limits, provenance restrictions, category selection, or redaction.

### Required regressions

Tests must include:

- depth exactly 8 succeeds when every other gate succeeds;
- depth 9 omits the whole candidate;
- a collection with exactly 64 children succeeds subject to other gates;
- a collection with 65 children omits the whole candidate;
- exactly 256 visited nodes succeeds subject to other gates;
- the 257th node causes whole-candidate omission;
- a wide/deep value cannot trigger unbounded provenance or redaction traversal;
- a generator/custom iterator/file-like object is not consumed and is omitted;
- overflow produces only a normalized, content-free diagnostic and never logs the rejected value;
- traversal overflow never affects normal Agent/model/tool execution.

## 3. Fixed Phase 4 decisions from this companion

- Ordinary-user `uag.trace_view.v1.name` is a closed UAG-owned enum, not a copied/sanitized backend span name.
- Backend/provider span names are ignored for ordinary-user v1 projection.
- Unknown span classes map to `UNKNOWN` rather than arbitrary text.
- Structured content traversal is bounded by depth 8, 64 immediate children per collection, and 256 visited nodes per candidate.
- Traversal limits are fixed and non-configurable in the initial Phase 4 implementation.
- Exceeding any traversal limit omits the whole capture candidate; partial prefix capture is forbidden.
- Unreviewed/streaming/opaque iterables are not consumed for telemetry.
