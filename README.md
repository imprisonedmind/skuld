# Skuld (MVP)

Skuld is a local CLI that correlates your development activity (WakaTime + Git) to Jira issues and posts accurate worklogs and comments. It runs locally and uses Jira REST.

- Branch‑based attribution: allocates WakaTime time to issues by matching keys in branch names
- Ownership filter: only issues assigned to you (verified via Jira /myself)
- Delta logging: only add time when WakaTime > already logged by you
- Idempotent uploads: per‑issue/per‑window tracking to avoid duplicates
- [SKULD] comments: posts a readable comment with the time added and concise bullets
- Safe previews (`--test`): identical output without writing to Jira

## Requirements
- Python 3.10+
- WakaTime API key (auto‑discovered from `~/.wakatime.cfg` or configured in `~/.skuld.yaml`)
- Jira Cloud site + user email + API token

## Quick Start
1) Configure auth once:
   - `python -m skuld.cli start`
   - Enter Jira site/email/token and WakaTime API key.
2) (Recommended) Map repo → WakaTime project:
   - In your repo: `python -m skuld.cli add`
   - Picks or prompts for the WakaTime project and optional Jira project key. Writes to `~/.skuld.yaml` under `projects`.
3) Preview (no writes):
   - `python -m skuld.cli sync week --test --project /path/to/repo`
   - Shows issues with positive deltas only, and the [SKULD] comment body.
4) Upload (apply):
   - `python -m skuld.cli sync week --project /path/to/repo`
   - Posts worklogs and a separate issue comment for each positive delta.

## Install Options (for production use)
- pipx (recommended):
  - `pipx install .` (from this repo) or package when published.
  - Then run `skuld ...` via the pipx shim if configured as a console script, or use `python -m skuld.cli`.
- npm (wrapper):
  - `npm install -g skuld-cli` (when published), or from this repo: `npm link`.
  - Then run `skuld ...` — the wrapper calls `python -m skuld.cli`.
- Homebrew:
  - Create a formula that installs the npm wrapper or a Python shim; see docs/skuld-plan.md Distribution.

## Behavior and Rules
- Attribution
  - Uses the WakaTime Summaries API to get per‑branch seconds for the chosen project.
  - Extracts issue keys via regex (default `[A-Z][A-Z0-9]+-\d+`) from branch names. No fabricated splits.
- Ownership
  - Resolves your Jira account via `/rest/api/3/myself`.
  - Searches issues by key (no assignee filter) and filters locally by your `accountId` or `emailAddress`.
- Delta
  - For each issue in the period: `TimeToAdd = max(0, WakaTimeSeconds - YourLoggedSecondsInWindow)`.
  - If `TimeToAdd = 0`, Skuld does not update or comment on that issue.
- Uploads
  - Worklog: `timeSpentSeconds = TimeToAdd`, `started = now`, `comment = [SKULD]…` (ADF format).
  - Issue comment: posts the same `[SKULD]` body as a separate comment (ADF).
  - Idempotency: uses a local state file (JSON) to skip repeat uploads for the same (issue, window, delta).
- Preview (`--test`)
  - Prints only issues with positive deltas. Shows: Issue, Name, Time to add, Total Time, Already Logged, and the [SKULD] comment content.

## Configuration
Skuld reads `~/.skuld.yaml` (fallback: `~/.time-time.yaml`). It merges changes and writes a `.bak` before saving.

Example:
```yaml
jira:
  site: https://your-org.atlassian.net
  email: your.email@your.org
  apiToken: YOUR_JIRA_API_TOKEN
regex:
  issueKey: "[A-Z][A-Z0-9]+-\\d+"
wakatime:
  apiKey: YOUR_WAKATIME_API_KEY
projects:
  "/absolute/path/to/your/repo":
    wakatimeProject: your-wakatime-project
    jiraProjectKey: SOT
state:
  path: ~/.local/share/skuld/state.json
```

## Commands
- `skuld start` — interactive setup for Jira + WakaTime
- `skuld add [--project <path>]` — add a per‑repo mapping for faster, more reliable syncs
- `skuld sync today|yesterday|week --test [--project <path>]` — preview without writes
- `skuld sync today|yesterday|week [--project <path>]` — upload worklogs + comments (delta > 0 only)

## Debugging
- Add `--debug` to `sync` to print detailed diagnostics:
  - Regex (configured/normalized), chosen WakaTime project, branch→seconds
  - Candidate keys and filtered Jira keys
  - Ownership verification, and any Jira HTTP errors

## Notes and Limitations
- WakaTime “Summaries” per‑day totals are used; for precise partial‑day slicing we can add “Durations” support later.
- The `started` timestamp for worklogs is currently “now”. If you prefer a different policy (e.g., end of window), we can adjust.

## Roadmap
- Optional LLM‑assisted split across parent/child issues
- Precise partial‑day attribution with WakaTime Durations
- Packaging via `pipx`, Homebrew, or npm/bun

## License
TBD
