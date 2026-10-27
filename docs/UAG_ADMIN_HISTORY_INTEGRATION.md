# Scoped management session metadata API (v1)

The existing management manifest credential (`UAGENT_MANAGEMENT_API_TOKEN`) remains **manifest-only**. Session metadata requires its **own** secret and an explicit server-side identity/project scope.

Set these only in the UAG Web service's private secret environment:

- `UAGENT_MANAGEMENT_READ_TOKEN`: independent random secret, at least 32 UTF-8 bytes.
- `UAGENT_MANAGEMENT_READ_PRINCIPAL`: trusted UAG principal for which session metadata is requested.
- `UAGENT_MANAGEMENT_READ_PROJECT_ID`: exact UAG project ID to permit.

The configured principal must have an **explicit, active, non-directory** `viewer` / `editor` / `admin` membership in the named active project under UAG's `ProjectAccessPolicy`. Cached directory-policy memberships are deliberately rejected because this bearer request has no authenticated directory identity with which to refresh revoked group access. Being listed in `UAGENT_ADMIN_PRINCIPALS` alone does **not** grant this service access: an explicit project membership is still required. No principal/project identity is accepted from the bearer caller. The endpoint additionally limits sessions to records whose `sessions.project` **and** `sessions.principal_id` exactly match those fixed settings. Existing sessions whose stored project label does not match the UAG project ID will not be returned. This conservative limit is intentional: project membership alone must not expose another user's private-room session metadata.

After setting the values and enabling the session store, the manifest advertises `session.metadata.read`.

```http
GET /api/admin/integration/v1/sessions?project_id=<exact-project-id>&limit=50
Authorization: Bearer <separate-read-token>
```

Only the session ID, project ID, `recorded` state and UTC creation/update times are returned. No conversation text, instruction, summary, room ID, path or message content is selected. Response includes `api_version: "1"`, `instance_id`, `items` and an opaque `next_cursor` for pagination (up to 100 items per page).

Unconfigured reads return 404, malformed configuration returns 503, missing/wrong bearer returns 401, project mismatch or denied membership returns 403, and invalid cursors return 400. A database or policy outage fails closed. The authorization database is opened with SQLite `mode=ro` for every read, without triggering MemoryStore schema initialization/migrations or modifying permissions. If the access database is absent, the API denies the request. Project membership can be provisioned/revoked via existing trusted project administration APIs. This credential does not authorize user/admin UAG endpoints or project membership writes.

The task history store does not yet provide a guaranteed project ownership key, so **no task-history capability** is advertised in this phase. The API is opt-in and disabled by default.

## Project membership metadata (read only)

When the independent management read credential is configured, the manifest
advertises `project.membership.read`. The fixed service principal must have an
explicit, active **admin** membership in the configured active project. Neither
`UAGENT_ADMIN_PRINCIPALS` nor a cached directory-policy membership can replace
that grant.

```http
GET /api/admin/integration/v1/projects/<configured-project-id>/members?limit=50
Authorization: Bearer <separate-read-token>
```

The response contains `api_version`, `instance_id`, `project_id`,
`members`, and `next_cursor`. Every member contains only `principal_id`,
`role` and `revision`. Pagination is sorted by principal ID and limited to
100 items per request. The opaque-in-purpose `cursor` equals the previous
page's final principal ID and does not grant access.

Directory-policy rows reflect the last trusted directory sync and may become
stale; this endpoint does not claim to refresh directory authorization. The
SQLite store is opened read-only, and the endpoint cannot write permissions.
Failures are fail-closed: absent read config 404, malformed config 503,
invalid bearer 401, unauthorized project/admin 403, and database failure 503.
No UAG Admin screen or permission-writing API is added in this phase.


## Multiple independent project read scopes (opt in)

Legacy `UAGENT_MANAGEMENT_READ_TOKEN`, `UAGENT_MANAGEMENT_READ_PRINCIPAL`
and `UAGENT_MANAGEMENT_READ_PROJECT_ID` continue to define **one fixed
project and service principal** with both read capabilities. Existing clients
and the response format do not change.

For multiple projects on **one UAG Web instance**, configure
`UAGENT_MANAGEMENT_READ_SCOPES_FILE` as the **absolute path** to a protected
UTF-8 JSON file **outside source control**. Do not place it in the public
repository, commit it, log it, or serve it as a static asset. On Unix set file
permissions to `0600` and set the file owner to the UAG service UID
(or root); restrict parent directory write permissions. UAG checks
the owner/mode on the **opened file descriptor** and refuses a leaf
symlink. On Windows the service checks the **opened handle's DACL and owner**
and fails closed unless effective allow ACEs name only the current service
principal, local SYSTEM or built-in Administrators. Avoid inheriting
`Everyone`, `Authenticated Users`, `Users` or service-unrelated allow
ACEs. Windows validation uses pywin32; if the security APIs are
unavailable or the ACL is unsafe, reads fail closed instead of ignoring ACLs.
Keep tokens in your
secret distribution mechanism and rotate them by atomically replacing the
protected file. The file is read per request so changes and revocations do not
require restarting the Web service. Example schema (replace all placeholders
with real secrets, and use the UAG Web instance's actual UUID):

```json
{
  "version": 1,
  "scopes": [
    {
      "instance_id": "12345678-1234-5678-1234-567812345678",
      "token": "<independent-random-token-at-least-32-ascii-characters>",
      "principal_id": "trusted-service-operator-for-project-b",
      "project_id": "project-b",
      "capabilities": ["session.metadata.read", "project.membership.read"]
    }
  ]
}
```

Each token is independently bound on the server to **exactly one**
`(instance_id, project_id, principal_id, capabilities)` tuple. Project ID
or principal supplied in a request cannot change that binding. The manifest
advertises the union of enabled **read-only** capabilities; a specific token
still must possess the requested capability and pass the UAG project policy.
One UAG Admin `project_read_connection` should store one encrypted token
per (`instance_id`, `project_id`); never reuse a token across projects.

The file allows up to 64 records and 256 KiB; only
`session.metadata.read` / `project.membership.read` are valid capabilities.
Duplicate tokens (including collisions with the legacy read token **or
the manifest-only `UAGENT_MANAGEMENT_API_TOKEN`**), unknown
fields/capabilities, incorrect instance IDs, untrusted file ownership, unsafe Unix file modes,
unsafe Windows DACLs or malformed/missing files fail closed with HTTP 503; neither service token nor
file path is included in the HTTP response. Absent config returns 404.
Unknown bearer tokens return 401, and an authenticated token with a wrong
project or insufficient capability returns 403. The original manifest bearer
credential remains manifest-only.

For session metadata, the UAG service principal must retain an **explicit
active non-directory viewer/editor/admin membership**, and only its own
sessions for the configured project are returned. Membership listing still
requires that principal's **explicit active non-directory project admin
membership**, checked on every page. A global UAG admin setting alone or a
cached directory-policy grant never suffices. Data is queried from existing
SQLite in read-only mode, not copied to UAG Admin, and these bearer tokens
cannot change memberships. This feature does **not** add user impersonation,
write permissions or arbitrary project discovery.

Operators may retain the legacy single scope alongside the scoped file while
migrating, provided every read credential is unique. To revoke the legacy
scope, remove its three env values together (in the UAG Web process); to
revoke a file scope, remove its record or rotate the token and atomically
replace the file. Avoid updating a live JSON file in place, because readers
will fail closed on a partially written file.
