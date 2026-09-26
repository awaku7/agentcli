# OpenTelemetry Phase 4 Trace Name and Structured Traversal Contract

Status: Normative Phase 4 companion  
Parent scope: `docs/UAG_OPENTELEMETRY_PHASE4_SCOPE.md`  
Security contract: `docs/UAG_OPENTELEMETRY_PHASE4_SECURITY_CONTRACT.md`  
Applies to: Phase 4A content traversal and Phase 4D ordinary-user trace projection

This document closes remaining implementation ambiguities from Phase 4 review. Where the parent scope or security contract uses the phrases `canonical/supported span name`, `cap recursion depth`, `cap collection item counts`, or `cap total captured characters per span`, the rules below are normative for the initial Phase 4 implementation.

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

Character ceilings alone are insufficient because provenance/redaction traversal can otherwise do substantial work before final rendering. Initial Phase 4A therefore uses fixed traversal limits that are enforced while walking structured content.

The initial constants are:

```text
MAX_CAPTURE_DEPTH = 8
MAX_COLLECTION_ITEMS = 64
MAX_CAPTURE_NODES = 256
```

These are hard maxima and defaults for the initial implementation. They are not configurable through CLI, environment, browser input, tool payloads, provider payloads, baggage, or remote configuration in the initial Phase 4 release.

A future change may add configurability only through a separately reviewed configuration contract that preserves equal-or-lower safe maxima unless the privacy/security design is explicitly revised.

### 2.1 Root eligibility remains provenance-first

The parent Phase 4 eligibility order remains normative. The implementation must reject obviously ineligible roots before structural traversal.

For each capture candidate, evaluate these root gates first using trusted UAG-local metadata only:

```text
root trusted provenance is forbidden?
  -> yes: omit without traversing the value
content master gate enabled?
  -> no: omit without traversing the value
semantic category explicitly allowed?
  -> no: omit without traversing the value
root source/category combination allowed?
  -> no: omit without traversing the value
otherwise
  -> begin bounded structural traversal
```

No container enumeration, scalar normalization, secret scanning, string conversion, or serialization occurs before those root gates pass.

For eligible structured roots, the traversal limits below are then enforced incrementally before descending into each child. Trusted child provenance is checked before any child value normalization or redaction. A forbidden or security-opaque child is handled according to the parent provenance contract without scanning its body.

### 2.2 Depth definition

Depth is counted from the capture candidate root:

```text
root scalar/container = depth 0
child of root container = depth 1
...
```

No node deeper than depth 8 may be visited for capture purposes.

Before descending into a child that would exceed the depth limit, the entire capture candidate is rejected and omitted. The implementation must not partially serialize the prefix of an over-deep value.

### 2.3 Collection width definition

Each mapping, list, tuple, or other explicitly reviewed finite structured container may contain at most 64 immediate logical children.

For sequences, one element is one logical child. For mappings, one key/value pair is one logical child for the 64-item width limit, even though key and value occurrences are counted separately for the total-node budget defined below.

If a container contains more than 64 entries/elements, the entire capture candidate is rejected and omitted. The implementation must not capture only the first 64 items because doing so can produce misleading or security-sensitive partial structures.

Opaque/custom iterators, generators, file-like objects, streaming values, and unreviewed container types are not traversed. They fail closed to omission rather than being consumed to discover their size.

### 2.4 Total node budget and deterministic accounting

At most 256 node occurrences, including the root, may be examined for one capture candidate.

Node accounting is occurrence-based, not object-identity-based:

- the root scalar/container counts as one node;
- each sequence element occurrence counts as one node when visited;
- each mapping key occurrence counts as one node;
- each mapping value occurrence counts as one node;
- therefore a mapping with `N` scalar key/value pairs consumes `1 + 2N` node occurrences for that mapping and its direct children, before descendants of container values are counted;
- if the same Python/runtime object is referenced in multiple positions, every occurrence counts again;
- aliases are never deduplicated for budget purposes.

Traversal order for conformance tests is deterministic:

- sequences are visited in index order;
- mappings are visited in their stable runtime iteration/insertion order;
- for each mapping entry, visit the key occurrence first, then the value occurrence;
- only reviewed bounded scalar key types are accepted; opaque/custom key objects cause whole-candidate omission rather than arbitrary conversion.

