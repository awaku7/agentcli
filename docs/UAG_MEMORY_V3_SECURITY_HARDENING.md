# Memory v3 security hardening

Current baseline: **uag v0.7.14 / `9d9b25aee5ec67dc7fb321ee61f45ee332a65115`**.

This document tracks security hardening discovered by comparing `docs/UAG_MEMORY_ARCHITECTURE_V3.md` with the implemented runtime. The release-level code review is recorded in [UAG v0.7.14 implementation review](UAG_0_7_14_IMPLEMENTATION_REVIEW.md).

## Implemented hardening

- [x] Make project authorization server-controlled rather than trusting an arbitrary request `project_id`.
- [x] Bind OIDC project selection to the server-side authenticated session.
- [x] Re-check Memory access generation before provider calls, streamed response delivery and tool-loop continuation; stale/revoked projection state is rejected.
- [x] Expose revision-bound Personal Memory read grants through `/api/me/shared-memories` and grant-management APIs.
- [x] Isolate authenticated Profile storage by principal.
- [x] Add project membership, room-to-project binding and Room membership/policy checks.
- [x] Restrict legacy `/api/memories` and `/api/profile` to local identity mode.
- [x] Add project-isolation and active-revocation regression coverage.
- [x] Carry Entra group IDs only from verified OIDC claims and fail closed on malformed/overage claims.
- [x] Add safe authentication status/configuration validation and invalidate stale OIDC/WebSocket identity after security-sensitive configuration changes.

## Project authorization decision

The project boundary is **server-bound `ProjectContext` plus server-side project membership policy**. A client-supplied `project_id` is only a selector that must match the bound context; it is never an authorization grant.

Current implementation:

- fixed single-project deployments can bind through `UAGENT_MEMORY_PROJECT`;
- OIDC sessions can bind an authorized project through `/api/project-context`;
- Project memberships use viewer/editor/admin-style role checks;
- Room IDs are persisted as bindings to exactly one Project before Room Memory is used;
- Project/Room membership and directory policy changes participate in access-generation invalidation;
- directory groups are policy inputs, never Memory ownership keys.

Remaining project-context work:

- non-OIDC multi-user / multi-project HTTP requests still need a trusted server-derived workspace/project binding;
- browser-supplied `project_id` must remain a selector only in those future integrations as well.

## Memory / sharing boundary

SQLite V3 Memory stores:

- `owner_id` and explicit audience information;
- stable `memory_id` and revision;
- revision-bound read grants;
- transactional access-generation changes.

A recipient read grant does not grant edit, delete or re-share permission. Updating a source Memory does not silently extend an old grant to a new revision. Forgetting a source removes its grants.

Authenticated projection loads only records authorized for the current principal/project/room. Snapshots bind identity and access generation so an earlier snapshot is rejected when the relevant access state changes.

Shared Personal Memory remains attributed evidence. It must not become the recipient's Personal Profile/Applicable Guidance automatically.

## Authentication boundary

OIDC Web authentication currently provides:

- browser-bound Authorization Code + PKCE transactions;
- provider discovery/JWKS and ID-token verification;
- opaque server-side session cookie;
- WebSocket identity inheritance;
- safe `/api/auth/status` and administrator status output;
- authentication configuration fingerprinting and session invalidation.

OIDC sessions are intentionally process-local in v0.7.14. Process restart signs users out. Before multi-instance/HA rollout, define a durable session store that preserves expiration, revocation and configuration-fingerprint invalidation semantics.

Enterprise identity modes (`oauth`, `trusted_proxy`, `windows_ad`, `token`, `external`) use explicit resolver/verifier contracts and do not silently fall back to `local`. Deployment-specific verification is still required where the core cannot establish the trust boundary itself.

## Directory groups / Entra

Verified group claims may be mapped to Project/Room roles. Deployments without a custom adapter may use `UAGENT_DIRECTORY_GROUP_POLICY` as configuration/bootstrap mapping, for example:

```json
{"groups":{"engineering":{"projects":["demo"],"rooms":{"room-x":"editor"}}}}
```

This mapping is not an AD/Entra directory client.

Entra OIDC group-overage markers fail closed today. Production deployments that need overage support must add a trusted directory API adapter and define:

- how the authenticated principal is correlated with the directory request;
- membership cache lifetime/freshness;
- revocation propagation;
- failure behavior when directory access is unavailable.

## Additional v0.7.14 review finding: Web Memory DB lifetime

`web_impl/routes_api.py` creates a Memory store inside `_personal_store()` and `_room_service()` before every project/membership/binding check has completed. The caller closes the store only after the helper returns successfully. If a helper raises during project binding or authorization, it can exit before handing the store back to the caller for explicit close.

This is a resource-lifetime hardening issue rather than an authorization bypass: the failing request is still denied, but repeated denied requests should not be allowed to accumulate SQLite connection resources.

Follow-up requirement:

- make the helper exception-safe or use an owning context manager/service object;
- add regression coverage that exercises repeated denied Personal/Room requests and verifies the connection is closed.

## Current rollout gates

The following should remain zero/false in deterministic and deployment-specific validation:

```text
identity_leak_count
audience_violation_count
profile_leak_count
snapshot_identity_mismatch_count
unauthenticated_fallback_count
auth_mode_fallback_count
directory_role_violation_count
unauthorized_shared_memory_use_count
shared_memory_profile_attribution_error_count
revoked_grant_reuse_count
```

Project isolation and active-revocation fixtures exist, but production rollout must also exercise the actual OIDC/directory/proxy environment used by the deployment.

## Remaining hardening / rollout work

1. Fix Web Memory store lifetime on authorization-failure paths.
2. Add server-derived ProjectContext for non-OIDC multi-user/multi-project deployments.
3. Add a trusted directory API adapter for Entra group overage and membership freshness/revocation.
4. Decide and implement durable OIDC sessions before multi-instance/HA Web rollout.
5. Validate Trusted Proxy / Windows IWA / OAuth / External adapters in their real trust boundaries.
6. Run the complete V3 isolation/revocation/migration/single-user-regression gate before changing multi-user defaults.

The existence of the APIs is not itself approval to make authenticated multi-user or shared-room Memory universally default-on.
