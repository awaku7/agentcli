# OpenTelemetry Phase 4 Pseudonym Output Contract

Status: Normative Phase 4 companion  
Parent scope: `docs/UAG_OPENTELEMETRY_PHASE4_SCOPE.md`  
Security contract: `docs/UAG_OPENTELEMETRY_PHASE4_SECURITY_CONTRACT.md`  
Applies to: Phase 4B pseudonymous correlation output

This companion fixes the initial exported pseudonym representation so implementations cannot choose an arbitrarily short digest truncation while still claiming compliance.

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

## 2. Collision and security semantics

The 128-bit pseudonym remains a diagnostic correlation label only. It is not a security identity and must never be used for authentication, authorization, session selection, Memory access, routing, storage keys, credential selection, or trace-query authorization.

A pseudonym collision must never merge or broaden an authorization decision because authorization is performed only from current UAG-owned identity/scope records.

Raw identifiers remain local to UAG and the full HMAC digest need not be exported.

## 3. Required regressions

Tests must prove that:

- every exported initial Phase 4 pseudonym is exactly 32 lowercase hex characters;
- the output contains exactly the first 128 bits of the HMAC-SHA-256 digest;
- a configuration or payload cannot request 1-bit, 8-bit, 64-bit, or any other shorter truncation;
- equivalent key/scope/kind/raw-identifier inputs produce the same 128-bit pseudonym across replicas;
- different `kind` or `deployment_scope` values remain domain-separated;
- pseudonym collisions, whether synthetic in tests or theoretical in operation, cannot affect authorization because pseudonyms are never authorization inputs.

## 4. Fixed Phase 4 decisions from this companion

- Initial exported pseudonyms use exactly 128 HMAC digest bits.
- Encoding is exactly 32 lowercase hexadecimal characters.
- Truncation length is not configurable in the initial release.
- Fewer than 128 digest bits are forbidden.
- Pseudonyms remain diagnostic-only and never become security identities.