Cycle handling is separate from alias accounting. The walker maintains an active-ancestor identity set for traversed containers. Encountering a container that is already on the active ancestor path is a cycle and causes whole-candidate omission. A previously completed container referenced again later is not a cycle, but its new occurrence is counted and traversed again subject to all limits.

The node counter increments before any value-level secret scan, string conversion, normalization, or child descent for that occurrence. If visiting the next occurrence would exceed 256, the entire capture candidate is rejected and omitted.

The total-node budget is independent of the per-container 64-item limit and depth-8 limit; all limits must pass.

### 2.5 Raw scalar preflight before redaction

Secret scanning itself must be bounded. An eligible scalar is therefore size-checked before invoking the value-level redactor.

For initial Phase 4A:

- strings are accepted for redaction only when their native character length is less than or equal to the effective `MAX_FIELD_CHARS` value;
- because `MAX_FIELD_CHARS` is itself bounded to at most 16384, the redactor never scans an arbitrarily large string;
- strings above the effective field limit cause whole-candidate omission; they are not truncated before scanning;
- byte arrays, byte buffers, file-like values, data URLs classified as body content, and other opaque binary/body scalars remain excluded by provenance/type policy and are not decoded or scanned as text;
- primitive numeric/boolean/null scalars have bounded representation and may proceed only after normal provenance/category gates and the scalar/numeric preflight contract;
- mapping keys are subject to the same bounded-scalar preflight before any normalization or secret scanning.

The implementation must use a size operation that does not require copying, decoding, regex-scanning, or rendering the whole scalar. No generic `str(value)`, JSON serialization, UTF-8 re-encoding of an oversized string, or regex/classifier pass is permitted before this preflight succeeds.

### 2.6 Enforcement order

The combined normative order is:

```text
candidate + trusted root metadata
  -> root forbidden-provenance gate
  -> content master gate
  -> semantic-category gate
  -> root source/category gate
  -> supported finite root shape?
     -> no: omit
  -> root node budget/depth checks
  -> if root scalar: raw scalar-size preflight
  -> if root container: collection-width check
  -> for each child in deterministic order:
       -> next occurrence fits node/depth budget?
          -> no: omit whole candidate
       -> trusted child provenance gate
       -> supported child shape/type?
          -> no: omit according to provenance/type contract
       -> if child scalar: raw scalar-size preflight
       -> if child container: collection-width/cycle checks before descent
       -> recurse with the same rules
  -> after a scalar passes preflight: value-level secret redaction
  -> canonical safe candidate rendering
  -> per-field character budget
  -> shared per-span content ledger check
  -> final key/privacy filter
  -> export
```

Structural checks may inspect only bounded container metadata needed to apply these limits; they must not consume opaque iterators or inspect forbidden child bodies.

No overflow condition may truncate into an apparently valid partial content value. Overflow omits the whole content candidate and leaves normal Agent/model/tool execution unaffected.

### 2.7 Character budgets are cumulative across the entire span

The existing character limits remain:

```text
MAX_FIELD_CHARS default 2048, valid 64..16384
MAX_SPAN_CHARS  default 8192, valid 256..65536
MAX_SPAN_CHARS >= MAX_FIELD_CHARS
```

`MAX_SPAN_CHARS` is enforced by one shared UAG-owned ledger per canonical span. It is **not** reset per attribute, event, category, tool argument, tool result, message, or capture candidate.

The ledger starts at zero when the canonical span is created. Every content-capture candidate is first fully processed through provenance checks, structural/scalar bounds, redaction, and canonical safe rendering without mutating the span ledger. The candidate is then charged atomically against the remaining span budget.

For budget purposes, candidate character cost is the number of Unicode code points in the exact final canonical content representation that UAG would export for that candidate after redaction and safe rendering. This cost:

- includes scalar text actually exported;
- includes fixed redaction markers such as `[REDACTED]` exactly as rendered;
- includes user/tool-derived structured mapping keys that remain in the rendered content;
- includes canonical structural punctuation, separators, quoting, and escape sequences that are part of the final rendered content representation;
- excludes the OTel/UAG attribute or event **name** used to carry the already-rendered candidate because that carrier name is fixed metadata rather than captured content;
- excludes content candidates that are omitted before export.

The exact same canonical rendering function must be used both to determine the charged character count and to produce the exported candidate. Implementations must not estimate from pre-redaction input length or maintain separate incompatible counting/serialization paths.

Candidate ordering for a canonical span is deterministic. Initial Phase 4 uses this semantic category order:

```text
user_input
assistant_output
tool_arguments
tool_result
```

Within one category, candidates are processed in the trusted UAG-local creation ordinal assigned when the canonical span records the candidate. The ordinal is process-local metadata and cannot be supplied or changed by browser/tool/provider payload content. Structured contents inside one candidate retain the deterministic traversal order defined above.

For each candidate in that order:

```text
candidate_cost = len(final_canonical_rendered_content)
remaining = MAX_SPAN_CHARS - span_content_chars_used

if candidate_cost <= remaining:
    export whole candidate
    span_content_chars_used += candidate_cost
else:
    omit whole candidate
    ledger unchanged
```

Rules:

- no candidate is truncated to fit the remaining span budget;
- a candidate that does not fit is omitted in full;
- omission of one oversized/late candidate does not retroactively remove earlier accepted candidates;
- an omitted candidate consumes zero ledger characters;
- later candidates may still be considered if they fit the unchanged remaining budget;
- redaction and safe rendering happen before the ledger decision, so the ledger charges what is actually exported rather than sensitive pre-redaction text;
- the ledger counts only controlled captured content, not normal metadata-only span attributes already permitted by the Phase 1-3 privacy contract;
- ledger state is local telemetry state and must not affect Agent/model/tool behavior.

Passing traversal limits does not bypass character limits, provenance restrictions, category selection, scalar preflight, or redaction.

### Required regressions

Tests must include:

- a forbidden-provenance root is rejected without enumerating/traversing its value;
- content master OFF or category not selected rejects the root without traversal;
- depth exactly 8 succeeds when every other gate succeeds;
- depth 9 omits the whole candidate;
- a sequence with exactly 64 children succeeds subject to other gates;
- a sequence with 65 children omits the whole candidate;
- a mapping with exactly 64 pairs is width-valid and counts root + 64 keys + 64 values before descendants;
- mapping key-before-value and sequence index-order accounting are deterministic;
- repeated aliases count per occurrence rather than once per object identity;
- an active-path cycle omits the whole candidate;
- exactly 256 visited occurrences succeeds subject to other gates;
- the 257th occurrence causes whole-candidate omission;
- an oversized string is omitted before the redactor/classifier is invoked;
- a scalar exactly at the effective `MAX_FIELD_CHARS` limit may proceed to redaction;
- a wide/deep value cannot trigger unbounded provenance or redaction traversal;
- a generator/custom iterator/file-like object is not consumed and is omitted;
- multiple eligible candidates on one span share one cumulative `MAX_SPAN_CHARS` ledger rather than each receiving a fresh budget;
- final rendered scalar text, surviving structured keys, structure/escaping, and `[REDACTED]` markers contribute exactly their rendered character counts;
- fixed OTel/UAG carrier attribute/event names do not consume the content ledger;
- a candidate whose cost exactly equals the remaining span budget is exported and exhausts the ledger;
- a candidate exceeding the remaining span budget by one character is omitted whole and does not mutate the ledger;
- a later smaller candidate may still fit after an earlier candidate is omitted for insufficient remaining budget;
- category ordering and trusted creation ordinal make accepted/omitted candidate selection deterministic;
- overflow produces only a normalized, content-free diagnostic and never logs the rejected value;
- traversal or character-budget overflow never affects normal Agent/model/tool execution.

## 3. Fixed Phase 4 decisions from this companion

- Ordinary-user `uag.trace_view.v1.name` is a closed UAG-owned enum, not a copied/sanitized backend span name.
- Backend/provider span names are ignored for ordinary-user v1 projection.
- Unknown span classes map to `UNKNOWN` rather than arbitrary text.
- Root provenance/master/category eligibility gates execute before structural traversal.
- Structured content traversal is bounded by depth 8, 64 immediate logical children per collection, and 256 visited node occurrences per candidate.
- Mapping keys and values count as separate node occurrences; aliases count per occurrence; active-path cycles fail closed.
- Raw scalar size is checked before value-level secret scanning; oversized strings are omitted rather than scanned or truncated.
- Traversal limits are fixed and non-configurable in the initial Phase 4 implementation.
- Exceeding any traversal limit omits the whole capture candidate; partial prefix capture is forbidden.
- `MAX_SPAN_CHARS` is one cumulative per-span ledger charged from the exact post-redaction canonical content representation; candidates are accepted or omitted atomically in deterministic order.
- Unreviewed/streaming/opaque iterables are not consumed for telemetry.
