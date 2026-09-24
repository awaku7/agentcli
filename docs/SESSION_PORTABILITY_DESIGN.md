# UAG Session Portability Design

Status: Proposed design only\
Baseline: `main` / `6f848f2069cc9e9365d3a56d6dbb6419dbd1becc` (2026-09-24)

## 1. Purpose

Session Portability allows a UAG work session to be moved between UAG installations,
entry points, machines, and LLM providers without treating machine-local runtime state
or authentication state as portable authority.

The initial goal is:

```text
UAG CLI / Web / Desktop
        ↓ export
Portable Session Package (.uags)
        ↓ import
another UAG installation
        ↓
new local session
        ↓
resume with current identity, project policy, memory policy, and provider
```

The important property is not merely chat-log export. A portable session must preserve
enough committed work context to continue the task while re-establishing every security
boundary in the destination environment.

This design deliberately separates **portable committed state** from **live process
checkpoint state**.

## 2. Existing UAG foundations

UAG already has building blocks that should remain the source of truth rather than being
replaced by a second session subsystem.

- `SessionStore` persists sessions, messages, tool calls, summaries, tool results,
  response state, tool context state, agent state, policy decisions, and context
  decisions in SQLite.
- Sessions can be bound to `principal_id` and `room_id` and reject cross-principal /
  cross-room rebinding.
- Stored message and tool data already pass through redaction / sanitization paths.
- `session_resume.py` provides deterministic session selection independently of natural
  language interpretation.
- Artifact storage is separate from the session database and can be referenced by
  durable artifact metadata.
- Memory V3 treats principal, room, project, session, and audience as distinct security
  concepts.

Session Portability therefore acts as an explicit serialization boundary around existing
canonical state. It must **not** copy `sessions.sqlite3` or restore a source database
verbatim.

## 3. Goals

### 3.1 Functional goals

1. Export an idle or committed UAG session into a versioned portable package.
1. Import that package into another UAG installation without requiring the original
   SQLite database.
1. Resume the imported work using the destination's currently selected provider/model.
1. Allow CLI/Web/Desktop to share the same portable format.
1. Preserve durable conversation and useful task provenance without requiring the same
   absolute work directory.
1. Make future remote `push` / `pull` or A2A exchange possible without changing the
   core format.
1. Permit optional artifact transfer without making arbitrary local filesystem paths
   portable authority.

### 3.2 Security goals

1. Import never grants identity, Project, Room, Memory, tool, filesystem, or admin
   permission.
1. Secrets and authentication credentials are never intentionally exported.
1. Imported content cannot become current System/Safety/Policy instructions merely
   because the source package labels it `system` or `developer`.
1. Destination authorization is evaluated from current server-side state.
1. A malformed or malicious package cannot escape the import directory, cause
   unbounded decompression, or silently overwrite an existing session.
1. Import and resume remain fail-closed when required destination authorization cannot
   be established.

## 4. Non-goals for v1

The following are explicitly outside Session Portability v1:

- restoring a Python process, PID, socket, thread, event loop, or file descriptor;
- resuming a tool call in the middle of execution;
- restoring a live MCP/A2A/WebSocket connection;
- moving OIDC/OAuth/browser sessions;
- exporting API keys, access tokens, refresh tokens, cookies, passwords, or other
  credentials;
- preserving provider-side response/conversation IDs as resumable authority;
- guaranteeing that the same model/provider is available at the destination;
- copying the whole Memory database or Profile store;
- treating source `principal_id`, `room_id`, group, role, or Project metadata as an
  authorization grant;
- transparent migration of arbitrary machine-local files;
- remote cloud synchronization or a hosted session registry.

Live migration of executing agents is a separate checkpoint/restore problem and should
not be hidden behind the term Session Portability.

## 5. Core invariants

The existing Memory V3 identity rules continue to apply:

```text
principal_id != room_id != project_id != session_id
```

Additional portability invariants are:

```text
portable package != authentication session
portable package != authorization grant
source session_id != destination session_id
source path != destination path authority
source provider state != destination provider state
historical system message != current system policy
```

