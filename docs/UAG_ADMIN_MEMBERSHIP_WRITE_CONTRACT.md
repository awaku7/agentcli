# PR-C: UAG project membership write — secure staged implementation

Status: **C0 and C1 implemented; remote write opt-in, C2 Admin signing client pending**.
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

## C1: separate UAG write API (design requirements)

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

## C1 implemented protocol (UAG write API)

C1 is opt-in. UAG provides `POST /api/admin/integration/v1/projects/{project_id}/memberships`, protected by **both** a per-project write-only Bearer token and an Ed25519 operator assertion. It is not a local browser write API.

Set `UAGENT_MANAGEMENT_WRITE_SCOPES_FILE` to an absolute, protected JSON file (Unix owner service/root and mode 0600; Windows validated owner/DACL, symlinks/reparse points forbidden). An example schema with placeholders:

```json
{
  "version": 1,
  "scopes": [
    {
      "instance_id": "11111111-1111-4111-8111-111111111111",
      "project_id": "project-a",
      "principal_id": "UAG-registered-service-admin",
      "token": "REPLACE_WITH_INDEPENDENT_WRITE_SECRET_AT_LEAST_32_CHARS",
      "issuer_id": "trusted-uag-admin-deployment",
      "public_key": "BASE64URL_NO_PADDING_OF_32_BYTE_ED25519_PUBLIC_KEY"
    }
  ]
}
```

The UAG service principal must have an **explicit active manually managed admin** membership in that project; the `principal_id` is never copied from an HTTP header, a UAG Admin username, or the signed human identity. This credential cannot duplicate any read token or the manifest token. The full protected configuration is reloaded and validated per request for prompt revocation; malformed/unreadable files fail closed.

```http
POST /api/admin/integration/v1/projects/project-a/memberships
Authorization: Bearer <independent-write-token>
X-UAG-Actor-Assertion: <base64url-JSON>.<base64url-Ed25519-signature>
Content-Type: application/json

{"action":"grant","target_principal_id":"principal123","role":"editor","expected_revision":1}
```

Revoke uses exactly `{"action":"revoke","target_principal_id":"principal123","expected_revision":1}`. The initial grant of a missing target uses revision 0; revoked target rows retain their revision for re-grant CAS. No extra body keys are accepted.

The Ed25519 signature covers the **exact original UTF-8 JSON bytes before base64url encoding**, not the ASCII characters of the encoded segment. The assertion header encodes those raw JSON bytes as base64url, followed by a dot and the base64url signature. The JSON object contains exactly `issuer_id`, `actor_user_id` (positive integer), `session_version` (nonnegative integer), `audience` (UAG instance UUID), `project_id`, `method` ("POST"), `path` (canonical API path), `body_sha256` (lowercase hex of the exact request bytes), `issued_at`, `expires_at` (Unix seconds, at most 60 s apart) and a fresh random `nonce` (16–128 URL-safe characters). No more than five seconds of future clock skew is allowed; timestamps outside the signed window fail. UAG pins the public key and the trusted `issuer_id`, rather than trusting arbitrary identity assertions.

The local operator ID and signed session version are *audited operator attribution*, not a UAG principal ID. The trusted signing service (future C2) MUST check a live and enabled local admin session, CSRF, approval, and session version **immediately before signing each distinct request**. Reusable pre-signed assertions are forbidden. The C1 UAG verifier cannot query Admin's user database and therefore relies on the pinned issuer to enforce those local conditions.

C1 atomically performs `BEGIN IMMEDIATE` actor UAG admin check, revision CAS, final-manual-admin safety checks, replay nonce insertion, mutation, and audit insertion in the same SQLite transaction. If any step fails, neither nonce nor mutation commits. The resulting audit rows record the UAG authorizing principal *and* signed external issuer/operator/session/nonce. Successful mutations return `api_version`, `instance_id`, `project_id`, `principal_id`, `role`, `status`, `revision` (not history/text). Errors are fail-closed: absent config 404, invalid Bearer or actor signature 401, project/UAG admin denial 403, malformed body 400, stale revision/replay/no-op 409, protected-config/DB/audit failures 503. Responses include `Cache-Control: no-store`. The write request body is capped at 2048 bytes *while streaming*, and oversized payloads receive HTTP 413 before mutation.

Machine-to-machine POSTs without an `Origin` header are exempt from the browser Origin guard **only for this exact membership write route**. The route still requires the separate write Bearer and correctly signed actor assertion. Requests supplying an Origin (including untrusted browser Origins) are subject to the normal Origin policy; all other mutation routes retain their Origin guard.

C1 does not distribute signing private keys, create a signing service, nor enable UAG Admin mutations. Those belong to C2. Without `UAGENT_MANAGEMENT_WRITE_SCOPES_FILE`, write capability is not advertised.

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
