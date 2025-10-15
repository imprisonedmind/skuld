# Changelog

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
