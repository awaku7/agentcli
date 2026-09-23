# Memory and Profile

Status: **Current runtime reference for uag v0.7.14.**

This document describes the Memory/Profile behavior users and integrators should expect today. Historical V2 design rationale lives in `UAG_MEMORY_ARCHITECTURE_V2.md`; authenticated multi-user architecture and security invariants live in `UAG_MEMORY_ARCHITECTURE_V3.md`.

For authenticated Web deployment instructions, see [Web identity and Memory](WEB_IDENTITY_MEMORY.md). For the v0.7.14 implementation audit and remaining gaps, see [UAG v0.7.14 implementation review](UAG_0_7_14_IMPLEMENTATION_REVIEW.md).

______________________________________________________________________

## 1. Two runtime boundaries

uag supports two related but distinct Memory modes.

| Mode | Identity boundary | Primary API / workflow | Intended use |
|---|---|---|---|
| **Local compatibility** | trusted local principal / V2 owner scope | CLI tools, local Profile, legacy `/api/memories` and `/api/profile` | CLI, GUI, trusted single-user Web |
| **Authenticated Web V3** | server-resolved `principal_id` + project/room policy | `/api/me/*`, `/api/rooms/*`, project/room membership APIs | multi-user Web deployments |

The local path remains compatible with existing installations. The authenticated Web path does not trust a browser-supplied owner and does not treat a room ID or project ID as identity.

______________________________________________________________________

## 2. Storage defaults

### Session Store

Session history uses SQLite by default for structured search, tool auditing and summaries.

```text
UAGENT_SESSION_STORE=1
UAGENT_SESSION_BACKEND=sqlite
# Unset: user state directory/sessions/sessions.sqlite3
UAGENT_SESSION_STORE_PATH=
```

The Session Store persists user/assistant/tool messages, tool-call metadata and summaries. Credentials, tokens, cookies and common API-key formats are redacted before persistence.

### Memory Store

Long-term Memory uses SQLite by default:

```text
UAGENT_MEMORY_BACKEND=sqlite
# Unset: user state directory/memory.sqlite3
UAGENT_MEMORY_DB=
```

JSONL remains a local compatibility backend, but authenticated multi-user V3 grants/audiences require SQLite. Do not use JSONL as a multi-user authorization fallback.

______________________________________________________________________

## 3. Local Long-term Memory and Shared Memory

### Local Long-term Memory

Local Long-term Memory stores stable notes such as preferences, constraints or persistent environment facts. Typical management tools include `add_long_memory` and `get_long_memory`.

Local V2 scope defaults are:

```env
UAGENT_MEMORY_PROJECTION=1
UAGENT_MEMORY_STRICT_SCOPE=1
UAGENT_MEMORY_OWNER=
UAGENT_MEMORY_PROJECT=
```

`UAGENT_MEMORY_OWNER` is optional in local mode. When unset, the V2 compatibility path resolves the local owner from the current OS login. Strict Scope rejects records whose project boundary cannot be verified.

### Shared Memory compatibility store

The existing Shared Memory store is a compatibility mechanism for cross-session/agent context in trusted local deployments. It is not the same authorization model as V3 Room Memory or a direct per-user read grant.

For multi-user Web, use the scoped Personal/Room APIs instead of treating the compatibility Shared Memory store as an access-control mechanism.

______________________________________________________________________

## 4. Turn-local retrieval and projection

Memory retrieval is deterministic and tokenizer-free by default. It prefers:

1. normalized exact/phrase matches;
2. word-like token matching where reliable boundaries exist;
3. script-aware character n-gram fallback where whitespace is not a dependable word boundary;
4. candidate-relative ranking to suppress weak boilerplate matches.

Regression coverage includes English and languages that benefit from script-aware fallback, including Japanese, Chinese and Thai.

Relevant Profile guidance and Memory evidence are projected into provider-facing context for one user turn. Projection content is not appended to durable user/assistant history.

The provider-facing order is conceptually:

1. Base System / Safety / Policy
2. Applicable User Guidance
3. authorized Memory Evidence
4. working conversation context
5. current user request

`UAGENT_MEMORY_PROJECTION=0` disables the turn projection compatibility path. `UAGENT_MEMORY_STRICT_SCOPE=0` should be used only for intentional legacy evaluation because it relaxes unknown-scope filtering.

______________________________________________________________________

## 5. Authenticated Web Memory V3

Set an explicit identity mode for Web deployments. OIDC is the built-in browser sign-in path:

```env
UAGENT_IDENTITY_MODE=oidc
UAGENT_OIDC_ISSUER=https://idp.example.com/...
UAGENT_OIDC_CLIENT_ID=your-client-id
UAGENT_OIDC_REDIRECT_URI=https://uag.example.com/auth/oidc/callback
UAGENT_MEMORY_BACKEND=sqlite
```

The server resolves an authenticated `principal_id`. Browser/model payloads cannot select the Memory owner.

### Personal Memory

```text
GET    /api/me/memories
POST   /api/me/memories
PUT    /api/me/memories/{memory_id}
DELETE /api/me/memories/{memory_id}
```

