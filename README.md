# Skuld

Skuld is a local CLI that correlates your development activity (WakaTime + Git) to Jira issues and prepares precise worklogs and comments. It is MCP‑friendly, but does not require MCP — Jira REST alone is enough.

- Automatic time attribution from WakaTime totals to Jira issues found in your Git commits/branches
- Optional LLM‑assisted parent/child allocation (planned)
- Idempotent logging with clear, auditable comments prefixed with `[SKULD]`
- Safe previews (`--test`) that do not write to Jira

## Status
- Preview flow implemented: fetches WakaTime totals, scans Git commits, fetches Jira summaries, and prints proposed logs.
- Upload (Jira worklogs + comments) pending wiring.

## Requirements
- Python 3.10+
- Git repo with commit messages containing Jira keys (e.g., `SOT-507 fix …`)
- WakaTime API key (Skuld auto‑discovers from `~/.wakatime.cfg` or uses `~/.skuld.yaml`)
- Jira site + user email + API token (for showing issue “Name” and filtering to your issues)

## Quick Start (local, in place)
1) Clone this repo and `cd` into it.
2) Initialize config (you can skip tokens if you only want a very basic preview):
   - `python -m skuld.cli start`
   - Enter Jira site (for clickable links) and WakaTime API key.
3) Add per‑repo mapping (optional but recommended for speed/accuracy):
   - From inside your repo: `python -m skuld.cli add`
   - Picks the WakaTime project (auto‑detected or manual) and optional Jira project key. Writes to `~/.skuld.yaml` under `projects`.
4) Test against a Jira‑relevant repo (with keys in commits):
   - `python -m skuld.cli sync today --test --project /path/to/your/repo`
   - Or `yesterday` / `week`.

## Testing Locally from Another Repo’s Console
If you want to run Skuld while your shell is inside another repo:

- Option A: Use an alias pointing to this repo
  - Add to your shell profile:
    - `alias skuld='PYTHONPATH=/absolute/path/to/your/skuld-repo python -m skuld.cli'`
  - Then, from any repo:
    - `skuld start`
    - `skuld sync yesterday --test` (defaults `--project` to the CWD)

- Option B: Invoke with a one‑off `PYTHONPATH`
  - From your other repo:
    - `PYTHONPATH=/absolute/path/to/your/skuld-repo python -m skuld.cli start`
    - `PYTHONPATH=/absolute/path/to/your/skuld-repo python -m skuld.cli sync yesterday --test`

Tips:
- For accurate project scoping, add a mapping in `~/.skuld.yaml`:
  ```yaml
  projects:
    "/absolute/path/to/your/repo":
      wakatimeProject: your-wakatime-project
      jiraProjectKey: SOT
  ```
- With Jira credentials set, Skuld fetches the real issue summary and filters to issues where `assignee = currentUser()`.

## What `--test` Does
- Reads WakaTime totals for the period:
  - From `--wakatime-file` JSON, or
  - Live via WakaTime API using `~/.skuld.yaml` or `~/.wakatime.cfg`
- Scans your Git commits for Jira keys and groups by issue
- Optionally fetches Jira summaries and filters to your assigned issues
- Prints a preview in this format (no writes to Jira):
  ```
  -----------------------------------------------------------------------------------------
  Issue: SOT-507
  Name:  Add migration for unique, indexed slug for Company
  Time to add:  3m 55s
  Total Time: 3m 55s
  Comment:
    [SKULD] - Adding `3m 55s` on `15/10/25` at `11:33 AM`  
    - Merged in feature/SOT-507-public-identifier-for-company (pull request #208)
  -----------------------------------------------------------------------------------------
  ```

Notes:
- Today previews use daily totals from WakaTime; for precise partial‑day slicing we’ll add the Durations API.
- “Time to add” vs “Total Time”: in preview both are equal; when uploads are wired, “Time to add” will reflect the delta after reconciling existing Jira worklogs.

## Configuration
Skuld reads `~/.skuld.yaml` (fallback: `~/.time-time.yaml`). Example:
```yaml
jira:
  site: https://your-org.atlassian.net
  email: your.email@your.org
  apiToken: YOUR_JIRA_API_TOKEN
mcp:
  endpoint: http://localhost:port
  auth: YOUR_MCP_AUTH_TOKEN
regex:
  issueKey: "[A-Z][A-Z0-9]+-\\d+"
projects:
  "/absolute/path/to/your/repo":
    wakatimeProject: your-wakatime-project
    jiraProjectKey: SOT
wakatime:
  apiKey: YOUR_WAKATIME_API_KEY
state:
  path: ~/.local/share/skuld/state.sqlite
```

## Commands
- `skuld start` — interactive setup for Jira + WakaTime + optional MCP
- `skuld add [--project <path>]` — add a per‑repo mapping to speed up syncs
- `skuld sync today --test [--project <path>]` — preview today (last 12h or start‑of‑day)
- `skuld sync yesterday --test [--project <path>]` — preview yesterday
- `skuld sync week --test [--project <path>]` — preview current week

## Roadmap
- Write Jira worklogs + comments (REST) with idempotency
- LLM‑assisted parent/child allocation (optional)
- Precise partial‑day attribution with WakaTime Durations
- Packaging for `pipx`, Homebrew, or npm/bun

## MCP vs REST
- MCP optional; Jira REST is sufficient for logging work and comments
- LLM usage can be via MCP tools or any provider/local model via an adapter

## License
TBD
