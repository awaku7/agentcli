# PR-C: UAG project membership write — secure staged implementation

Status: **C0 implemented backend only; remote write endpoint disabled by absence**.
UAG Admin PR-B1 (#8) is read-only. This contract intentionally does **not**
equate a UAG Admin local username or `users.id` with a UAG `principal_id`.

## C0: atomic domain backend (this PR)

`runtime/project_membership_mutation.py::apply_membership_change` accepts an
**already-authenticated UAG principal**, fixed project and target, `grant`
with role (`viewer`, `editor`, `admin`) or `revoke`, and a required
`expected_revision`. It uses `BEGIN IMMEDIATE` on the existing MemoryStore
SQLite connection, and checks actor authorization, target revision, active
project, non-directory grant provenance and last-admin floor under the lock.
Manual explicit admin membership is required for the UAG authorization
principal: global admin allowlist or cached directory-policy grants cannot
replace it. It refuses no-op writes, preserves revoked revisions to prevent
ABA, and inserts an audit event in the same transaction. Audit failure rolls
back the membership. C0 adds **no new HTTP endpoint** and does not enable
remote writes by default.

The existing trusted UAG membership APIs are unchanged by C0 and must be
evaluated/hardened before being reused by C1. The C0 service is the intended
backend for future UAG Admin delegated updates, not an override for
`ProjectAccessPolicy` or its identity boundary.

## C1: separate UAG write API (next PR)

Before any `project.membership.write` route is registered/advertised:

1. Use a separate opt-in project **write** credential. Never accept
   `UAGENT_MANAGEMENT_API_TOKEN`, any `UAGENT_MANAGEMENT_READ_TOKEN` or read
   scope token for writes. Scope must be server-side bound to exact
   `instance_id`, `project_id` and verified UAG admin principal. A bearer
   secret alone must **not** prove the individual operator's identity.
2. Require proof of a distinct, explicitly trusted operator identity. A
   defensible design is a short-lived, **Ed25519-signed delegated Admin
   assertion**, with UAG-pinned issuer public key and UAG Admin private signing
   key stored securely *outside* the UAG service. Each assertion includes
   immutable local `actor_user_id`, trusted issuer ID, Admin session version,
   intended audience/instance, project, HTTP method and path, request-body
   digest, issue/expiry times (<=60 seconds) and one-time nonce. The assertion
   is issued **only after** Admin re-checks that the local user is an enabled
   `admin`, has a live session, passes CSRF and has explicitly confirmed the
   mutation. No username-derived principal identity. Reject missing, expired,
   mismatched, duplicated and invalid signatures.
3. On UAG, verify the signed actor assertion **and** separate scoped write
   bearer. Check explicit active UAG project admin service-principal membership
   at mutation time; directory policy cache and global admin flag do not
   substitute. The signed *Admin operator identity* is for human accountability
   and must be recorded alongside the UAG authorizing principal, not confused
   with it.
4. Enforce `expected_revision` in the body, a complete audit event and
   nonce-consumption uniqueness in **the same SQLite transaction** as the
   membership mutation (otherwise retries can replay and invalidate conflict
   guarantees). Disallow demotion or revocation of the final explicitly
   authorized manual project admin. Reject changing directory-managed rows
   through the manual write endpoint. Use 400 malformed, 401 invalid actor or
   token, 403 insufficient scope/admin, 409 stale revision/replay/no-op and
   503 dependency/config failure. No fallback to manifest credential.
5. Keep write config in a bounded, owner/ACL-verified protected file (do not
   follow symlinks, protect Windows DACL, inspect opened handle), rotate and
   revoke write tokens and delegated issuer keys independently. Fail closed if
   any input or identity provider cannot be verified. Disable browser caching
   and prohibit leaking credentials, actor signature or secrets in logs.
6. Integration test interleaved role changes, concurrent revision conflicts,
   replay, invalid issuer/audience/project, local Admin deactivation, UAG
   membership revocation, signed content mismatch, last-admin preservation,
   directory-policy updates, failed audit or nonce insert, and runtime service
   revocation.

## C2: UAG Admin client/UI (after C1)

- Keep write keys separate from per-project **read** connection rows, require
  explicit admin approval per operation, and hold signing secrets only in UAG
  Admin. Never rely on cached read rights to authorize writes.
- Render project membership revision for optimistic CAS; after submission show
  UAG-confirmed outcome only. Refresh membership list after a successful write,
  handle 409 and 403 precisely, log local audit with the immutable local
  `user_id` and UAG returned audit reference.
- Do not enable the mutate controls until the target UAG explicitly advertises
  `project.membership.write` and signed-actor verification succeeds.

## Migration/compatibility

Read-only connections and user grants stay separate from write authority. No
automatic migration of old read tokens to write, and no shadow authorization
through local role names. Old unauthenticated mutation shapes are not part of
the C1 contract (backward compatibility is not a requirement).
