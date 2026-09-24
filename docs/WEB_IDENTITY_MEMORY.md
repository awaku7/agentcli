# Web identity and Memory

This guide explains the authenticated multi-user Web behavior available in uag v0.7.14. It focuses on identity, project/room access, Personal Memory, shared Memory, and Profile isolation.

For the internal design and security invariants, see [UAG Memory Architecture V3](UAG_MEMORY_ARCHITECTURE_V3.md). For the implementation status review, see [UAG v0.7.14 implementation review](UAG_0_7_14_IMPLEMENTATION_REVIEW.md).

## 1. Choose the deployment mode

### Local / single-user

The default identity mode is `local`:

```env
UAGENT_IDENTITY_MODE=local
```

The local resolver uses one trusted local principal. Existing local Memory/Profile commands and the legacy Web `/api/memories` and `/api/profile` compatibility APIs remain available in this mode.

### Authenticated multi-user Web

For browser sign-in, use OIDC:

```env
UAGENT_IDENTITY_MODE=oidc
UAGENT_OIDC_ISSUER=https://idp.example.com/...
UAGENT_OIDC_CLIENT_ID=your-client-id
UAGENT_OIDC_REDIRECT_URI=https://uag.example.com/auth/oidc/callback
# Required only when the provider/client registration uses a client secret.
UAGENT_OIDC_CLIENT_SECRET=

# Keep secure cookies enabled for HTTPS deployments. Default: 1
UAGENT_OIDC_COOKIE_SECURE=1
# Server-side session lifetime in seconds. Default: 28800
UAGENT_OIDC_SESSION_TTL=28800

# Memory V3 multi-user APIs require SQLite Memory.
UAGENT_MEMORY_BACKEND=sqlite
```

uag uses Authorization Code + PKCE and verifies the provider metadata, signing key and ID-token claims before creating an opaque server-side session. The browser does not choose its `principal_id`.

For a fixed single-project deployment, bind the server to one project:

```env
UAGENT_MEMORY_PROJECT=my-project
```

For an OIDC multi-project deployment, the authenticated session can select an authorized project through `/api/project-context` after project membership has been configured.

## 2. Sign in and inspect status

Start the Web UI normally, then open:

```text
/auth/oidc/login
```

After a successful callback, uag creates an HttpOnly session cookie and redirects to `/`.

Safe authentication status is available at:

```text
GET /api/auth/status
```

It reports the configured mode/health and whether the current request is authenticated without returning raw tokens or the provider subject.

Logout:

```text
POST /auth/logout
```

Administrators configured through `UAGENT_ADMIN_PRINCIPALS` can use:

```text
GET /api/admin/auth/status
```

The admin status endpoint returns safe operational metadata such as the active OIDC session count; it does not expose tokens, client secrets, or raw identity claims.

## 3. Project access is server controlled

A `project_id` sent by a browser is only a selector. It does not grant access.

For a fixed deployment, `UAGENT_MEMORY_PROJECT` is the server-side project binding. For OIDC sessions without a fixed project, or authenticated non-OIDC sessions using the ProjectContext cookie, select a project after authentication:

```http
POST /api/project-context
Content-Type: application/json

{"project_id":"my-project"}
```

The selection succeeds only when the authenticated principal already has at least viewer access to that project.

Project roles are used as authorization boundaries. The current policy uses viewer/editor/admin-style access: read operations require an appropriate membership, writes require stronger access, and project/room administration requires admin authorization.

Project membership administration endpoints include:

```text
GET    /api/projects/{project_id}/members
PUT    /api/projects/{project_id}/members/{principal_id}
DELETE /api/projects/{project_id}/members/{principal_id}
```

A room can also be bound to a project:

```text
PUT /api/projects/{project_id}/rooms/{room_id}
```

Knowing a project or room identifier is never treated as authorization by itself.

## 4. Personal Memory

Authenticated Personal Memory is always derived from the current server-side principal. The browser cannot supply another owner.

```text
GET    /api/me/memories
POST   /api/me/memories
PUT    /api/me/memories/{memory_id}
DELETE /api/me/memories/{memory_id}
```

Create example:

```json
{
  "project_id": "my-project",
  "note": "Prefer concise release summaries"
}
```

Updates and deletes use the stable `memory_id` and an `expected_revision`. A stale revision is rejected rather than silently overwriting a newer value.

### Private Web session lifecycle

`POST /api/me/private-room` creates an owner-bound private Web room only after server-side identity and project authorization succeed. Disconnected, idle private sessions have a 24-hour reconnect grace period by default. Set `UAGENT_WEB_ROOM_IDLE_TTL_SECONDS` to change it (accepted range: 60 seconds to 30 days). Activity refreshes the idle deadline. Active WebSockets and rooms with a running agent, streaming response, or pending `human_ask` are not evicted. On upgrade, legacy private rooms receive a fresh reconnect grace period rather than expiring based on their original creation time.

After the idle period expires, UAG removes the private-room binding, its room-scoped Memory, and the associated Web session history. Personal Memory is not removed. A private room that has expired cannot be reconnected.

## 5. Share one Personal Memory with another user

A Personal Memory can be shared as a read-only grant for exactly the confirmed revision.

List grants:

```text
GET /api/me/memories/{memory_id}/grants
```