Personal writes derive `owner_id` and personal audience from the current principal. Updates use stable `memory_id` plus `expected_revision`.

### Direct read-only sharing

An owner can grant another principal read access to one confirmed revision:

```text
GET    /api/me/memories/{memory_id}/grants
POST   /api/me/memories/{memory_id}/grants
DELETE /api/me/memories/{memory_id}/grants/{grant_id}
```

Recipients read shared references through:

```text
GET /api/me/shared-memories
GET /api/me/shared-memories/{memory_id}
```

A grant does not confer edit/delete/reshare ownership. Updating a source Memory invalidates grants to the old revision for the new content; forgetting it removes the source and its grants.

### Room Memory

```text
GET    /api/rooms/{room_id}/memories
POST   /api/rooms/{room_id}/memories
PUT    /api/rooms/{room_id}/memories/{memory_id}
DELETE /api/rooms/{room_id}/memories/{memory_id}
```

Room Memory requires authorized project access, a persisted room-to-project binding and Room policy permission. Knowing `room_id` is not authorization.

Personal Memory is never automatically promoted into Room Memory.

______________________________________________________________________

## 6. Project and Room authorization

Authenticated multi-user Memory is bounded by project policy before record relevance is evaluated.

A fixed single-project deployment may set:

```env
UAGENT_MEMORY_PROJECT=my-project
```

An OIDC multi-project session may select an already-authorized project through:

```text
POST /api/project-context
```

The client `project_id` acts only as a selector that must match the server-bound context and membership policy.

Project administration endpoints include:

```text
GET    /api/projects/{project_id}/members
PUT    /api/projects/{project_id}/members/{principal_id}
DELETE /api/projects/{project_id}/members/{principal_id}
PUT    /api/projects/{project_id}/rooms/{room_id}
```

Room membership endpoints include:

```text
GET    /api/rooms/{room_id}/members
PUT    /api/rooms/{room_id}/members/{principal_id}
DELETE /api/rooms/{room_id}/members/{principal_id}
```

______________________________________________________________________

## 7. User Profile

### Local Profile

The local compatibility Profile stores environment, preferences and constraints. Typical commands are `:profile`, `:profile-fromlog` and `:profile-clear`.

### Authenticated principal Profile

Authenticated Web users have principal-keyed Profile files and APIs:

```text
GET /api/me/profile
PUT /api/me/profile
```

The runtime hashes the stable principal ID into the per-user Profile path instead of using display name/email as the storage key.

Shared evidence from another principal remains attributed Memory evidence. It is not automatically promoted into the recipient's preferences or constraints.

The legacy `/api/profile` endpoint is restricted to local identity mode.

______________________________________________________________________

## 8. Snapshot invalidation and revocation

Authenticated projection snapshots bind identity and access state, including principal/project/room and Memory access generation.

Memory writes, grant changes and relevant authorization changes cause stale projection state to be rejected. The provider/tool continuation path checks whether the snapshot remains current instead of blindly reusing a snapshot created before revocation.

This does not retroactively erase information that was already shown/exported or already sent to an external provider. Revocation controls subsequent authorized use and reuse.

______________________________________________________________________

## 9. Directory groups

Verified directory group claims may feed Project/Room policy, but groups are authorization inputs, never Personal Memory ownership keys.

Entra OIDC group-overage markers currently fail closed. `UAGENT_DIRECTORY_GROUP_POLICY` can map already verified group IDs to project/room roles, but it is not a directory client and does not resolve overage by itself.

______________________________________________________________________

## 10. Legacy Web APIs

These compatibility endpoints remain available only when the request resolves to local identity:

```text
/api/memories
/api/profile
```

Authenticated multi-user Web clients should use `/api/me/*` and `/api/rooms/*`. The legacy endpoints are intentionally not an alternate way to select another user's owner.

______________________________________________________________________

## 11. Security constraints

- Never store passwords, API keys, access tokens, ID tokens or cookies in Memory/Profile.
- Never derive authenticated ownership from email, UPN, display name, room ID or browser-provided owner fields.
- Multi-user Memory requires SQLite and server-controlled identity/project/room policy.
- Direct read grants are read-only and revision-bound.
- Shared evidence must not silently become the recipient's Profile guidance.
- Identity resolution failures in non-local modes must fail closed rather than silently falling back to `local`.

______________________________________________________________________

## 12. Current v0.7.14 limitations

The major V3 boundaries are implemented, but production rollout is not complete in every deployment shape:

- OIDC sessions are process-local; restart signs users out and multi-instance/HA needs a durable session design.
- Non-OIDC multi-user/multi-project HTTP ProjectContext still needs deployment integration.
- Entra group overage/freshness requires a trusted directory API adapter.
- Trusted Proxy/OAuth/Windows AD/External modes require deployment-specific verified adapters/trust boundaries where applicable.
- Multi-user/shared-room default rollout should follow the V3 isolation/revocation evaluation gates.

See [Web identity and Memory](WEB_IDENTITY_MEMORY.md), [Memory V3 security hardening](UAG_MEMORY_V3_SECURITY_HARDENING.md), and [the v0.7.14 implementation review](UAG_0_7_14_IMPLEMENTATION_REVIEW.md) for details.
