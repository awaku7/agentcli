# OpenTelemetry Phase 4 Scalar and Trace Timing Contract

Status: Normative Phase 4 companion  
Parent scope: `docs/UAG_OPENTELEMETRY_PHASE4_SCOPE.md`  
Security contract: `docs/UAG_OPENTELEMETRY_PHASE4_SECURITY_CONTRACT.md`  
Traversal/rendering contract: `docs/UAG_OPENTELEMETRY_PHASE4_TRACE_NAME_AND_TRAVERSAL_CONTRACT.md`  
Applies to: Phase 4A controlled-content primitive scalars and Phase 4D ordinary-user trace timing projection

This document is the sole normative owner for primitive scalar admission and trace timing normalization. Container admission, mapping-key type, canonical content rendering, candidate limits, and span character accounting are owned by the traversal/rendering contract.

## 1. Primitive content scalars are conversion-free bounded before rendering

A content scalar must not be converted to text, JSON, decimal, bytes, or another variable-size representation before a constant/bounded-cost type and range preflight succeeds.

### 1.1 Accepted exact built-in scalar forms

After provenance/master/category/structure gates pass, the initial controlled-content implementation may process only these exact built-in scalar forms:

```text
None
bool
str
int
float
```

Subclasses and custom protocol-compatible values are not admitted.

Additional rules:

- `bool` is classified before `int` and rendered as boolean;
- strings are subject to the traversal contract's native-length and surrogate preflight;
- integers must be in signed 64-bit range;
- floats must be finite values of the reviewed built-in binary64 `float` type;
- `NaN`, positive/negative infinity, `Decimal`, `Fraction`, arbitrary-precision decimal/rational values, symbolic values, numpy/custom numeric types, or other wrappers are omitted.

Initial mapping keys are **not** governed by the numeric scalar rules: the traversal/rendering contract restricts mapping keys to exact built-in `str` only. Numeric/boolean/null/custom mapping keys fail closed before conversion.

### 1.2 Signed 64-bit integer preflight

The admitted integer range is exactly:

```text
-9223372036854775808 <= value <= 9223372036854775807
```

The implementation must determine eligibility without decimal conversion, for example using range comparison or sign plus `bit_length()`.

An arbitrary-precision integer outside the range is omitted before:

- `str()` / `repr()`;
- JSON serialization;
- decimal formatting;
- UTF-8 rendering;
- regex/secret scanning of a rendered value;
- logging.

### 1.3 Float preflight

Only exact built-in finite `float` values are admitted. `math.isfinite()` or an equivalent bounded operation must succeed before rendering.

The canonical renderer is defined by the traversal/rendering contract. If supported Python versions would produce different canonical text for an admitted float, the implementation must introduce an explicit stable float renderer before enabling Phase 4A rather than accepting version-dependent telemetry output.

### 1.4 Ordering requirement

For an eligible primitive scalar occurrence, the relevant order is:

```text
trusted root/child provenance and category gates
  -> node/depth admission
  -> exact built-in scalar type gate
  -> native scalar preflight
       str   -> native length + surrogate rules
       int   -> signed 64-bit range, conversion-free
       float -> exact built-in finite binary64
       bool/None -> accepted
  -> bounded value-level secret handling where applicable
  -> post-redaction field bound
  -> canonical rendering
  -> shared per-span ledger
  -> export
```

No generic conversion/serialization hook is allowed before the scalar preflight succeeds.

### 1.5 Failure semantics

An unsupported or oversized primitive causes the whole controlled-content candidate to be omitted. It never causes tool/model/Agent failure and never logs the rejected value.

### 1.6 Required regressions

Tests must prove that:

- signed 64-bit minimum and maximum may proceed subject to all other gates;
- the first integer below/above those bounds is omitted before rendering;
- a million-digit integer is rejected without `str()`, JSON rendering, secret scanning of rendered text, or logging;
- exact built-in finite floats may proceed;
- `NaN`, infinities, subclasses, Decimal/Fraction/custom numeric objects fail closed;
- `bool` is rendered as boolean, not integer `0`/`1`;
- numeric mapping keys are rejected without coercion;
- primitive preflight failures emit only normalized content-free diagnostics.

## 2. `uag.trace_view.v1` timing fields use canonical numeric representations

Ordinary-user trace timing fields never copy arbitrary backend strings or vendor payloads. The proxy constructs timing fields only from adapter-normalized typed values.

### 2.1 Canonical output types