An import always creates or resolves a **destination-owned session record**. It does not
adopt the source session's identity binding.

## 6. Portability boundary

### 6.1 Portable by default

The v1 portable core contains:

- normalized committed conversation events;
- session creation/update metadata needed for provenance;
- logical project hint (not an access grant);
- entry-point provenance;
- completed/sanitized tool-call history useful to understand prior work;
- summary information;
- optional references to Memory/artifacts;
- format/version/features metadata;
- integrity digests.

### 6.2 Portable only as hints

These values may be recorded for user experience, but the destination must treat them
as untrusted hints:

- project display name;
- source room label/ID;
- provider and model names;
- source entry point;
- source UAG version;
- artifact original filename;
- tool name/version metadata.

The source `project_key` is derived from machine-local workspace identity and is not a
portable Project grant. Absolute `project_path` is excluded by default because it leaks
machine-local information and is not meaningful on another machine.

### 6.3 Not portable

The exporter must not intentionally serialize:

- raw credentials or environment secrets;
- browser/OIDC session tokens or cookies;
- raw authorization headers;
- source principal credentials or directory claims;
- process-local policy/admin capability;
- live `response_id` continuation state;
- live tool context that assumes a local process/resource;
- active agent execution state;
- locks, leases, queue ownership, timers tied to the source process;
- arbitrary absolute local paths;
- UAG runtime-control markers (for example `[CWD]` events carrying `path`, `prev`, or `resolved` values) that could alter destination workdir or execution state when a session is restored;
- hidden provider caches;
- unredacted command environment variables.

`response_states`, live `tool_context_states`, and `agent_states` are therefore not
restored as executable v1 state. Future extensions may define individually portable
subsets, but they must opt in explicitly and pass the same security review.

## 7. UAG Portable Session Package v1

The proposed filename extension is:

```text
.uags
```

The initial container is ZIP because it is widely supported and allows streaming entry
validation. The extension denotes UAG's schema and security rules; consumers must not
treat an arbitrary ZIP as trusted merely because it has a `.uags` suffix.

### 7.1 Package layout

```text
session.uags
├─ manifest.json
├─ session.json
├─ conversation.jsonl
├─ tool_history.jsonl
├─ references.json
├─ checksums.json
├─ artifacts/                 # optional, opt-in
│  └─ <opaque-artifact-id>
└─ extensions/                # optional, namespaced
   └─ <vendor-or-feature>/...
```

The minimal valid package contains `manifest.json`, `session.json`,
`conversation.jsonl`, `references.json`, and `checksums.json`.

### 7.2 `manifest.json`

Illustrative schema:

```json
{
  "format": "uag-session",
  "schema_version": 1,
  "package_id": "6f755ed1-3fc5-4ced-92d0-a1794a7ac242",
  "created_at": "2026-09-24T10:00:00Z",
  "source": {
    "uag_version": "0.x",
    "source_session_id": "opaque-source-id",
    "entry_point": "cli"
  },
  "checkpoint": {
    "kind": "committed-turn",
    "last_event_sequence": 42
  },
  "required_features": [],
  "optional_features": ["tool-history"],
  "entries": [
    {
      "path": "conversation.jsonl",
      "media_type": "application/x-ndjson",
      "size": 12345,
      "sha256": "..."
    }
  ]
}
```

`package_id` identifies the export operation, not the user. It is used for import
idempotency and audit.

### 7.3 `session.json`

`session.json` contains non-authoritative session provenance and resume hints.

Illustrative fields:

```json
{
  "title": "optional user-visible label",
  "project_hint": "agentcli",
  "source_room_hint": "",
  "source_entry_point": "cli",
  "provider_hint": "openai",
  "model_hint": "gpt-5.x",
  "created_at": "...",
  "last_used_at": "...",
  "summary": "...",
  "imported_from": null
}
```

The following are intentionally absent as authoritative fields:

- destination `principal_id`;
- destination Project membership/role;
- destination Room membership/role;
- access-generation values;
- credentials;
- absolute source workdir.

### 7.4 `conversation.jsonl`

