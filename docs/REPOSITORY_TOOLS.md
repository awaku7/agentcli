# Repository Analysis Tools

This repository includes three tools for reviewing and validating source trees.

## `git_review`

Summarizes Git changes without exposing secret values.

Use it to inspect staged and unstaged changes before a commit.

Key options:

- `root`: repository path
- `include_untracked`: include untracked files
- `max_diff_chars`: limit diff output
- `scan_secrets`: detect likely secret patterns

The result includes status, changed files, diff statistics, risky filenames, and test candidates.

## `security_scan`

Scans repository files for likely secrets and risky filenames.

Key options:

- `root`: directory to scan
- `include_hidden`: include hidden files
- `max_files`: maximum number of files
- `max_file_bytes`: maximum file size
- `scan_content`: enable content scanning

Secret values are never returned. Findings contain only the file, line, category, and a redacted preview.

## `coverage_report`

Runs the project test command through a language-specific coverage adapter.

Supported adapters:

- `python`: `coverage` and pytest
- `typescript`: `c8` and npm test
- `rust`: `cargo llvm-cov`
- `go`: `go test -coverprofile`

Key options:

- `language`: `auto`, `python`, `typescript`, `rust`, or `go`
- `test_target`: optional safe test target
- `timeout`: execution timeout in seconds
- `dry_run`: show the selected command without running it
- `auto_install`: automatically install missing Python coverage dependencies with pip

Python coverage dependencies are installed only when execution is requested; dry runs do not install packages.

The tool returns the selected adapter, command, execution status, output, and coverage totals when the adapter provides them.

## Safety

All three tools restrict paths to the current working directory, avoid returning secret values, and enforce bounded output or execution limits.