For `uag.trace_view.v1`:

```text
start_time  : JSON integer, Unix epoch milliseconds
end_time    : JSON integer, Unix epoch milliseconds
duration_ms : JSON integer, derived only as end_time - start_time
```

All timing fields are exact JSON integers, never strings or floating-point values.

`start_time` and `end_time` must satisfy:

```text
0 <= value <= 9007199254740991   # 2^53 - 1
end_time >= start_time
```

`duration_ms` is never copied from backend data:

```text
duration_ms = end_time - start_time
```

Therefore `duration_ms` is also a non-negative integer `<= 2^53 - 1`.

### 2.2 Adapter raw timestamp preflight

A supported backend adapter must validate the raw typed timestamp before any unit conversion, division, multiplication, decimal/string conversion, serialization, or logging.

For exact built-in integer timestamp inputs, initial accepted ranges are:

```text
milliseconds:
  0 <= raw_ms <= 9007199254740991

microseconds:
  0 <= raw_us <= 9007199254740991999
  canonical_ms = raw_us // 1000

nanoseconds:
  0 <= raw_ns <= 9007199254740991999999
  canonical_ms = raw_ns // 1000000
```

The raw range check itself must be conversion-free. A million-digit integer must be rejected before division or rendering.

Allowed initial normalization forms are:

- exact built-in integer milliseconds after raw-range preflight;
- exact built-in integer microseconds after raw-range preflight, then `// 1000`;
- exact built-in integer nanoseconds after raw-range preflight, then `// 1000000`;
- a backend-specific strict text parser only when that adapter defines a closed grammar and a small fixed input-length ceiling **before parsing**.

Booleans are not timestamps even though Python `bool` subclasses `int`.

### 2.3 Strict text parser requirements

If a specific backend requires textual timestamps, the adapter contract must define:

- maximum raw input length before parsing;
- exact accepted ASCII/Unicode grammar;
- timezone/default behavior if applicable;
- exact conversion to Unix epoch milliseconds;
- rejection of trailing/leading junk;
- no echoing of the raw input in errors or telemetry.

A generic date parser that accepts arbitrary text is not permitted for ordinary-user v1 projection.

### 2.4 Invalid timing behavior

The following make a span invalid for ordinary-user v1 projection:

- unsupported type;
- boolean masquerading as integer;
- negative timestamp;
- raw value above the unit-specific maximum;
- float/NaN/infinity timestamp;
- malformed/overlong text;
- parser failure;
- `end_time < start_time`;
- arithmetic inconsistency.

The invalid span is omitted. If at least one otherwise authorized valid span remains, response `partial=true`. If no authorized valid span remains, the trace-query fail-closed behavior applies and no backend payload is returned.

### 2.5 Timing fields are not content channels

The implementation must never:

- pass through backend timing strings;
- fall back to `str()`/`repr()` of malformed values;
- copy vendor descriptions, timezone labels, URLs, request IDs, exception text, or arbitrary metadata into timing fields;
- preserve raw backend duration when canonical start/end disagree.

Equivalent safe spans from supported backends project to the same integer-millisecond shape.

### 2.6 Required regressions

Tests must prove that:

- valid integer ns/us/ms timestamps normalize to integer Unix epoch milliseconds;
- each unit-specific raw maximum is accepted;
- the first integer above each raw maximum is rejected before conversion;
- million-digit ns/us integers are rejected before division/rendering/logging;
- sub-millisecond precision is discarded deterministically by integer division;
- `duration_ms` equals canonical `end_time - start_time` and ignores raw backend duration;
- negative, float, boolean, malformed, unsupported, or reversed timestamps omit the span;
- arbitrary timing text is never echoed;
- strict backend text parsers reject overlong input before parsing;
- timing omission sets `partial=true` when other authorized spans remain;
- timing failures never affect Agent execution.

## 3. Fixed Phase 4 decisions from this companion

- Primitive scalar admission is exact-type and conversion-free before rendering.
- Controlled-content integers are signed-64-bit only.
- Only finite exact built-in binary64 floats are admitted.
- Numeric/custom mapping keys are not admitted; mapping keys are string-only under the traversal contract.
- Ordinary-user v1 timing fields are JSON integer Unix epoch milliseconds in `0..2^53-1`.
- Raw ms/us/ns integers are range-checked before conversion.
- `duration_ms` is derived from normalized start/end and never copied from backend data.
- Malformed timing values omit the span; arbitrary timing text is never forwarded.