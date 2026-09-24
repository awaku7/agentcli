# UAG v0.7.14 implementation review

Baseline: `v0.7.13...v0.7.14` (`9dff4735e9e861587d8db0700b08ccad667f7e08` -> `9d9b25aee5ec67dc7fb321ee61f45ee332a65115`).
The release contains 75 commits, so this review treats v0.7.14 as a functional milestone rather than a small patch release.

> Follow-up status (2026-09-24): the Web Memory request-lifetime issue identified below has been fixed, and Scheduler durable dispatch now has a SQLite outbox, consumer-dequeue acknowledgement, retry state, event ordering, and explicit orphan reclaim. Identity-bound scheduler reclaim and real multi-process crash-injection testing remain follow-up work.

## Summary

The main architectural change is that Memory V3 is no longer only a design document. The current runtime contains real server-side identity, project, room, grant, profile and projection boundaries. Scheduler isolation also moved from an in-process model to a SQLite-backed cross-process claim/lease model. Model capability decisions continue moving toward `llmcapa` rather than provider/model-name hard-coding.

The implementation is not yet the end state described by the V3 architecture. The important remaining boundaries are deployment-specific identity integration, non-OIDC/multi-project ProjectContext, durable authentication sessions, directory group overage resolution, end-to-end rollout validation, and the remaining identity-bound scheduler recovery work identified below.

Computer Use is an opt-in feature and is intentionally not part of this review's primary product positioning or rollout guidance.

## Implementation status

| Area | Current status | Remaining work |
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
| Web Memory store lifetime | Request-boundary cleanup implemented for denied/exception paths | Keep resource-lifetime regression tests |
| Scheduler instance isolation | Implemented: instance ownership, SQLite claims/leases, reclaim, WAL | Continue multi-process failure injection and identity-bound recovery |
| Scheduler durable dispatch | Implemented core: SQLite outbox, atomic schedule/event commit, dequeue ACK, retry, ordering, explicit reclaim | Identity-bound reclaim service, real process-kill matrix, run-store cross-process strategy, retention |
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

## Code review findings and follow-up status

### A. SQLite store lifetime on authorization failure — resolved

The original review found that Web Memory helpers could open a Memory store and fail authorization before returning the handle to the route-level `finally` block.

The Web request boundary now tracks opened Memory stores and closes them even when authorization fails before the helper returns. Denied Personal Memory and Room Memory paths have regression coverage. The developer documentation was also updated to describe the request-lifetime rule.

### B. Scheduler queue handoff — core durable dispatch implemented

The original v0.7.14 flow created a run and finalized/deleted the schedule before placing its event on the in-process sink. A sink failure could therefore leave persisted run/schedule state without an execution event.

The follow-up implementation adds a SQLite `scheduler_events` outbox. Schedule finalization and outbox insertion are committed in the same transaction. Dispatch rows carry a target scheduler instance, retry/lease state, attempt count, last error, and deterministic event key.

For the normal CLI/GUI queue, an outbox event is acknowledged when the consumer dequeues it rather than when `put()` succeeds. A process failure before dequeue therefore leaves durable pending state that can be explicitly reclaimed and re-dispatched. Same-run event ordering prevents a later execution event from overtaking an earlier pending notice.

Delivery is deliberately **at least once**. `SchedulerRun` remains the execution state machine, and the persisted run id/idempotency key is used to prevent the same run from being executed twice. Outbox `delivered` means that the event reached the consumer, not that the run completed.

Remaining work is identity-bound reclaim: before moving an orphaned schedule/event to a new process owner, the current session, principal, project, room, and authentication configuration must be revalidated. Real multi-process process-kill injection also remains.

### C. Lease semantics — clarified

Schedule claim lease, dispatch-event lease, queue delivery, and run execution are separate concepts:

- the schedule claim lease protects due-schedule selection;
- the outbox lease protects dispatch of one pending event;
- `delivered` records consumer acknowledgement;
- `SchedulerRun` records queued/running/terminal execution state.

None of these alone implies exactly-once event delivery. Documentation now states the at-least-once dispatch guarantee and the separate run-idempotency boundary.

### D. Developer documentation lag — resolved for the identified V3 status

`src/uagent/docs/DEVELOP.md` was updated from the older staged V3 wording to the current authenticated Web Memory implementation. Current Memory, Web identity, scheduler and user-facing timer documentation now separate implemented behavior from remaining rollout work.

`docs/UAG_MEMORY_ARCHITECTURE_V3.md` remains the architecture/invariants document; this review and the implementation roadmap carry the current implementation checkpoint.

## Documentation structure

1. Keep `UAG_MEMORY_ARCHITECTURE_V3.md` as the architecture/invariants document.
2. Use this file as the v0.7.14 review plus post-release follow-up checkpoint.
3. Use `MEMORY.md` / `MEMORY.ja.md` for current local/V3 Memory behavior.
4. Use the Web identity/Memory guides for authenticated project, sharing, Profile and Room behavior.
5. Use `SCHEDULER_INSTANCE_ISOLATION_DESIGN.ja.md` for scheduler ownership, claim, outbox, delivery and reclaim invariants.
6. Use `SET_TIMER.md` / `SET_TIMER.ja.md` for user-facing timer behavior and delivery guarantees.
7. Keep Computer Use documented as an optional feature, but do not use it as the primary explanation of these changes.

## Recommended next implementation order

1. Add identity-bound scheduler reclaim with session/principal/project/room/authentication revalidation.
2. Add real multi-process scheduler crash-injection tests and decide the cross-process `SchedulerRunStore` strategy.
3. Implement non-OIDC/multi-project server-derived ProjectContext.
4. Add a directory API adapter for Entra group overage and revocation freshness.
5. Decide durable OIDC session storage for multi-instance Web deployments.
6. Run the full Memory V3 isolation/revocation evaluation matrix in real deployment modes.
7. Only then revisit whether authenticated multi-user projection/shared-room Memory should become default outside explicitly configured deployments.
