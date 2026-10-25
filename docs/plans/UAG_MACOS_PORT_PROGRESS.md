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
| 2026-10-25 | Root cause: missing Web extra | Diagnostic GitHub Actions run [`40178668150`](https://github.com/awaku7/agentcli/actions/runs/40178668150) proves `uagent.cli_entry` and `uagent.gui` import on macOS ARM64; `uagent.web` fails: `ModuleNotFoundError: No module named 'mcp'` through `web_impl.routes_auth` → OIDC → `tools.mcp.client`. The `web` extra omitted `mcp` although the Web import requires it. | Add the missing Web dependency; retest. |
| 2026-10-25 | Web extra correction | Commit `64e7a249`: add `mcp` to `[project.optional-dependencies].web`. No Python source changed. **Acceptance pending subsequent macOS CI**, including GUI import and tests. | Check fresh ARM64/Intel CI and any subsequent missing packages. |
| 2026-10-25 | ARM64 corrected Web smoke | Run [`40178785266`](https://github.com/awaku7/agentcli/actions/runs/40178785266): editable install, compilation, CLI/Web/GUI imports and `uag session --help` **passed** on macOS ARM64 after the Web extras fix. The broad selected regression tests had 1 failure: `test_mxc_host_paths_accept_only_pre_dotenv_overrides` assumes Windows/Linux runtime paths, which macOS MXC explicitly lacks today. | Do not alter production MXC safety fallback; scope the Mac test to the supported contracts and record the omitted case. |
| 2026-10-25 | OS-specific test scope | Commit `e7943fec`: retain macOS session regression tests and the other MXC contract tests while excluding the **single Windows/Linux-only host runtime paths test** via an explicit pytest filter. This test continues to run in Linux CI; it must be reconsidered when implementing Seatbelt. | Check fresh ARM64 and Intel jobs before accepting the PR. |
| 2026-10-25 | Baseline verification accepted | GitHub Actions run [`40178979641`](https://github.com/awaku7/agentcli/actions/runs/40178979641), head `1f8fbd5d`: macOS 15 ARM64 and macOS 15 Intel both **success** (CLI/Web/GUI imports and selected regressions). The PR's quality, pull-request-tests, Python 3.11/3.13/3.14, Ubuntu 24.04/26.04 MXC jobs also succeeded. `full-tests` and `nightly-full-tests` were intentionally skipped by event conditions; neither was executed. | Seek review for baseline PR; proceed to Seatbelt as an isolated follow-up stage. |
| 2026-10-25 | Explicit Codex re-review (PR #276) | Review on `724b91c9` found one P2 issue: the macOS CI imported only the lightweight `uagent.cli_entry` and used `uag session --help`, never loading the actual interactive `uagent.cli` implementation; this permits false-positive CLI support. [Finding](https://github.com/awaku7/agentcli/pull/276#discussion_r4370382363). | Include a direct import of `uagent.cli` in the same separate-process smoke loop on both Mac architectures. |
| 2026-10-25 | P2 CLI smoke fix | Commit `83b32b37`: macOS ARM64/Intel CI import matrix now includes the real `uagent.cli` after the existing dispatcher, without changing shipped Python code. **CI and re-review still pending**. | Inspect fresh CI; report any Mac-only dependency/import failure and request another Codex review after success. |
| 2026-10-25 | Execution environment | The current GitHub connector can read/write the repository; this assistant's execution container cannot resolve github.com and is not a Mac. | Use GitHub Actions for macOS tests and report that local macOS testing has not occurred. |

## Stages and acceptance gates

1. **macOS baseline CI:** build/install on macOS 15 Apple Silicon and Intel, validate CLI entrypoint/import, desktop imports, local Web imports, and selected portable regression tests. Do not start an interactive GUI in a headless runner.
2. **Fix macOS regressions:** only issues identified by test evidence; preserve Windows and Linux behavior and existing CLI/Tool contracts.
3. **MXC Seatbelt (separate PR):** probe and fail-closed enforcement, narrow read/write roots, no networking, process-tree cleanup, bounded resources, workspace policy, and live macOS acceptance. The static four-tool MXC catalog remains unchanged unless separately reviewed.
4. **Remote acceptance:** not part of the baseline or Seatbelt local work; require separate explicit security acceptance tests.

## Validation ledger

- macOS ARM64: **verified by CI success**, run `40178979641` (macOS 15 ARM64).
- macOS x86-64: **verified by CI success**, run `40178979641` (macOS 15 Intel).
- Local Black/Ruff/pytest: **not run**; repository cannot be cloned into the available execution container.
- GitHub CI: **completed successfully** on head `1f8fbd5d` (both macOS architectures, Linux MXC, Linux quality, and PR tests). The subsequent record-only commit is not itself evidence of another successful run.

Update this record with concrete run URLs, failures, fixes, and outstanding gaps at every milestone. No result counts as passing without a completed CI job.
