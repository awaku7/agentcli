# samples

This directory contains environment-variable sample files for uag.

## Files

- `env.sample.env`
  - Canonical cross-provider template (updated by wizard)
- `generate_env_samples.py`
  - Interactive wizard + generator for shell-specific samples
- `env.sample.sh`
  - Generated from `env.sample.env` (UTF-8, LF)
- `env.sample.ps1`
  - Generated from `env.sample.env` (UTF-8 with BOM / `utf-8-sig`, CRLF)
- `env.sample.bat`
  - Generated from `env.sample.env` (CP932, CRLF)
- `provider.*.env.sample`
  - Provider-specific minimal templates

## How to run (interactive wizard)

From repository root:

```bash
python samples/generate_env_samples.py
```

If you installed uag via pip/wheel and want to create a `.env` in your project directory, use:

```bash
uag_setup
```

The script runs an interactive wizard (provider selection, back navigation, etc.), updates `samples/env.sample.env`, and overwrites:

- `samples/env.sample.sh`
- `samples/env.sample.ps1`
- `samples/env.sample.bat`

## Recommended workflow

1. Run `python samples/generate_env_samples.py` and answer prompts.
2. Verify updated `samples/env.sample.env`.
3. Verify generated shell-specific files.

Do not put real secrets in sample files.
