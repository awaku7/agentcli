# UAG v0.7.14 implementation review

Baseline: `v0.7.13...v0.7.14` (`9dff4735e9e861587d8db0700b08ccad667f7e08` -> `9d9b25aee5ec67dc7fb321ee61f45ee332a65115`).
The release contains 75 commits, so this review treats v0.7.14 as a functional milestone rather than a small patch release.

## Summary

The main architectural change is that Memory V3 is no longer only a design document. The current runtime contains real server-side identity, project, room, grant, profile and projection boundaries. Scheduler isolation also moved from an in-process model to a SQLite-backed cross-process claim/lease model. Model capability decisions continue moving toward `llmcapa` rather than provider/model-name hard-coding.

The implementation is not yet the end state described by the V3 architecture. The important remaining boundaries are deployment-specific identity integration, non-OIDC/multi-project ProjectContext, durable authentication sessions, directory group overage resolution, end-to-end rollout validation, and a few reliability/resource-lifetime issues identified below.

Computer Use is an opt-in feature and is intentionally not part of this review's primary product positioning or rollout guidance.

## Implementation status

| Area | Current status in v0.7.14 | Remaining work |
|---|---|---|
| Identity / TurnContext | Implemented | Continue regression coverage across every host and sub-agent path |
| OIDC Web login | Implemented: Authorization Code + PKCE, discovery/JWKS verification, server-side opaque sessions, cookie-backed WebSocket identity | Session store is process-local; production persistence/HA policy remains |
| Authentication management | Implemented safe status/config validation and invalidation fingerprinting | Full management UI and deployment-specific operations remain |
| Personal Memory V3 store | Implemented with `owner_id`, audience, revision, read grants and access generation | Migration/rollout policy for legacy deployments remains |
| Direct user-to-user sharing | Implemented as revision-bound read grants | Product/UI workflow and larger evaluation matrix remain |
| Identity-bound Memory Projection | Implemented for authenticated non-local turns | Multi-user default decision still requires deployment evaluation |
| Principal-keyed Profile | Implemented for Web `/api/me/profile` and projection loading | Confirm every profile extraction/write path stays actor/principal scoped |
| Room Memory / Room policy | Implemented | Management UI/audit surface remains incomplete |
| Project membership / Room binding | Implemented | Non-OIDC/multi-project request binding remains |
| Entra groups | Verified signed group claims are carried into authorization policy | Group overage needs a trusted directory API adapter |
| Trusted Proxy / OAuth / Windows AD / External | Resolver/verifier contracts exist; token and trusted-proxy boundaries exist | Deployment-specific verification and real-environment integration remain |
| Legacy `/api/memories` and `/api/profile` | Restricted to local identity mode | Keep clearly documented as compatibility APIs |
| Scheduler instance isolation | Implemented: instance ownership, SQLite claims/leases, reclaim, WAL | Durable queue handoff semantics still need hardening |
| OS scheduler payload | Hardened with opaque IDs, one-shot consumption, size/path/permission validation | Continue platform-specific validation, especially Windows ACL behavior |
| Native tool search / token parameters | Gated using `llmcapa` capabilities | Keep capability catalog/version testing strong |
| Explicit Skill selection | Fixed | Preserve explicit user selection over automatic narrowing |
| Token count cache | Fixed after message insertion/replacement | Keep prefix-cache mutation tests |
| CI | Documentation-only skip and duplicate pytest removal implemented | Preserve required security/regression suites as non-skippable where appropriate |

## Memory V3: what is actually connected now

The following paths are connected in the current implementation and should no longer be documented as future-only:

- `runtime/memory_access.py`: authenticated `MemoryAccessContext`, scoped SQL filtering, revision-bound read grants, update/forget/revoke behavior.
- `runtime/memory_projection.py`: principal/project/room/access-generation bound snapshots, scoped V3 retrieval, principal profile loading and stale snapshot rejection.
- `profile_manager.py`: principal-keyed profile files for authenticated users.
- `web_impl/routes_api.py`: `/api/me/memories`, sharing/grant APIs, `/api/me/shared-memories`, `/api/me/profile`, project membership, project context, room membership and room memory APIs.
- `web_impl/routes_auth.py`: OIDC login/callback/logout and safe authentication status endpoints.
- `project_access.py` / `room_access.py`: server-side authorization policy and generation changes.
- WebSocket/worker identity propagation: authenticated connection identity is converted into turn-local identity instead of accepting an owner from browser/model payloads.

