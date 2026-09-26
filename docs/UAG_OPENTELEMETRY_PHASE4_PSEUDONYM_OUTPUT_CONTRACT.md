# OpenTelemetry Phase 4 Pseudonym Output Contract

Status: Normative Phase 4 companion  
Parent scope: `docs/UAG_OPENTELEMETRY_PHASE4_SCOPE.md`  
Security contract: `docs/UAG_OPENTELEMETRY_PHASE4_SECURITY_CONTRACT.md`  
Applies to: Phase 4B pseudonymous correlation output and correlation-key version labels

This companion fixes the initial exported pseudonym representation so implementations cannot choose an arbitrarily short digest truncation while still claiming compliance. It also fixes the initial correlation-key version grammar so rotation metadata remains bounded and low-cardinality.

## 1. Initial pseudonym representation is fixed

The HMAC construction and canonical framed input remain defined by the parent scope:

```text
magic = b"uag-otel-pseudo-v1"
frame(x) = uint32_be(len(utf8(x))) || utf8(x)
message = magic || frame(deployment_scope) || frame(kind) || frame(raw_identifier)
digest = HMAC-SHA-256(correlation_key, message)
```

For the initial Phase 4 implementation, the exported pseudonym is exactly:

```text
pseudo128 = lowercase_hex(digest[0:16])
```

Therefore:

- exactly the first 128 digest bits are exported;
- the textual representation is exactly 32 lowercase hexadecimal characters;
- no operator, browser, provider, tool, A2A/MCP peer, baggage value, or remote configuration may shorten the digest;
- no implementation may use fewer than 128 digest bits;
- the truncation length is not configurable in the initial Phase 4 release;
- changing the representation or digest length requires an explicitly reviewed schema/version change.

Using more than 128 bits is also deferred for the initial schema so equivalent deployments produce the same stable representation rather than implementation-specific output lengths.

## 2. Correlation-key version labels are bounded and low-cardinality

The public controls are:

```text
--otel-correlation-key-version <version>
UAGENT_OTEL_CORRELATION_KEY_VERSION=<version>
```

Configuration precedence remains the security-contract rule:

```text
explicit CLI/application setting
    > UAGENT_* environment setting
    > safe default
```

The initial safe default is exactly:

```text
v1
```

An explicitly configured version is valid only when it matches this ASCII grammar exactly:

```text
^[a-z0-9][a-z0-9._-]{0,31}$
```

Therefore the version label:

- is 1 to 32 ASCII characters;
- begins with a lowercase ASCII letter or digit;
- after the first character may contain only lowercase ASCII letters, digits, `.`, `_`, or `-`;
- is case-sensitive and lowercase-only;
- contains no whitespace, control characters, path separators, quotes, non-ASCII text, or arbitrary free-form metadata;
- is operator/server configuration only and cannot be supplied by a browser, tool, provider, A2A/MCP peer, baggage value, trace header, or request payload.

Examples accepted by the initial contract include:

```text
v1
v2
2026q4
blue-2
key_03
rotation.4
```

Examples rejected by the initial contract include empty values, values longer than 32 characters, `V2`, `v 2`, `/v2`, `v2/`, `v2:prod`, Unicode labels, or any other value outside the grammar.

Validation and failure behavior:

- a missing CLI and environment value uses the safe default `v1`;
- an explicitly supplied empty or invalid value does **not** fall back to `v1`;
- an invalid explicit version disables pseudonymous-correlation emission for that process and emits only a normalized secret-free diagnostic;
- invalid version metadata never disables core metadata tracing and never affects Agent/model/tool behavior;
- the version label is diagnostic metadata only and is never an authentication, authorization, routing, storage, Memory, credential-selection, or trace-query authorization input;
- UAG never derives the label from secret key bytes and never places secret material in the label.

Rotation semantics:

- one version label identifies one intentionally selected correlation-key generation within a deployment correlation domain;
- when correlation key material is intentionally rotated, the configured version label must also change before new pseudonyms are emitted;
- a version label remains stable while the corresponding key generation is active;
- historical traces retain their historical version label and pseudonym;
- reusing one version label for different correlation-key material is a configuration error and must fail closed when detectable by UAG-managed key metadata;
- if the external credential store does not expose enough metadata to detect such reuse, operators are responsible for changing the version label together with the key; UAG must not guess or synthesize a replacement label.

The version label is not part of the HMAC message in the initial construction. Domain separation continues to come from the dedicated key, `deployment_scope`, and `kind`; the version is bounded diagnostic metadata for rotation/query interpretation.

## 3. Collision and security semantics

The 128-bit pseudonym remains a diagnostic correlation label only. It is not a security identity and must never be used for authentication, authorization, session selection, Memory access, routing, storage keys, credential selection, or trace-query authorization.

A pseudonym collision must never merge or broaden an authorization decision because authorization is performed only from current UAG-owned identity/scope records.

Raw identifiers remain local to UAG and the full HMAC digest need not be exported.

## 4. Required regressions

Tests must prove that:

- every exported initial Phase 4 pseudonym is exactly 32 lowercase hex characters;
- the output contains exactly the first 128 bits of the HMAC-SHA-256 digest;
- a configuration or payload cannot request 1-bit, 8-bit, 64-bit, or any other shorter truncation;
- equivalent key/scope/kind/raw-identifier inputs produce the same 128-bit pseudonym across replicas;
- different `kind` or `deployment_scope` values remain domain-separated;
- pseudonym collisions, whether synthetic in tests or theoretical in operation, cannot affect authorization because pseudonyms are never authorization inputs;
- missing key-version configuration resolves to exactly `v1`;
- valid boundary labels of length 1 and 32 are accepted when they satisfy the grammar;
- empty, uppercase, whitespace-bearing, non-ASCII, path-like, punctuation-outside-the-allowlist, and 33-character labels fail closed to no pseudonym emission;
- CLI key-version configuration overrides the environment fallback;
- invalid explicit CLI configuration does not silently fall back to a valid environment value or `v1`;
- key-version labels cannot be overridden by request, provider, tool, A2A/MCP, baggage, or trace data;
- rotation changes both key material and version label before new pseudonyms are emitted;
- no key-version failure changes core tracing or Agent execution.

## 5. Fixed Phase 4 decisions from this companion

- Initial exported pseudonyms use exactly 128 HMAC digest bits.
- Encoding is exactly 32 lowercase hexadecimal characters.
- Truncation length is not configurable in the initial release.
- Fewer than 128 digest bits are forbidden.
- The initial correlation-key version default is exactly `v1`.
- Explicit key-version values must match `^[a-z0-9][a-z0-9._-]{0,31}$`.
- Invalid explicit key-version configuration disables pseudonym emission rather than falling back silently.
- Correlation-key rotation changes the version label along with the key generation.
- Pseudonyms and version labels remain diagnostic-only and never become security identities.
