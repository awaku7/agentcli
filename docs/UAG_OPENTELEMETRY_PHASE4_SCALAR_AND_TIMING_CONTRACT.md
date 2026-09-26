# OpenTelemetry Phase 4 Scalar and Trace Timing Contract

Status: Normative Phase 4 companion  
Parent scope: `docs/UAG_OPENTELEMETRY_PHASE4_SCOPE.md`  
Security contract: `docs/UAG_OPENTELEMETRY_PHASE4_SECURITY_CONTRACT.md`  
Traversal contract: `docs/UAG_OPENTELEMETRY_PHASE4_TRACE_NAME_AND_TRAVERSAL_CONTRACT.md`  
Applies to: Phase 4A controlled-content scalar handling and Phase 4D ordinary-user trace projection

This companion closes two remaining implementation ambiguities found during Phase 4 review. Where the parent or companion documents say that primitive numeric values have a bounded representation, or list `start_time`, `end_time`, and `duration_ms` without exact scalar rules, the rules below are normative for the initial Phase 4 implementation.

## 1. Numeric content scalars are conversion-free bounded before rendering

A content scalar must not be converted to text, JSON, decimal, or another variable-size representation before a constant/bounded-cost type and range preflight succeeds.

### 1.1 Accepted primitive scalar forms

After the existing provenance/master/category/type gates pass, the initial controlled-content implementation may process only these primitive scalar forms:

- `null`;
- boolean;
- string, subject to the existing native-length `MAX_FIELD_CHARS` preflight;
- integer in the signed 64-bit range `[-9223372036854775808, 9223372036854775807]`;
- finite IEEE-754 binary64 floating-point values representable by the runtime's reviewed built-in float type.

Arbitrary-precision integers outside the signed 64-bit range are omitted. The implementation must determine integer eligibility without decimal conversion, for example by sign plus `bit_length()` or an equivalent bounded-cost range comparison.

`NaN`, positive/negative infinity, arbitrary-precision decimal types, rational/fraction types, custom numeric objects, symbolic numbers, and unreviewed numeric wrappers are omitted unless a later reviewed contract explicitly admits them.

The same scalar rules apply to eligible mapping keys. A custom key object's `__str__`, formatter, serializer, iterator, or conversion hook must never be invoked merely for telemetry.

### 1.2 Ordering requirement

For an eligible scalar occurrence, the relevant order is:

```text
trusted provenance/category/type gates
  -> node/depth budget admission
  -> native scalar preflight
       string -> native length <= effective MAX_FIELD_CHARS
       int    -> signed 64-bit range check without decimal conversion
       float  -> reviewed built-in binary64 and finite
       bool/null -> accepted primitive form
  -> value-level secret redaction/classification where applicable
  -> bounded normalization/rendering
  -> per-field/per-span character budgets
  -> export
```

No `str(value)`, `repr(value)`, JSON serialization, decimal formatting, UTF-8 encoding of a rendered number, regex pass over a rendered number, or provider/custom conversion is allowed before the numeric preflight succeeds.

An oversized/unsupported numeric scalar causes the whole controlled-content capture candidate to be omitted, consistent with the traversal contract's fail-closed overflow behavior. Normal Agent/model/tool execution is unaffected.

### 1.3 Required regressions

Tests must prove that:

- signed 64-bit minimum and maximum integers may proceed subject to all other gates;
- `-9223372036854775809` and `9223372036854775808` are omitted before decimal/string/JSON rendering;
- an arbitrary-precision integer with millions of decimal digits is rejected using a conversion-free range/bit-length check and is never passed to `str()`, JSON serialization, or the secret redactor;
- finite reviewed built-in floats may proceed, while `NaN` and infinities are omitted;
- arbitrary precision decimal/fraction/custom numeric objects are omitted without invoking custom formatting/conversion hooks;
- the same rules apply to mapping keys;
- numeric preflight failure emits only normalized content-free diagnostics and never the rejected value.

## 2. `uag.trace_view.v1` timing fields use canonical numeric representations

