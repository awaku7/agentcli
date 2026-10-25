# macOS Platform Support — Implementation and Verification Log

- Repository: `awaku7/agentcli`
- Working branch: `feat/macos-platform-support` (based on `main` commit `5e0e6885`, UAG 0.7.34)
- Started: 2026-10-25
- Priority change: macOS functionality and verified CI coverage **before** Windows VM-grade sandbox acceptance.
- Existing Windows Sandbox draft PR #274: independent; this branch must neither merge nor alter it.
- Goal: macOS ARM64 and x86-64 support for UAG's everyday CLI, desktop UI, and trusted local Web workflows; add MXC Seatbelt as a **separate stage** after the baseline works.
- Safety: do not claim Seatbelt, enterprise VM isolation, or remote multi-tenant acceptance from basic macOS startup tests. Unsupported sandbox requests must continue to fail closed.

## Append-only progress record

| Date (JST) | Stage | Evidence / status | Next action |
| --- | --- | --- | --- |
| 2026-10-25 | Baseline inspection | `README.md` documents Python >=3.11, `uag` CLI, `uagg` desktop, and `uagw` Web. `mxc_backend.py` rejects macOS, despite some existing macOS platform integration. `docs/SANDBOX_MXC.md` explicitly calls macOS unsupported. | Establish macOS ARM64/x86-64 CI smoke coverage, then address findings. |
| 2026-10-25 | Backend feasibility | Upstream Microsoft MXC documents the Seatbelt backend on macOS 15+, with process-tree rather than persistent-container semantics and limitations on network policy. UAG's current host-side resource/cleanup logic is Windows Job Objects or Linux systemd/cgroup v2. | Keep Seatbelt work separate until a macOS-specific bounded cleanup/resource design and live tests exist. |
| 2026-10-25 | macOS CI added | Commit `937027639`: workflow jobs on `macos-15` (ARM64) and `macos-15-intel` (Intel) install CLI/Desktop/Web dependencies, import entrypoints, and exercise session and MXC regression tests. **Not yet executed**. | Open a draft PR and inspect GitHub Actions results. |
| 2026-10-25 | First PR CI (run `40178469555`) | macOS ARM64 install and Python compile passed, but combined entrypoint import step exited 1 without a traceback in captured output; root cause not yet known. Other jobs continued. | Split imports into distinct processes with explicit stderr tracebacks. |
| 2026-10-25 | Diagnostic patch | Commit `37d37373`: independent macOS CLI/GUI/Web import probes with traceback output; this is instrumentation, **not a fix or acceptance result**. | Inspect second CI run and make the narrowest required code change. |
| 2026-10-25 | Execution environment | The current GitHub connector can read/write the repository; this assistant's execution container cannot resolve github.com and is not a Mac. | Use GitHub Actions for macOS tests and report that local macOS testing has not occurred. |

## Stages and acceptance gates

1. **macOS baseline CI:** build/install on macOS 15 Apple Silicon and Intel, validate CLI entrypoint/import, desktop imports, local Web imports, and selected portable regression tests. Do not start an interactive GUI in a headless runner.
2. **Fix macOS regressions:** only issues identified by test evidence; preserve Windows and Linux behavior and existing CLI/Tool contracts.
3. **MXC Seatbelt (separate PR):** probe and fail-closed enforcement, narrow read/write roots, no networking, process-tree cleanup, bounded resources, workspace policy, and live macOS acceptance. The static four-tool MXC catalog remains unchanged unless separately reviewed.
4. **Remote acceptance:** not part of the baseline or Seatbelt local work; require separate explicit security acceptance tests.

## Validation ledger

- macOS ARM64: **failed initial import smoke**; run [`40178469555`](https://github.com/awaku7/agentcli/actions/runs/40178469555), diagnostic rerun pending.
- macOS x86-64: **not yet verified**.
- Local Black/Ruff/pytest: **not run**; repository cannot be cloned into the available execution container.
- GitHub CI: macOS matrix executed; initial ARM64 failed at import smoke. Further results pending.

Update this record with concrete run URLs, failures, fixes, and outstanding gaps at every milestone. No result counts as passing without a completed CI job.