The legacy local API is deliberately kept separate. `/api/memories` and `/api/profile` reject non-local identities rather than becoming alternate multi-user access paths.

## Remaining Memory / identity boundaries

### 1. Non-OIDC and multi-project ProjectContext

HTTP project authorization currently relies on either:

- configured single-project `UAGENT_MEMORY_PROJECT`, or
- project selection bound to the OIDC server-side session.

The architecture still needs a server-derived project/workspace binding for non-OIDC multi-user deployments. A client-provided `project_id` must remain only a selector and never become an authorization grant.

### 2. Directory group freshness and Entra overage

OIDC group claims are accepted only after token verification and malformed/overage claims fail closed. This is the correct security default. A production Entra deployment that exceeds token group limits still needs a trusted directory API adapter and a freshness/revocation policy.

### 3. Authentication session durability

OIDC sessions are intentionally process-local today. Restarting the process invalidates them. Before multi-instance/HA Web deployment, choose an explicit durable session design with expiration, configuration-fingerprint invalidation and revocation semantics preserved.

### 4. Rollout gates

Project isolation and active-revocation regression tests are present, but multi-user default-on should still depend on deployment-specific evaluation for:

- identity leak count;
- audience violations;
- profile attribution leaks;
- stale snapshot reuse after membership/grant changes;
- directory membership revocation;
- single-user compatibility regression.

## Code review findings that should become follow-up work

### A. SQLite store lifetime on authorization failure

`web_impl/routes_api.py` opens the Memory store inside `_personal_store()` and `_room_service()` before all project/membership/binding checks have completed. The caller closes the store only after the helper returns successfully. If `_project_id()`, directory-policy synchronization, project membership checks or room binding checks raise, the helper can exit without an explicit `store.close()`.

Recommended fix: make the helper itself exception-safe, or use a context manager/service object that owns the store lifetime. Add tests that repeatedly exercise denied requests and verify connections are closed.

### B. Scheduler queue handoff is not yet durable

`SchedulerService._fire_due_items()` creates the run and finalizes/deletes the schedule before `_emit()` places the event on the sink. `_emit()` intentionally swallows sink exceptions. Therefore a queue failure can leave a persisted run and an advanced/deleted schedule without the execution event being delivered.

The SQLite claim/lease changes solve competing scheduler instances, but they do not by themselves provide durable delivery from the scheduler store into the execution queue.

Recommended fix: use an outbox/dispatch state, or keep the claim/run pending until queue acceptance is confirmed. Recovery should be able to re-dispatch a persisted pending run without producing duplicate execution.

### C. Lease semantics should be documented precisely

The new claim lease protects schedule selection across processes. It is not an execution lease for the full task duration because the schedule claim is finalized before the queued task executes. Documentation should avoid implying exactly-once execution solely from the claim table.

### D. Developer documentation lag

`src/uagent/docs/DEVELOP.md` still contains an older V3-4 statement saying Web API, projection, Profile, response delivery and continuation invalidation are not connected. That statement is stale in v0.7.14. The current source tree already connects most of those paths.

`docs/UAG_MEMORY_ARCHITECTURE_V3.md` also carries implementation-status text anchored to earlier PR/commit baselines. The architecture remains useful, but implementation status should point to this review/current release status rather than treating PR #60 as the latest checkpoint.

## Documentation actions for v0.7.14

This review recommends the following documentation structure:

1. Keep `UAG_MEMORY_ARCHITECTURE_V3.md` as the architecture/invariants document.
2. Use this file as the release-level implementation review/status checkpoint.
3. Update `MEMORY.md` to describe both local V2 compatibility and authenticated V3 Web behavior.
4. Add a user-facing Web identity/Memory guide with OIDC setup, project binding, Personal/Room/shared Memory APIs, and current limitations.
5. Keep Computer Use documented as an optional feature, but do not use it as the primary explanation of what changed in v0.7.14.

## Recommended next implementation order

1. Fix Memory Web API store lifetime on failed authorization paths.
2. Make scheduler run dispatch durable across sink/process failures.
3. Implement non-OIDC/multi-project server-derived ProjectContext.
4. Add a directory API adapter for Entra group overage and revocation freshness.
5. Decide durable OIDC session storage for multi-instance Web deployments.
6. Run the full Memory V3 isolation/revocation evaluation matrix in real deployment modes.
7. Only then revisit whether authenticated multi-user projection/shared-room Memory should become default outside explicitly configured deployments.
