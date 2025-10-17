# Changelog

## v0.1.13
- Describe changes here.


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
