# UAG Session Portability v1

`.uag` is an encrypted portable conversation package. It can be imported into a
different installation and continued using that installation's provider and
credentials. There is no plaintext package mode or automatic cloud synchronization.
The existing SQLite session store remains the local source of truth; this feature
does not encrypt that database.

## CLI

Install the core extra (`pip install 'uag[core]'`). These commands use the normal
SessionStore and its `UAGENT_SESSION_STORE_PATH` override:

```sh
uag session export <local-session-id> -o work.uag
uag session import work.uag
uag session resume <new-local-session-id>
```

Export/import prompt for a passphrase without echo; export asks twice. Use a strong,
unique passphrase and communicate it separately from the file. There is no recovery
key. Passphrases are never accepted in arguments, environment variables, chat or
tool calls. A terminal capable of hidden input is required. Export refuses to
overwrite an existing file. Import prints the **new** session ID and does not start
an LLM, restore a directory or execute tools. Resume initializes the destination
normally and adds canonical conversation to its new local instructions.

Interactive CLI also supports:

```text
:sessions export <id> "path with spaces/work.uag"
:sessions import-uag "path with spaces/work.uag"
:sessions resume <new-id>
```

The existing `:sessions load <id>` works too. Legacy `:sessions import` retains
its JSONL behavior but rejects `.uag`; it is not a plaintext portable mode.
Review imported conversation before
continuing: package encryption proves knowledge of a passphrase, not the identity
or trustworthiness of its author. Normal destination tool approval still applies.

## Web API

Web integration is an authenticated API in v1; no new transfer panel is added.
Use HTTPS for remote servers. Passphrases belong only in the JSON request body,
never in URLs, command messages or application/proxy logs. Do not enable request
body logging on these endpoints. Responses carrying packages use `Cache-Control: no-store`.

| Operation | Request | Result |
| --- | --- | --- |
| Export | `POST /api/sessions/{id}/export`, JSON `{ "passphrase": "…" }` | Binary `.uag` download |
| Import | `POST /api/sessions/import`, JSON `{ "passphrase": "…", "package": "<base64 .uag bytes>" }` | New `session_id`, `references_status: unresolved` |
| Resume | `POST /api/me/private-room`, JSON `{ "portable_session_id": "<imported id>" }` | New private `room_id` and `session_id` |

The normal destination ProjectContext/OIDC/configured project selection applies to
resume. Where normal private-room creation permits project selection, `project_id`
may be supplied and is checked against current server-side membership. It is never
taken from the package. Connect to the returned room using the existing WebSocket
flow. Resume makes a new private copy; the imported session is not overwritten.

Authenticated callers can export/resume only their own sessions. A bound Room's
current Room/Project policy is rechecked, including after export encryption.
Imports bind ownership to the destination identity, without binding a Room or
Project. ProjectContext tokens, identity claims and grants are never imported.
Transfer requests are bounded and JSON-only; concurrent crypto requests receive
429 while the process handles another transfer.

## Contents and exclusions

The inner JSON contains `format: uag-session`, integer `version: 1`, `session`,
`conversation` and `references`. Unknown fields are rejected.

- Session metadata: source ID (provenance only), creation timestamp, source entry
  point and a simple project-name hint. No source path or principal is restored.
- Canonical conversation: user/assistant text; text parts of multimodal content
  are retained. Historical tool results become labeled assistant text. Tool calls,
  tool IDs, provider response IDs and native provider state are omitted.
- Memory references (`memory:<id>@<revision>`) and artifact references
  (`artifact://<32-hex-id>`) are inert, unresolved records. They never cause reads,
  downloads, path traversal, local ID lookup or grants during import/resume.
  Reauthorization and an explicit destination binding are necessary to use the
  referenced resource; automatic reference resolution is not implemented in v1.
- System/developer messages, derived Memory/Profile projections, credential
  stores, configuration, attachments and artifact bytes are excluded.
- API keys, OAuth/OIDC tokens, passwords, cookies, authorization headers and
  private keys are not export fields. Export uses an allowlist and conservative
  text redaction (credential-bearing messages, PEM private keys, known secret values
  from environment and structured message/tool fields).

Free-form dialogue can contain an unlabelled password or another arbitrary secret
that no generic filter can recognize. Redaction is defense in depth, not a proof
that arbitrary prose contains no secrets. Do not paste credentials into ordinary
conversation; review sensitive conversations before sharing. Dialogue may also
quote previously authorized information; exporting it is an explicit disclosure
by its owner, not a transfer of access to the original Memory resource.

## Wire format and security invariants

All integers are unsigned big endian. The fixed 65-byte header uses struct
`>10sBBBIII16s12s12s`:

| Field | Bytes / value |
| --- | --- |
| Magic | 10, ASCII `UAGSESSION` |
| Format version | 1, value 1 |
| Crypto suite | 1, value 1 (Argon2id + AES-256-GCM) |
| Argon2 version | 1, value 19 |
| Memory, iterations, lanes | 3 × 4; exactly 65536 KiB, 3, 4 |
| Salt | 16 random bytes |
| DEK wrapping nonce | 12 random bytes |
| Payload nonce | 12 random bytes |

The header is followed by a 48-byte wrapped DEK (32-byte key + 16-byte GCM tag)
and the encrypted JSON payload (including its 16-byte tag). Each export creates a
fresh CSPRNG 256-bit DEK, salt and both nonces. Argon2id derives a 32-byte KEK from
the passphrase's exact UTF-8 encoding, without normalization. No keys/passphrases
are stored. `cryptography>=44.0.2` supplies both primitives; unsupported crypto
backends fail closed without an alternative algorithm.

DEK wrapping authenticates `header || /DEK`. Payload encryption authenticates
`header || wrapped_DEK || /payload`. Both must authenticate before JSON parsing or
any database write. Wrong passphrase and authentication failure share one error.
The v1 reader accepts only the fixed KDF tuple, before running Argon2id. There is
no attacker-controlled KDF cost negotiation. JSON payloads are limited to 16 MiB,
10,000 messages and 10,000 references per type; individual texts to 1 MiB. Duplicate
JSON keys, unknown fields/versions/suites, invalid types and path-like references
are rejected. The package is not an archive; nothing is extracted to disk.

Import validates the entire package, then inserts session, conversation, FTS rows
and inert provenance in one SQLite transaction. A freshly generated local ID is
required; collision fails and rolls back without replacing any existing session.
Repeated imports produce independent sessions. Plaintext package temporary files
are never created. Decrypted content and keys exist in process memory; Python
does not guarantee zeroization, nor protection against an already compromised host.

Non-goals: live processes, in-flight tools, sub-agents, sockets/MCP connections,
agent plans/runtime checkpoints, credential migration, attached file contents,
provider-native continuation, automatic Memory/artifact resolution, signatures,
public-key recipients, passphrase recovery and cloud sync.

Implementation references: [PyCA Argon2id](https://cryptography.io/en/latest/hazmat/primitives/key-derivation-functions/#argon2id)
and [PyCA AESGCM](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM).
