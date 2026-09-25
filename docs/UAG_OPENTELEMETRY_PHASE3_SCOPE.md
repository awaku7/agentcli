# OpenTelemetry Phase 3 Scope

Phase 3 adds trusted distributed trace propagation without changing UAG authentication, authorization, tool, or model behavior.

## Goals

- propagate W3C `traceparent` / `tracestate` only across UAG-controlled or explicitly trusted internal hops;
- keep browser/user supplied trace context detached from Web Agent roots;
- represent remote Agent execution as child `invoke_agent` work rather than unrelated roots when the transport is trusted;
- preserve one logical UAG span per Agent/LLM/Tool boundary and avoid duplicate transport-level logical spans;
- keep trace context completely separate from identity, authorization, room/project scope, session validity, and Memory access policy;
- degrade safely when OpenTelemetry is disabled or propagation cannot be performed.

## Trust model

Trace propagation is metadata, never authentication.

Default rules:

1. Browser/WebSocket/client-provided inbound trace headers remain untrusted and detached.
2. A2A outbound calls may inject trace context only when initiated by UAG runtime code through the trusted A2A client boundary.
3. A2A inbound context may be extracted only after the request has passed the existing A2A authentication/trust boundary.
4. Sub-Agent execution inside the same process inherits the active ContextVar/OTel context naturally; no serialized trace metadata is required.
5. MCP stdio does not require W3C header propagation. It may remain a child of the current local tool span through in-process context only.
6. MCP HTTP propagation is opt-in to the UAG-owned HTTP transport boundary and must never overwrite configured authentication headers.
7. Reverse-proxy/internal ingress propagation is disabled unless an explicit server-side trust policy says the ingress is trusted.
8. `traceparent`, `tracestate`, baggage, trace IDs, and span IDs are never used as authorization inputs.

## Implementation order

### A2A

- add provider-neutral inject/extract helpers under `runtime.observability`;
- inject current trace context from `A2AClient` for authenticated UAG-to-UAG requests;
- extract trusted context at the authenticated A2A server request boundary;
- parent the remote Agent execution from the extracted context;
- do not trust arbitrary public/client trace headers before authentication.

### Sub-Agent

- add canonical `invoke_agent` child spans around logical Sub-Agent executions;
- inherit active process-local context automatically;
- chains/parallel executions create sibling child Agent spans rather than one shared long-lived span;
- do not export task text, ContextPack bodies, run IDs, raw role/config content, or tool payloads.

### MCP

- keep existing outer UAG `execute_tool` span authoritative;
- for HTTP MCP transports, inject W3C context only through the UAG-created HTTP client path;
- for stdio, retain local parent/child context only and do not invent trace headers;
- avoid duplicate canonical tool spans from SDK/HTTP auto-instrumentation.

## Trusted reverse-proxy ingress

No network source is trusted merely because it supplied a valid W3C header. A later implementation in this phase may accept inbound context only when a server-side deployment policy explicitly marks the ingress path as trusted. The policy must be independent from request payload/header values and must default to OFF.

## Privacy and cardinality

Phase 3 must not export:

- request/message/task/tool bodies;
- tokens, cookies, Authorization values, MCP OAuth material, or credential names/secrets;
- raw principal/subject/group/session/room/project IDs;
- A2A task IDs, Sub-Agent run IDs, MCP session IDs, resource URIs, or arbitrary endpoint URLs as metric dimensions.

Low-cardinality transport attributes may describe categories such as `a2a`, `sub_agent`, `mcp_http`, or `mcp_stdio`.

## Failure isolation

- propagation helpers are best-effort and no-op when observability is disabled;
- malformed or unavailable trace context never fails an Agent task;
- propagation failure never bypasses or weakens existing authentication/authorization;
- exporter/SDK failures remain isolated from runtime behavior.

## Validation

Required tests include:

- browser-provided trace context remains detached;
- authenticated trusted A2A hop continues a trace;
- unauthenticated/untrusted A2A input cannot select the parent trace;
- trace context does not change auth/authz outcomes;
- Sub-Agent child spans inherit the active trace while sibling executions keep separate spans;
- HTTP MCP injection preserves auth headers and omits sensitive content;
- stdio MCP remains functional without serialized W3C headers;
- duplicate logical spans are not introduced;
- OTel disabled behavior is unchanged;
- Python 3.11 / 3.13 / 3.14, Ruff, Black, and full pytest stay green.

## Out of scope

- controlled prompt/response/tool content capture;
- pseudonymous user/session correlation;
- provider SDK auto-instrumentation as a replacement for UAG logical spans;
- end-user trace-query UI/proxy;
- using trace metadata for security decisions.
