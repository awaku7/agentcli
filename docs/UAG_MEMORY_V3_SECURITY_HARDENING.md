# Memory v3 security hardening

Current source baseline: **main `6f848f2069cc9e9365d3a56d6dbb6419dbd1becc` (v0.7.15 series, after PR #75)**.

This document records the security state rechecked against that main revision. The v0.7.14 findings remain a historical review in [UAG v0.7.14 implementation review](UAG_0_7_14_IMPLEMENTATION_REVIEW.md); do not treat its unclosed-at-the-time items as the current remaining-work list.

## Implemented hardening

- [x] Make project authorization server-controlled rather than trusting an arbitrary request `project_id`.
- [x] Bind OIDC project selection to the server-side authenticated session.
- [x] Re-check Memory access generation before provider calls, streamed response delivery and tool-loop continuation; stale/revoked projection state is rejected.
- [x] Expose revision-bound Personal Memory read grants through `/api/me/shared-memories` and grant-management APIs.
- [x] Isolate authenticated Profile storage by principal.
- [x] Add project membership, room-to-project binding and Room membership/policy checks.
- [x] Restrict legacy `/api/memories` and `/api/profile` to local identity mode.
- [x] Add project-isolation and active-revocation regression coverage.
- [x] Carry Entra group IDs only from verified OIDC claims; resolve signed Entra group-overage markers through Microsoft Graph when the delegated Graph scope is configured, otherwise fail closed.
- [x] Bind non-OIDC project selection to principal, authentication configuration and expiry in a server-side ProjectContext store; verify membership at selection and use.
- [x] Reconcile only directory-derived memberships against the current mapping; preserve manual membership and downgrade stale directory admin roles.
- [x] Close request-scoped Web Memory stores on success, denial and exception paths.
- [x] Add safe authentication status/configuration validation and invalidate stale OIDC/WebSocket identity after security-sensitive configuration changes.

## Project authorization decision

The project boundary is **server-bound `ProjectContext` plus server-side project membership policy**. A client-supplied `project_id` is only a selector that must match the bound context; it is never an authorization grant.

Current implementation:

- fixed single-project deployments can bind through `UAGENT_MEMORY_PROJECT`;
- OIDC sessions can bind an authorized project through `/api/project-context`;
- authenticated non-OIDC users can select a membership-approved project through an opaque ProjectContext cookie backed by server-side SQLite, bound to principal, authentication configuration and expiry;
- each request re-checks the current project policy; Project memberships use viewer/editor/admin-style role checks;
- Room IDs are persisted as bindings to exactly one Project before Room Memory is used;
- Project/Room membership and directory policy changes participate in access-generation invalidation;
- directory groups are policy inputs, never Memory ownership keys.

Remaining project-context work:

- deployment-specific automatic derivation of a default HTTP ProjectContext from an authenticated workspace is not implemented;
- browser-supplied `project_id` remains a selector only and never grants access.

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

OIDC sessions remain process-local in the v0.7.15-series main baseline. Process restart signs users out. Before multi-instance/HA rollout, define a durable session store that preserves expiration, revocation and configuration-fingerprint invalidation semantics.

Enterprise identity modes (`oauth`, `trusted_proxy`, `windows_ad`, `token`, `external`) use explicit resolver/verifier contracts and do not silently fall back to `local`. Deployment-specific verification is still required where the core cannot establish the trust boundary itself.

## Directory groups / Entra

Verified group claims and Graph-resolved Entra overage group IDs may be mapped to Project/Room roles. Deployments without a custom policy adapter may use `UAGENT_DIRECTORY_GROUP_POLICY` as configuration/bootstrap mapping, for example:

```json
{"groups":{"engineering":{"projects":["demo"],"rooms":{"room-x":"editor"}}}}
```

This mapping is not an AD/Entra directory client. For Entra overage, the OIDC callback uses the access token from the same authorization-code exchange only when `UAGENT_OIDC_GRAPH_SCOPE` includes `GroupMember.Read.All`; it maps the verified Entra issuer to an allowlisted Graph host and rejects redirects or unsafe pagination URLs. Access tokens are not persisted. Overage resolution fails closed on missing consent/scope, request failure, malformed data, or configured limits.

At main `6f848f20`, the Graph size check occurs after the full response body is buffered, so it is not an actual receive-memory bound. The result is fetched at login; it does not provide session-time membership refresh or immediate revocation. A generalized directory adapter and membership freshness/revocation policy remain future work.

## Resolved v0.7.14 finding: Web Memory DB lifetime

The v0.7.14 review found that denied `/api/me/*` and Room API paths could raise before a caller received the opened SQLite Memory store and closed it. This resource leak (not an authorization bypass) was fixed in merged PR #72: the Web request boundary tracks and closes opened Memory stores on success, denial and exception paths. Regression coverage verifies cleanup on denied requests. The historical finding and review-time state remain in [UAG_0_7_14_IMPLEMENTATION_REVIEW.md](UAG_0_7_14_IMPLEMENTATION_REVIEW.md).

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

## Remaining hardening / rollout work at main `6f848f20`

1. Add safe idle TTL / eviction and persistent cleanup for private Web rooms without breaking reconnect, active WebSocket, agent/streaming or pending `human_ask` behavior.
1. Stream Entra Graph responses and enforce the response-byte ceiling before buffering can exceed it.
1. Add automatic workspace-derived default ProjectContext where deployments require it; retain membership checks for user-selected projects.
1. Define session-time directory membership freshness/revocation and generalized non-Entra Directory API adapters.
1. Decide and implement durable OIDC sessions before multi-instance/HA Web rollout.
1. Validate Trusted Proxy / Windows IWA / OAuth / External adapters in their real trust boundaries.
1. Run the complete V3 isolation/revocation/migration/single-user-regression gate before changing multi-user defaults.

The v0.7.14 Web Memory store-lifetime item is resolved; it is not part of this remaining-work list.

The existence of the APIs is not itself approval to make authenticated multi-user or shared-room Memory universally default-on.
