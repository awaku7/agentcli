# OpenTelemetry Phase 4 Scope

Status: Design overview  
Parent design: `docs/UAG_OPENTELEMETRY_DESIGN.md`  
Normative contract: `docs/UAG_OPENTELEMETRY_PHASE4_CONTRACT.md`  
Prerequisite: Phase 3 complete on `main`

This file is intentionally **non-normative**. It explains Phase 4 goals, rollout, and boundaries only. Exact grammars, limits, schemas, processing orders, field types, privacy rules, pseudonym rules, provider diagnostics, trace-query behavior, and failure semantics are defined **only** in `docs/UAG_OPENTELEMETRY_PHASE4_CONTRACT.md`.

If this overview and the normative contract appear to conflict, the contract is authoritative and this overview must be corrected.

## 1. Purpose

Phase 4 adds four optional advanced-diagnostics capabilities without weakening Phase 1-3 behavior:

1. controlled content capture;
2. pseudonymous principal/room/project correlation;
3. optional provider SDK nested diagnostics;
4. authorization-aware trace-query proxying.

The governing principle remains:

> UAG owns the observability model. OpenTelemetry is an optional projection/export backend.

Telemetry is never a source of truth for identity, authorization, session validity, Memory policy, tool permission, Agent state, routing, credential selection, or scope selection.

## 2. Phase 1-3 invariants remain unchanged

Phase 4 preserves the existing contracts around:

- opt-in OpenTelemetry activation;
- canonical UAG Agent/LLM/Tool spans;
- one logical Agent trace per Web turn;
- trusted-ingress handling for browser trace context;
- A2A/MCP propagation isolation from identity/authz;
- server-authoritative OIDC/session and room/project/private-room authorization;
- no telemetry-derived authorization;
- no content/identity/secrets in metrics, baggage, or process resources;
- duplicate-span prevention;
- observability failure isolation from Agent/model/tool execution.

## 3. Rollout

### Phase 4A - privacy and controlled-content foundation

Implement the policy/runtime foundation first while keeping content capture OFF by default:

- one shared configuration resolver;
- explicit capture categories;
- trusted provenance and hard-denied provenance;
- bounded structured traversal and scalar handling;
- deterministic privacy/secret handling;
- one UAG-owned content carrier and renderer;
- bounded per-span content accounting.

### Phase 4B - pseudonymous correlation

Add server-held, trace-only pseudonymous correlation for principal/room/project using a dedicated key and stable deployment domain. Pseudonyms remain diagnostics only and never become identity, authorization, routing, or storage keys.

### Phase 4C - provider SDK diagnostics

Add optional metadata-only provider diagnostics beneath the canonical UAG `chat` span. UAG's canonical LLM operation remains authoritative and provider-native content capture stays disabled.

### Phase 4D - authorization-aware trace query proxy

Add bounded backend reads, a local UAG authorization/ownership index, current auth/authz revalidation, and a closed ordinary-user metadata-only response shape. Ordinary users never receive raw backend responses or credentials.

Controlled content should be the last Phase 4 capability enabled in production even though its policy foundation is implemented first.

## 4. Security and privacy posture

Across all four phases:

- every capability is independently opt-in and OFF by default;
- invalid or ambiguous telemetry configuration fails closed for the affected feature;
- reasoning/hidden analysis, system/developer instructions, authentication/session/credential bodies, Memory/retrieval bodies, file/artifact bodies, and comparable security-sensitive content remain outside the initial capture surface;
- pseudonyms never authorize;
- provider instrumentation never creates a second canonical LLM operation;
- trace possession never grants access;
- current UAG auth/authz wins over historical telemetry state;
- observability failures never change normal Agent/model/tool behavior.

## 5. Multi-user and distributed-trace boundaries

A distributed trace may span multiple UAG instances/services/scopes. Access to one local segment never authorizes another segment. Current authorization is evaluated from UAG-owned state, not backend span/resource fields.

A WebSocket/room is not a long-lived trace root, and one turn remains one logical Agent trace.

## 6. Retention and deletion

Phase 4 does not imply automatic deletion propagation into external telemetry backends. Backend retention/access policy remains an operator responsibility. Removing local UAG authorization metadata causes ordinary-user trace lookup to fail closed even if the backend retains the trace.

## 7. Implementation order and repository gates

Recommended implementation order:

1. Phase 4A;
2. Phase 4B;
3. Phase 4C;
4. Phase 4D.

Each implementation slice must retain existing repository gates, including supported Python versions, Ruff, Black, applicable I18N/tool-catalog checks, full pytest, and unchanged behavior when OpenTelemetry is disabled.

## 8. Explicitly deferred

Requires later design review:

- reasoning/chain-of-thought capture;
- system/developer instruction capture;
- Memory/retrieval/file/artifact/auth/session/credential body capture;
- provider-native prompt/response export;
- richer provider SDK attributes/events/links;
- ordinary-user captured-content viewing;
- ordinary-user pseudonym-based trace discovery;
- cross-instance trace-authorization federation;
- pseudonyms as security/storage identity;
- generic global provider/HTTP auto-instrumentation;
- direct ordinary-user raw trace-backend access;
- telemetry-driven authorization decisions.

## 9. Normative reference

All exact implementation behavior is defined in:

`docs/UAG_OPENTELEMETRY_PHASE4_CONTRACT.md`
