# Path and URL aliases

Long paths and URLs can be shortened for tool arguments.

## Path aliases: `@A{0}`–`@A{9}`

Use the `path_alias` tool to register, list, or delete path aliases. Each alias points to a directory and may be followed by a relative path:

```json
{"action":"set","slot":1,"path":"C:\\work\\project"}
```

Then use it with path arguments:

```json
{"filename":"@A{1}/src/main.py"}
```

`@A{0}` is special: when it has not been explicitly registered, it resolves dynamically to the current working directory. An explicit registration overrides that default.

Aliases are stored in `~/.uag/path_aliases.json` (or the path specified by `UAGENT_PATH_ALIAS_FILE`).

## URL aliases: `@B{0}`–`@B{9}`

Use the `url_alias` tool to register, list, or delete HTTP(S) base URLs:

```json
{"action":"set","slot":0,"url":"https://example.com/api"}
```

Then use it with URL arguments:

```json
{"url":"@B{0}/users?active=1"}
```

URL aliases are stored in `~/.uag/url_aliases.json` (or the path specified by `UAGENT_URL_ALIAS_FILE`).

## Common operations

```json
{"action":"list"}
{"action":"delete","slot":0}
```

For `set`, an existing alias is not replaced unless `"overwrite":true` is supplied.

## Scope

Alias expansion is performed at the common tool-dispatch boundary, so it also applies to nested path arguments such as browser actions. Typical supported path fields include `path`, `filename`, `file_path`, `paths`, `output_path`, `input_path`, `root_dir`, `pcap_path`, `zip_path`, `download_dir`, and `trace_path`. URL expansion applies to fields such as `url`, `base_url`, `business_url`, and nested browser `url` fields.

Only values beginning with the corresponding alias syntax are expanded. Ordinary paths, URLs, and message text are left unchanged.