Conversation data uses a canonical UAG event representation rather than a
provider-specific request/response payload.

Each event has, at minimum:

```json
{
  "sequence": 1,
  "event_id": "portable-event-id",
  "kind": "message",
  "role": "user",
  "content": "...",
  "created_at": "...",
  "provenance": "durable-session-history"
}
```

Optional normalized payload metadata may be included when it is known to be portable.
Provider-only fields must be removed or placed in an optional namespaced extension.

#### Runtime-control marker rule

UAG runtime-control events are not portable conversation content. In particular, the
exporter must structurally recognize and omit UAG-generated `[CWD]` system events that
carry `path`, `prev`, or `resolved` fields; those absolute paths must not appear in the
package. The importer must reject or neutralize such control events in package input,
and imported history must never be passed to `_restore_session_workdir()` or any other
routine that interprets runtime markers. Destination workdir comes only from the
current destination configuration / authorized Project policy. A user message that
merely contains the literal text `[CWD]` is not a control event and must not be
rewritten solely because of that substring.

#### System/developer role rule

A package is untrusted input. Therefore a historical event with role `system`,
`developer`, or equivalent must **never** be promoted into the destination's live
System/Safety/Policy layer.

On resume:

1. the destination generates its current System/Safety/Policy normally;
1. current identity/Project/Room policy is resolved normally;
1. current Memory/Profile projection is generated normally;
1. imported privileged-role events are retained only as historical provenance where
   useful, or omitted from active context according to policy;
1. imported user/assistant/tool history is appended as historical conversation context.

This prevents a crafted package from creating a policy-injection channel.

### 7.5 `tool_history.jsonl`

Tool history is optional and informational in v1.

Only completed, sanitized records may be exported. An imported tool call is not
re-executed automatically and cannot restore a capability grant.

Suggested fields:

```text
call_id (package-local)
tool_name
sanitized_args
sanitized_result_or_summary
status
artifact_refs
created_at
```

Environment variables, authorization headers, process IDs, temporary credentials,
open handles, and machine-local continuation tokens are excluded.

### 7.6 `references.json`

References describe dependencies without granting access to them.

Example categories:

```text
memory_refs
artifact_refs
project_hint
external_refs
```

A Memory reference should use stable Memory identity/revision/provenance when available,
but must not make the referenced Memory readable at the destination. The destination
re-authorizes each reference against the current principal, Project, audience, grants,
status, forget state, and access generation before rehydration.

If authorization fails, the reference remains unresolved metadata or is omitted from
active context.

### 7.7 Artifacts

Artifact embedding is **opt-in** in v1.

Default export includes only safe artifact metadata/references. An explicit future UX
such as `--include-artifacts` may copy eligible session-owned artifact payloads under the
package's `artifacts/` directory.

Rules for embedded artifacts:

- never follow symlinks;
- never preserve an absolute source path as extraction target;
- store using an opaque package entry name;
- retain original filename only as metadata after filename sanitization;
- record size and SHA-256;
- enforce per-file and total package limits;
- extract only into destination-controlled storage;
- never overwrite an existing file by source path.

## 8. Export semantics

### 8.1 Committed checkpoint

v1 exports a durable checkpoint, not live RAM state.

The preferred checkpoint boundary is the end of a committed turn after all durable
message/session updates for that turn have completed.

If a session is actively executing, the default behavior should be one of:

1. reject export with `session_busy`; or
1. explicitly export only the last committed checkpoint when the caller requests that
   behavior.

The exporter must not claim that an in-flight tool/sub-agent/provider operation was
captured when it was not.

### 8.2 Export authorization

Before reading a portable session, the current entry point must authorize the caller to
read/export that session using existing server-side identity/session/project rules.

Knowing a `session_id` is not sufficient permission.

For authenticated Web operation, a source package must not bypass Personal/Room/Project
boundaries already enforced by SessionStore and Memory V3.

### 8.3 Snapshot consistency

The exporter should read a transactionally consistent SessionStore snapshot. It must not
mix messages from one checkpoint with metadata/tool state from a later checkpoint.