Ordinary-user trace timing fields must never copy arbitrary backend strings or vendor payloads. The proxy constructs timing fields from adapter-normalized typed values.

### 2.1 Canonical output types

For `uag.trace_view.v1`:

```text
start_time  : JSON integer, Unix epoch milliseconds
end_time    : JSON integer, Unix epoch milliseconds
duration_ms : JSON integer, derived as end_time - start_time
```

All three fields are exact JSON integers, not strings and not floating-point values.

`start_time` and `end_time` must be within the non-negative IEEE-754 exact-integer range:

```text
0 <= value <= 9007199254740991   # 2^53 - 1
```

`end_time` must be greater than or equal to `start_time`.

`duration_ms` is never copied from the backend. It is computed only after both canonical timestamps validate:

```text
duration_ms = end_time - start_time
```

Therefore `duration_ms` is also a non-negative integer no larger than `9007199254740991`.

### 2.2 Adapter normalization

A supported backend adapter may receive timestamps in backend-specific units or representations, but it must normalize them before trace-view projection.

Allowed normalization rules:

- typed integer nanoseconds: convert with integer division to Unix epoch milliseconds;
- typed integer microseconds: convert with integer division to Unix epoch milliseconds;
- typed integer milliseconds: validate directly;
- another backend representation may be supported only by an adapter-specific strict parser with a bounded input length and a closed documented grammar.

An arbitrary or enriched backend string is never copied into any timing field. A strict timestamp parser, if used for a specific backend, must bound the input before parsing and return only the canonical integer milliseconds value.

Unsupported types, booleans masquerading as integers, floats, `NaN`/infinity, negative timestamps, out-of-range integers, malformed strings, parse failures, `end_time < start_time`, or arithmetic overflow make that span invalid for ordinary-user v1 projection. The invalid span is omitted rather than partially returned with timing text.

When one or more otherwise authorized spans are omitted because timing normalization fails, the response must set `partial=true`. If no authorized valid span remains, existing fail-closed trace-query behavior applies and no backend payload is returned.

### 2.3 Timing fields are not content channels

The implementation must not:

- pass through backend `start_time`, `end_time`, or `duration` strings;
- fall back to `str()`/`repr()` of malformed timing values;
- copy vendor timing descriptions, timezone labels, URLs, request IDs, exception text, or arbitrary metadata into timing fields;
- preserve raw backend duration when canonical start/end values disagree with it.

The canonical v1 timing representation is backend-independent. Equivalent spans from different supported backends project to the same integer-millisecond shape.

### 2.4 Required regressions

Tests must prove that:

- valid typed nanosecond/microsecond/millisecond timestamps normalize to integer Unix epoch milliseconds;
- sub-millisecond precision is discarded deterministically by integer division;
- `duration_ms` equals canonical `end_time - start_time` and ignores any conflicting raw backend duration;
- negative, out-of-range, floating, boolean, malformed, or unsupported timing values omit the span;
- `end_time < start_time` omits the span;
- a timing string containing a prompt fragment, URL, credential, exception, or other arbitrary text is never echoed in the response;
- a backend-specific strict parser, if implemented, rejects overlong input before parsing and emits only integer milliseconds;
- omission due to timing normalization sets `partial=true` when other authorized spans remain;
- no malformed timing input affects normal Agent execution.

## 3. Fixed Phase 4 decisions from this companion

- Controlled-content integers are restricted to signed 64-bit values before rendering.
- Arbitrary-precision integers are rejected using conversion-free range/bit-length checks.
- Only finite reviewed built-in binary64 floats are admitted; arbitrary/custom numeric types fail closed.
- Ordinary-user v1 timing fields are JSON integers in Unix epoch milliseconds.
- Timing output is bounded to `0..2^53-1` for exact cross-language integer representation.
- `duration_ms` is derived from normalized start/end timestamps and is never copied from backend data.
- Malformed or unsupported timing values omit the span; arbitrary timing text is never forwarded.
