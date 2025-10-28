# Changelog

## v0.1.19
- CLI: show ASCII banner and improved welcome/usage text.
- Docs: add README banner and npm badges.

## v0.1.18
- Feature: new `branches` command to list recent WakaTime branches and map them to Jira keys. Supports `--interactive`, `--set BRANCH KEY`, `--unset BRANCH`, `--list`, and `--days N` (default 7 days).
- Allocation: when a branch name lacks an embedded Jira key, Skuld now uses per‑repo `branchIssues` mappings from `~/.skuld.yaml` to attribute WakaTime time to the correct issue.
- WakaTime: prefer Durations API for branch aggregation in `branches`; request branch breakdown from Summaries where applicable.
- Defaults: `branches` uses a 7‑day lookback for speed; pass `--days` to change.

## v0.1.17
- CLI: add `--version` to print the installed version.
- Docs: clarify Homebrew tap mapping (`imprisonedmind/skuld` → `imprisonedmind/homebrew-skuld`) and note that `skuld-cli/Formula/skuld.rb` is a scaffold only.
- Tap: no functional changes; release pipeline unchanged, but Python `__version__` is now kept in sync by the release script.

## v0.1.16
— superseded by v0.1.17 before push; no functional difference.

## v0.1.14
- Fix: include WakaTime-only keys when verifying Jira ownership so time on branches without commits in the window (e.g., SOT-718) is allocated and shown in previews/uploads.

## v0.1.15
- Feature: add `jira.requireOwnership` (default true). When set to `false`, Skuld will include issues discovered from WakaTime branches even if Jira ownership cannot be verified (useful when Jira privacy restrictions hide assignee info).


## v0.1.13
- Default behavior: running `skuld` (no args) now shows a concise usage guide; `skuld sync` performs an incremental sync from the last successful sync to now (first run falls back to 24h).
- State: track per-repo last sync time in `~/.local/share/skuld/state.json`.
- Comments: disable separate Jira issue comments by default; add `comment.issueCommentsEnabled` config flag to opt-in.
- CLI: safer arg handling and small robustness tweaks around window selection and WakaTime API choice.
- Docs: update main README and Homebrew tap README for new defaults and examples.


## v0.1.12
- npm: add `keywords` in package.json for discoverability.

## v0.1.11
- Docs: update README install sections (macOS via Homebrew, Linux via npm) and troubleshooting; no code changes.

## v0.1.10
- Release: script now publishes to npm by default alongside Homebrew tap update (set `SKULD_NPM_PUBLISH=0` to skip).
- Node shim: set `PYTHONPATH` for cross‑platform (Linux) installs via npm.

## v0.1.9
- WakaTime Durations: use precise sub‑day durations for short windows (today/yesterday/24h); fall back to Summaries for longer ranges.
- Worklog timing: add configurable `time.startedPolicy` with options `now` (default), `periodEnd`, `lastCommit`, and `fixed` (`time.startedFixedTime: HH:MM`).
- Docs: updated printer examples for `--test` and upload; README adds ticket‑status bullet and license info.

## v0.1.8
- Uploads: when a Jira status transition occurs during upload (e.g., To Do → In Progress), append a note to the worklog/issue comment: "Updating status from XYZ to ABC".


## v0.1.7
- Jira: automatically transition issues from "To Do"/"Todo" to "In Progress" when uploading worklogs; print the resulting status.
- Preview: show current Jira status per issue and note when a transition will occur on upload.
- Robustness: use strict ISO timestamps for Git commit times and normalize to timezone-aware UTC for correct filtering since the last upload.


## v0.1.2
- Preview/comments: include commits from branches matching the issue key, not only subjects.
- Preview/comments: bound commit bullets to after the last Skuld upload for that issue.
- Minor: internal refactors for reliability (no behavior change to uploads).

## v0.1.1
- Homebrew formula: unpin Python to `python` (no `python@3.11`).
- Enforce per-repo mapping for `sync`; require `skuld add` before running.
- Remove cross-project auto-detection; `sync` will not pull time from other WakaTime projects.
- Update tap test to `--help` for stable CI.

## v0.1.0
- Initial public CLI and Homebrew formula.