The implementation may use a read transaction and a session-level activity guard rather
than copying SQLite files.

### 8.4 Secret handling

Existing redaction remains a defense in depth, but portability adds another explicit
boundary.

Before package creation, portable fields must pass the standard secret masking and
history sanitization pipeline. Export should not scan arbitrary unrelated filesystem
files unless the user explicitly opts into artifact embedding.

A package may still contain sensitive conversation content. `.uags` is therefore
sensitive user data even when no credentials are present.

## 9. Import semantics

Import is split into two stages:

```text
untrusted package
      ↓ validate
validated portable snapshot
      ↓ authenticate / authorize destination
new destination SessionStore session
```

No SessionStore mutation occurs before structural, resource-limit, and integrity
validation succeeds.

### 9.1 New session identity

Default import creates a fresh destination `session_id`.

```text
source_session_id --provenance--> destination_session_id
```

The original ID may be stored as provenance, but it is never inserted as the destination
primary key by default. This avoids collisions and prevents source identifiers from
becoming authority.

### 9.2 Principal binding

The package does not authenticate its source user.

The imported session is bound only after the destination resolves the **current**
`IdentityContext`. Source principal/group/role claims, if retained for historical audit,
are not copied into destination authorization state.

For non-local multi-user entry points, unresolved identity means import/resume fails
closed.

### 9.3 Project mapping

`project_hint` is advisory.

The destination must resolve or ask for a local ProjectContext using the same current
membership checks as a normal session. The importer must not create Project membership
from a package field.

Absolute source workdir is not automatically recreated or opened.

A destination mapping may conceptually be:

```text
source project_hint: agentcli
        ↓ user/server selection
current authorized workspace/project
        ↓ membership validation
new session ProjectContext
```

### 9.4 Room handling

v1 does not automatically rejoin a shared Room from package metadata.

A Web import should normally create/use a destination-private session/room owned by the
current principal. Reattachment to an existing shared Room is a later explicit operation
and must pass current Project and Room membership checks.

A package containing a historical Room ID does not prove membership.

### 9.5 Imported actor attribution

Historical actors must not silently become the current principal.

Imported history retains package-local provenance. In particular, historical imported
messages should not be fed into automatic Personal Profile/Memory learning as if the
current importer had just authored them.

New messages written after resume use the destination's real current principal and
normal learning policy.

### 9.6 Atomic import

After validation and destination authorization, creation of the destination session and
its imported durable records should be atomic. A failed import must not leave a partially
resumable session.

## 10. Resume semantics

The resume pipeline is intentionally provider-independent:

```text
current System / Safety / Policy
          ↓
current IdentityContext
          ↓
current Project / Room authorization
          ↓
current applicable Memory / Profile projection
          ↓
portable historical conversation
          ↓
new user request
          ↓
currently selected provider/model
```

This means an OpenAI-origin session can continue using another supported provider when
its canonical history is representable by UAG.

Provider/model fields in `session.json` are only defaults/hints. Unsupported models do
not make an otherwise compatible package invalid.

Provider-side response IDs and caches are not required for v1 resume.

## 11. Memory and revocation semantics

Session portability must preserve the distinction between **exported historical data**
and **live Memory authorization**.

### 11.1 Memory is not copied wholesale

The exporter does not package the Personal Memory database or Profile database.

Stable references may be exported, but any rehydration at the destination requires
current authorization.

### 11.2 Revocation after export

An exported package is an external copy. UAG cannot retroactively erase bytes that have
already been exported and copied outside its control.

Therefore:

- `forget` / grant revocation prevents future live rehydration through UAG;
- it does not claim to claw back text already embedded in a previously exported
  transcript/artifact;
- export should use the current visible/allowed committed state and must not resurrect
  already-forgotten records;
- the user-facing export UX must make this copy boundary clear.

This mirrors the existing distinction between revoking future access and recovering
information already delivered to a user/provider.

## 12. Archive validation and resource limits

`.uags` input is hostile until validated.

The importer must reject at least:

- absolute entry paths;
- `..` path traversal;
- Windows drive/UNC paths;
- symlink/hardlink/device entries;
- duplicate normalized entry names;
- unexpected mandatory top-level files;
- oversized manifest/JSONL lines;
- too many archive entries;
- excessive compressed or uncompressed size;
- unreasonable compression ratios;
- checksum mismatch;
- malformed UTF-8/JSON/JSONL;
- unsupported schema/required feature.

Extraction occurs only after validation and only into destination-controlled storage.
Archive filenames never directly select a destination filesystem path.

Exact limits should be configurable implementation constants with conservative defaults
and regression tests.

## 13. Integrity and authenticity

`checksums.json` and manifest SHA-256 values detect corruption and accidental mismatch.
They do **not** establish package authenticity because an attacker can replace both data
and checksums.

v1 therefore treats every package as untrusted even when checksums pass.

Package signing/attestation may be added as a future extension. A valid signature could
prove origin, but must still not bypass destination authorization.

## 14. Confidentiality

The v1 container format itself does not promise encryption. Portable sessions may
contain confidential conversation/tool/artifact data and must be treated as sensitive
files.

Implementation requirements should include:

- restrictive owner-only file permissions where the platform supports them;
- explicit user choice of export destination;
- no implicit upload to a third-party service;
- documentation that external transfer should use an encrypted channel/storage.

A future encrypted-envelope extension can add passphrase/key-based protection without
changing the inner canonical schema. Future remote `push`/`pull` must require encrypted
transport and appropriate server-side protection.

## 15. Versioning and extensions

`schema_version` is the portable-format major version.

Rules:

1. unknown major/schema version -> reject;
1. unknown `required_features` -> reject;
1. unknown `optional_features` -> ignore safely or preserve opaquely;
1. extension paths are namespaced;
1. extension content cannot override core authorization/security fields;
1. a newer writer must not silently reinterpret an older package's privileged fields.

Example future optional features:

```text
embedded-artifacts
signed-package
encrypted-envelope
portable-tool-state:<tool-namespace>
room-transcript-provenance
```

## 16. Import idempotency and provenance

The destination should record at least:

```text
package_id
package content digest
source_session_id (provenance only)
destination_session_id
imported_at
destination principal scope
resolved destination Project/Room scope
```

Default repeated import of the exact same package is idempotent only within the same
destination authorization scope. The idempotency key includes the authenticated
destination principal, resolved Project, authorized Room (or an explicit no-Room
scope), and package content digest/package ID. Package-global identifiers alone must
never select another principal's imported session.

Before returning a prior destination session, the importer re-checks current principal
ownership and current Project/Room membership. If the caller is not authorized, it fails
closed without revealing whether a matching import exists. Imports in a different
authorized Project/Room scope are independent destination sessions. An explicit
duplicate/copy operation may create another session within the same scope when
requested.

The provenance record must not contain source credentials.

## 17. Proposed service boundary

Implementation should introduce one portability service rather than spreading archive
logic through CLI/Web code.

Conceptually:

```python
class SessionPortabilityService:
    def export_session(...): ...
    def inspect_package(...): ...
    def import_package(...): ...
```

Responsibilities:

```text
SessionStore / ArtifactManager / Memory references
                    ↓
          SessionPortabilityService
                    ↓
       canonical package reader/writer
                    ↓
        CLI / Web / future A2A adapters
```

Entry points remain responsible for authentication, UI, file selection, and presenting
confirmation/errors. The service remains responsible for deterministic validation,
canonicalization, limits, integrity, and portable-state policy.

## 18. Proposed user/API surface

Exact syntax is intentionally non-normative in this design PR. Possible UX:

```text
uag session export <session-id> -o work.uags
uag session inspect work.uags
uag session import work.uags
uag session resume <imported-session-id>
```

Equivalent existing UAG command-style or Web actions may be added later.

Important behavioral contracts are more important than command spelling:

- export requires access to the source session;
- inspect performs no import and does not execute package content;
- import creates a new destination session;
- resume re-evaluates current authorization and current policy;
- artifacts are not embedded without explicit opt-in.

## 19. Provider independence

The canonical format belongs to UAG, not to a provider API.

