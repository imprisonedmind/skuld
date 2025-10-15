# Skuld

Skuld is a global CLI that turns your WakaTime + Git activity into correct Jira worklogs and readable comments.

- Matches WakaTime branch names to Jira keys (e.g., SOT‑691)
- Filters to issues assigned to you (Jira /myself)
- Adds only the delta (WakaTime − already logged by you)
- Posts a worklog and a separate issue comment with a [SKULD] header
- Idempotent: won’t double‑post the same (issue, window, delta)

## Install (Homebrew)
- Stable (recommended):
  - `brew tap imprisonedmind/skuld`
  - `brew install skuld`
  - Upgrade later with: `brew update && brew upgrade skuld`

- Dev/HEAD (from this repo):
  - `brew install --HEAD https://raw.githubusercontent.com/imprisonedmind/skuld/main/Formula/skuld.rb`
  - Useful for testing unreleased changes.

## Setup (one‑time)
- Configure your credentials:
  - `skuld start`
  - Provide Jira site/email/token and WakaTime API key (auto‑discovered from `~/.wakatime.cfg` when possible).
- Map each repo → WakaTime project (required for `sync`):
  - From inside the repo you will sync: `skuld add`
  - This stores a per‑repo mapping in `~/.skuld.yaml` and is required so `sync` only uses time from the current repo’s WakaTime project.

## Use (global commands)
- Preview (no writes):
  - Run inside the repo: `skuld sync week --test`
  - If the repo is not mapped yet, the command exits and prompts you to run `skuld add` here first.
  - Also supports `today` and `yesterday`.
- Upload (writes to Jira):
  - `skuld sync week`
  - Only posts when there’s time to add; adds a worklog and a matching issue comment.

## What it prints (preview)
```
-----------------------------------------------------------------------------------------
Issue: SOT-691
Name:  Use real data from mongoDB
Time to add:  1h 26m 28s
Total Time: 1h 26m 28s
Comment:
  [SKULD] - Adding `1h 26m 28s` on `15/10/25` at `1:28 PM`  
  - SOT-691 Use real data from mongoDB
-----------------------------------------------------------------------------------------
```

## How it decides
- Attribution: WakaTime per‑branch seconds (Summaries API) → branch names with issue keys.
- Ownership: Jira `/rest/api/3/myself`, then local filter of issue assignee by your account.
- Delta: For each issue and period: `max(0, WakaTimeSeconds − YourLoggedSecondsInWindow)`.
- Uploads: Worklog with [SKULD] ADF comment + separate issue comment; idempotent.

## Configuration
Skuld reads `~/.skuld.yaml` and backs it up to `~/.skuld.yaml.bak` on changes. Minimal example:
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
state:
  path: ~/.local/share/skuld/state.json
```

## Notes
- Today uses daily totals from WakaTime; for precise partial‑day slicing we can add “Durations” later.
- Worklog `started` is set to “now” by default; we can adjust policy if you prefer.

## License
TBD