Grant read access:

```text
POST /api/me/memories/{memory_id}/grants
```

Example body:

```json
{
  "project_id": "my-project",
  "grantee_principal_id": "<server principal id>",
  "expected_revision": 1
}
```

Revoke a grant:

```text
DELETE /api/me/memories/{memory_id}/grants/{grant_id}
```

A recipient can read references shared with them through:

```text
GET /api/me/shared-memories
GET /api/me/shared-memories/{memory_id}
```

A read grant does **not** grant ownership, edit, delete, or re-share permission. If the owner updates the Memory, the old revision grant no longer exposes the new revision until it is explicitly shared again. Forgetting the source Memory removes access for all recipients.

Shared Personal Memory is treated as attributed evidence. It is not automatically converted into the recipient's Profile or Personal Guidance.

## 6. Room Memory

Room Memory is separate from Personal Memory and is controlled by project and room membership policy:

```text
GET    /api/rooms/{room_id}/memories
POST   /api/rooms/{room_id}/memories
PUT    /api/rooms/{room_id}/memories/{memory_id}
DELETE /api/rooms/{room_id}/memories/{memory_id}
```

Room membership administration:

```text
GET    /api/rooms/{room_id}/members
PUT    /api/rooms/{room_id}/members/{principal_id}
DELETE /api/rooms/{room_id}/members/{principal_id}
```

Personal Memory is never automatically promoted to Room Memory. A direct grant to one user also does not make that Memory safe to use in a room that other participants can read.

## 7. Per-user Profile

Authenticated Web users have principal-scoped Profiles:

```text
GET /api/me/profile
PUT /api/me/profile
```

The Profile keeps environment metadata, preferences and constraints separately for each authenticated principal. Memory evidence shared by another user remains evidence from that user and must not become the recipient's preference/constraint automatically.

The legacy `/api/profile` endpoint is available only in local identity mode.

## 8. Memory projection and revocation

Relevant Memory/Profile information is projected into a turn-local provider context. For authenticated non-local turns the projection is bound to:

- principal;
- project;
- room;
- Memory access generation.

Grant, Memory or policy changes invalidate stale snapshots. The runtime rechecks the projection boundary so a revoked snapshot is not simply reused on a later provider/tool continuation.

The local V2 projection remains enabled by default:

```env
UAGENT_MEMORY_PROJECTION=1
UAGENT_MEMORY_STRICT_SCOPE=1
```

## 9. Entra ID / directory groups

Verified OIDC `groups` claims can feed project/room authorization policy. Group identifiers are authorization inputs, not Memory owners.

When Entra emits a signed group-overage marker, UAG can resolve group IDs at login through Microsoft Graph if the authorization-code exchange returns a delegated access token and `UAGENT_OIDC_GRAPH_SCOPE` includes `GroupMember.Read.All` with tenant consent. The access token is used transiently and is not saved as session or Memory data. Graph calls are restricted to the cloud host matching the verified issuer, redirects are disabled, pagination URLs are validated, and page/group/body limits fail closed. This is login-time resolution, not live membership refresh or immediate revocation.

`UAGENT_DIRECTORY_GROUP_POLICY` can map verified group identifiers to project/room roles, but it is policy configuration, not an identity verifier or directory client. Graph response bytes are bounded while streaming; redirects are disabled and unsafe pagination URLs or size-limit violations fail closed.

## 10. Current limitations at main `dd382cae`

- OIDC sessions are process-local. A process restart signs users out; multi-instance/HA deployments need a durable session design.
- Non-OIDC users can select a membership-approved Project through server-side ProjectContext. Automatic default-Project derivation from a trusted deployment workspace is not implemented.
- Entra group overage is resolved at login through Microsoft Graph with the configured delegated scope and tenant consent. Session-time membership refresh/revocation remains out of scope. Graph response bytes are bounded while streaming; redirects are disabled and unsafe pagination or size-limit violations fail closed.
- Private Web rooms have configurable idle expiry. Active WebSockets, running agents/streams, and pending `human_ask` are protected; expiry removes the room binding, room-scoped Memory, and associated session history. Legacy rooms receive a fresh reconnect grace period during upgrade.
- The Web Memory API closes request-scoped stores on denied and exceptional paths. This is separate from private-room retention.
- Trusted Proxy, OAuth, Windows AD and External modes have resolver/verifier contracts, but production deployments must provide and validate their trusted integration path. They do not silently fall back to `local`.
- Multi-user/shared-room default rollout should follow the isolation and revocation evaluation gates in the V3 architecture rather than being enabled merely because the APIs exist.

## 11. Security checklist

- Use HTTPS for OIDC Web deployments and keep `UAGENT_OIDC_COOKIE_SECURE=1`.
- Do not store passwords, API keys, access tokens, ID tokens or cookies in Memory/Profile.
- Do not treat email, display name, UPN, room ID or browser-supplied owner fields as a stable authenticated ownership key.
- Configure project/room memberships before exposing multi-user Memory APIs.
- Treat `/api/memories` and `/api/profile` as local compatibility APIs; authenticated multi-user clients should use `/api/me/*` and `/api/rooms/*`.
- Re-test isolation and revocation whenever identity, directory, proxy or project-binding configuration changes.