Provider-specific information should be divided into:

### Portable hints

- provider name;
- model name;
- generation settings that have a clear provider-neutral meaning.

### Nonportable state

- provider response/conversation ID;
- server-side cached context handle;
- provider credential/account identity;
- opaque continuation token;
- provider-specific tool execution state.

On resume, UAG reconstructs the provider request from canonical durable history and the
current runtime context. This is what enables provider switching without pretending that
one provider's private continuation state can be understood by another.

## 20. Shared Room considerations

A shared-room transcript may contain content from multiple actors and may have a broader
or narrower audience than the importer currently has.

For v1, the safe default is:

- export requires current permission to export the source session/transcript;
- actor provenance is preserved as historical metadata;
- import does not enroll the importer into the source Room;
- import does not create Room membership;
- imported multi-actor history is not automatically learned into the importer's Personal
  Profile/Memory;
- continuation occurs in a destination-owned/private context unless an explicit,
  separately authorized Room action is chosen.

Cross-user collaborative handoff can be designed later on top of explicit sharing and
Room policy rather than inferred from possession of a `.uags` file.

## 21. Tool portability

Tools fall into three categories:

### 21.1 History-only

Most tools are history-only in v1. Their completed sanitized arguments/results can help
explain prior work, but no live state is restored.

### 21.2 Artifact-backed

A tool may produce a portable artifact. The artifact can be referenced or explicitly
embedded and re-registered in destination ArtifactManager storage.

### 21.3 Explicit portable-state extension

A future tool may define a versioned, validated portable state contract. Such state must
be namespaced and opt-in; it cannot use generic pickle/object serialization and cannot
carry credentials/capabilities implicitly.

No tool becomes portable merely because its Python object can be serialized.

## 22. Failure model

Import/export errors should use explicit categories suitable for CLI/Web localization,
for example:

```text
session_not_found
session_busy
export_not_authorized
package_invalid
package_too_large
checksum_mismatch
unsupported_schema
unsupported_required_feature
import_not_authorized
project_mapping_required
artifact_rejected
```

No partial success should be reported as a fully resumable session.

## 23. Audit and observability

Security-relevant operations should be auditable without logging package content or
secrets.

Useful fields:

```text
operation = export | inspect | import | resume
package_id
source/destination session IDs where locally known
entry point
result/error class
counts and sizes
artifact count
schema version
```

Do not log conversation bodies, credentials, raw browser tokens, or embedded artifact
content as part of routine portability telemetry.

## 24. Implementation phases

### Phase P1 - canonical v1 export/import

- package schema/types;
- safe ZIP reader/writer;
- SessionStore canonical export;
- fresh-session atomic import;
- import provenance/idempotency;
- provider-independent resume from imported durable history;
- current identity/Project re-authorization;
- no embedded artifacts by default;
- CLI/service-level tests.

### Phase P2 - user experience and artifacts

- CLI/Web inspect/export/import UI;
- explicit artifact embedding;
- destination project/workspace mapping UX;
- private Web session creation after import;
- user-facing portability documentation.

### Phase P3 - collaboration and remote transport

- explicit shared-room handoff policy;
- remote session registry / `push` / `pull` if desired;
- encrypted envelope;
- signing/attestation;
- A2A portability profile;
- selected tool-specific portable-state extensions.

P3 is not required for useful local file portability.

## 25. Required regression tests for implementation PRs

The later implementation must cover at least:

### Round trip

- export committed session -> fresh store import -> canonical messages preserved;
- destination gets a new session ID;
- project/provider hints survive without becoming grants;
- provider can differ on resume.

### Identity/authorization

- source principal ID does not grant destination access;
- source Room ID does not join destination Room;
- source Project ID without current membership fails mapping/resume;
- unauthenticated multi-user import/resume fails closed;
- identical-package imports by different destination principals or Project/Room scopes cannot return one another's sessions;
- a repeated import in the same scope returns a prior session only after current ownership and Project/Room authorization are re-checked;
- imported history is not auto-attributed to current Personal Profile/Memory.

### Policy injection

