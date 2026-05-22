# uagent environment loading specification

## Scope

This document defines how startup configuration is resolved from pre-existing environment variables, `.env`, and `.env.sec`.

Only variables whose names start with `UAGENT_` are treated as uagent startup configuration for snapshot, merge, validation, and `.env.sec` synchronization.

## Terms

### Pre-existing environment variables

Environment variables that already exist in `os.environ` before uagent loads any `.env` or `.env.sec` file.

Examples:

- Windows user/system environment variables
- PowerShell variables such as `$env:UAGENT_PROVIDER = "ollama"`
- `cmd.exe` variables such as `set UAGENT_PROVIDER=ollama`
- Variables passed by a parent process or CI system

These variables are considered explicit settings for the current run.

### `.env`

A plaintext dotenv file in the selected workdir. It is convenient for development and manual editing, but it may contain secrets and should not be committed.

### `.env.sec`

An encrypted dotenv file in the selected workdir. After decryption, its content is parsed as dotenv-style `KEY=VALUE` lines.

The decryption key is selected by `uag_envsec.secret_core` using this order:

1. `.uagent.key` in the current workdir, if present
1. The default key location managed by `uag_envsec`

## Effective value priority

The effective runtime value for each `UAGENT_*` key must be resolved in this order:

1. Pre-existing environment variable
1. `.env.sec`
1. `.env`
1. Application default

A higher-priority source must not be overwritten by a lower-priority source.

Example:

```env
# .env.sec
UAGENT_PROVIDER=openai
```

```powershell
# pre-existing environment before launching uag
$env:UAGENT_PROVIDER = "ollama"
```

Effective value:

```env
UAGENT_PROVIDER=ollama
```

## Startup order

The CLI startup flow must follow this order:

1. Capture the pre-existing `UAGENT_*` environment snapshot before reading any `.env` or `.env.sec` file.
1. Decide and apply the workdir.
1. Load `.env` from the selected workdir with `override=False`.
1. Load `.env.sec` from the selected workdir without overriding keys that existed in the pre-existing snapshot.
1. Validate startup environment.
1. If validation fails in interactive CLI mode, run `uagent.setup_cli`.
1. After setup, reload `.env` and `.env.sec` using the same priority rules.
1. Validate again.
1. Build startup banner.
1. Create the provider client.

The startup banner and provider client must be created only after the final environment has been loaded and validated.

## `.env` behavior

`.env` is loaded with `override=False`.

This means `.env` fills missing values, but does not override values already provided by the process environment.

## `.env.sec` behavior

`.env.sec` is loaded after `.env`.

`.env.sec` may override values loaded from `.env`, but must not override keys that were present in the pre-existing environment snapshot.

If `.env.sec` exists but cannot be decrypted, startup should print a warning. Validation then decides whether startup can continue.

## Setup UI behavior

The setup UI should run only when required startup settings are still missing after loading all configured sources.

If `.env.sec` contains all required values, setup UI should not run.

After setup UI exits, startup must reload `.env` and `.env.sec` before validating again.

## `.env.sec` synchronization behavior

Automatic `.env.sec` synchronization must not silently discard or overwrite user intent.

Startup may offer to persist pre-existing `UAGENT_*` environment variables into `.env.sec` only after startup validation succeeds. This persistence is opt-in:

- If pre-existing `UAGENT_*` environment variables exist and `.env.sec` is missing, interactive CLI startup asks whether to create `.env.sec` from those startup environment variables.
- If `.env.sec` exists and a pre-existing `UAGENT_*` environment variable has a different value, the pre-existing environment variable remains the effective runtime value. Interactive CLI startup asks whether to update `.env.sec` with that environment value.
- If the user declines, runtime values are unchanged and `.env.sec` is not modified.
- GUI, Web, and non-interactive startup must not prompt. They should print guidance to use `uag_envsec` when synchronization is available.

Startup must never silently create or update `.env.sec`.

## Known failure modes this specification prevents

- `.env` overwriting a value explicitly set before launch.
- `.env.sec` being loaded only after validation.
- Startup banner showing a different provider from the provider client.
- Setup UI not running because stale process environment values mask missing configuration.
- User edits to `.env.sec` being overwritten by stale `.env` or stale process values.