- crafted imported `system`/`developer` event cannot replace current system policy;
- unknown privileged role does not become trusted policy;
- a crafted `[CWD]` system event cannot change process/destination workdir during import or resume;
- imported history is never sent through runtime workdir-marker restoration; literal user content is preserved without executing marker syntax.

### Secret boundary

- common API key/token/password/cookie patterns are redacted/excluded;
- OIDC/browser session data is absent;
- provider continuation IDs are not restored;
- persisted `[CWD]` runtime events and absolute `path` / `prev` / `resolved` values are absent from default exports.

### Archive safety

- `../` and absolute paths rejected;
- Windows drive/UNC paths rejected;
- symlink/device entries rejected;
- duplicate normalized names rejected;
- oversized entry/package rejected;
- compression bomb ratio rejected;
- malformed JSON/JSONL rejected;
- checksum mismatch rejected;
- unknown required feature rejected.

### Atomicity/idempotency

- failed import leaves no partial destination session;
- repeated identical import resolves idempotently for the same destination principal and authorized Project/Room scope;
- the same package imported by another principal or authorization scope creates an independent destination session and never returns another principal's session;
- an idempotent hit re-checks current ownership and membership before returning the prior session;
- explicit duplicate mode, if implemented, creates a distinct session.

### Memory/artifacts

- revoked/unavailable Memory reference is not rehydrated;
- artifacts are metadata-only by default;
- embedded artifact requires explicit option and lands only in managed destination
  storage;
- source absolute path is never used as extraction destination.

### Activity boundary

- active-session export rejects or explicitly uses the last committed checkpoint;
- package never claims in-flight tool execution is resumable.

## 26. Acceptance criteria for Session Portability v1

v1 is complete when all of the following are true:

1. A completed/idle session can be exported and imported into a fresh UAG state store.
1. The imported work can continue under a different supported provider/model.
1. The destination session receives a new local session ID.
1. No source credential/authentication session is required or restored.
1. Current destination principal/Project policy is evaluated before resume.
1. Possession of the package alone cannot grant Room/Project/Memory/admin access.
1. Imported privileged-role history cannot override current System/Safety/Policy.
1. Absolute source workspace paths are not required for successful import, and crafted `[CWD]` runtime markers cannot change the destination workdir or survive as executable history.
1. Malicious archive paths/resource bombs are deterministically rejected.
1. Optional artifacts are imported only through managed ArtifactManager storage.
1. The importer is atomic; an identical package is idempotent only within the same destination principal and authorized Project/Room scope, with authorization re-checked before returning a prior session.
1. Existing local sessions and existing natural session-resume behavior remain
   compatible.

## 27. Design decisions summary

| Question | v1 decision |
|---|---|
| Copy SQLite DB? | No |
| Preserve source session ID as destination ID? | No, provenance only |
| Portable process checkpoint? | No |
| Portable live tool/MCP state? | No |
| Provider-independent? | Yes, via canonical UAG history |
| Same provider required? | No |
| Restore credentials? | Never |
| Restore source identity/role? | Never |
| Project/Room access from package? | Never; re-authorize destination |
| Copy Memory DB/Profile? | No |
| Memory references allowed? | Yes, re-authorize before rehydration |
| Artifacts embedded by default? | No |
| Shared Room automatically rejoined? | No |
| Imported system/developer content trusted? | No |
| Encryption built into v1 container? | No; sensitive-file handling required, encrypted envelope later |
| Remote push/pull in v1? | No |

## 28. Architectural outcome

Session Portability should make UAG sessions independent of a particular UI, machine,
or LLM provider without weakening the identity and Memory boundaries already introduced
by Memory V3.

The intended abstraction is:

```text
live UAG runtime
     ↓ commit
SessionStore canonical durable state
     ↓ export policy
UAG Portable Session v1
     ↓ hostile-input validation
current destination identity + policy
     ↓ import
new destination SessionStore session
     ↓ fresh context projection
current provider/runtime
```

The `.uags` package is therefore a **portable work-history snapshot**, not a bearer token,
not a permission bundle, and not a serialized running agent.
