# skuld: Automatic Jira Time Logging from WakaTime + Git (via Atlassian MCP)

This document proposes a small, local tool that correlates your development activity (WakaTime + Git) to Jira tickets and updates them with time spent and a concise work description. It aims to be simple, private-by-default, and reliably idempotent.

## Decisions
- Trigger: CLI-first (manual) with simple subcommands; optional git hook remains as an add-on.
- Backend: MCP-first (use Atlassian Remote MCP Server tools); Jira REST remains a fallback.
- Minimum log unit: match WakaTime (exact parity). Reconcile Jira worklogs to equal WakaTime totals for the period.

## Goals
- Automatically log worklogs (“time spent”) to Jira issues you touched during the day.
- Add a short, useful comment describing the work (based on commits/branches).
- Run locally with minimal setup; avoid complex infra.
- Dry-run, review, and explicit confirmation modes to prevent mistakes.
- Leverage Atlassian’s MCP server where helpful, but keep Jira REST as a fallback.

## Constraints & Assumptions
- You already have WakaTime tracking enabled (projects/branches).
- Git histories and branch naming often include Jira issue keys (e.g., `ABC-123-some-feature`).
- Jira Cloud or Server is accessible with a token; using MCP server is preferred but REST API fallback is acceptable.
- Local-only execution is preferred; scheduled (cron/launchd) or on-commit hook are acceptable triggers.

## High-Level Approach
- Inputs
  - WakaTime activity for a time window (e.g., today): durations by project/branch; optionally heartbeats.
  - Git commits and current/active branches for the same window; extract issue keys from branch names and commit messages.
- Correlation
  - Attribute WakaTime time to Jira issues by matching ticket keys from Git context (branch/commit) and WakaTime project/branch.
  - If multiple issues are present, proportionally split based on commit density or active-branch time.
- Outputs
  - Jira worklogs with `timeSpentSeconds` per issue and `started` timestamps.
  - Optional comment summarizing work (commit subjects, branch names, PR link if available).

## Operating Modes
- CLI-first: `skuld start` (configure), `skuld sync <period>` (apply worklogs).
- Optional: On-commit hook that triggers a dry-run or queued upload.
- Optional: IDE integration that calls the CLI.

## Data Flow
1. Read config (`~/.skuld.yaml`; fallback `~/.time-time.yaml`): Jira site/token, MCP config, regex for issue keys, project mappings, timezone.
2. Pull WakaTime data for the time window (API summaries or local cache) → durations by project/branch.
3. Pull Git data: commits, branches, timestamps; extract issue keys via regex.
4. Correlate: assign durations to issues with heuristics (below) and produce candidate worklogs.
5. Reconcile with local state DB to avoid duplicate logging.
6. Write to Jira via MCP server (preferred) or REST fallback; record results in state DB. Ensure totals logged to Jira equal WakaTime totals for the window (reconciliation step).

## Matching Strategy (Heuristics)
- Ticket key regex: `[A-Z][A-Z0-9]+-\d+` (configurable).
- Primary signals (in decreasing weight):
  1) Current/active branch name contains a ticket key during measured intervals.
  2) Commit messages in the window reference a key.
  3) WakaTime branch name contains a key.
- Allocation:
  - If a single issue key dominates (e.g., >70% signals), assign all time to it.
  - If multiple keys present, split time proportionally by signal weight (e.g., commits per key, active-branch time, heartbeats on branch).
  - Unattributed time: hold and prompt for manual assignment or log to a configured fallback issue (optional, off by default).
- Comment building:
  - Use top N commit subjects in the period, dedupe similar lines, and include branch name.
  - Prefer concise language, e.g., “Updated auth flow; added tests (#a1b2c3)”

## LLM-Assisted Attribution
When multiple related issues (parent/child) exist, use an LLM to improve allocation across subtasks.

- Inputs to the model:
  - Recent commit subjects/bodies and diffs (size-capped), branch names, PR title (if present).
  - Candidate issues from Jira (parent and children): keys, titles, descriptions, and optionally recent comments.
  - WakaTime project/branch time slices for the period.
- Task:
  - Classify each commit (or time slice) to the most relevant issue among the candidates.
  - Produce allocation weights across issues and a short rationale.
  - Generate a compact worklog comment per issue using the classified commits.
- Guardrails:
  - Hard-cap tokens by sampling only recent N commits and truncating diffs.
  - If confidence is low or no clear child matches, fall back to logging on the parent/main ticket.
  - Keep a dry-run preview of allocations and comments.
- Implementation:
  - Use MCP-first to call an LLM tool with a constrained prompt. If MCP LLM is unavailable, use any configured LLM provider or heuristics-only fallback.

## Jira/MCP Integration
- Preferred: Atlassian Remote MCP Server
  - Configure a local MCP client to call Jira tools exposed by Atlassian’s MCP server (e.g., list issues, add worklog, add comment).
  - Pros: tighter alignment with Atlassian’s ecosystem; future-proof with agentic workflows.
  - Cons: adds a dependency on MCP runtime/config.
- Fallback: Jira REST API
  - POST `/rest/api/3/issue/{issueIdOrKey}/worklog` with `timeSpentSeconds` and `started`.
  - Add comment via `/rest/api/3/issue/{issueIdOrKey}/comment` (or embed in worklog comment field if desired).

### MCP vs REST (Practical Notes)
- Core capability does not require MCP; Jira REST alone is sufficient.
- Atlassian’s Remote MCP Server is Atlassian-hosted. You can also run your own MCP servers/tools locally, but that is separate and optional.
- LLM usage is independent of MCP; any LLM (hosted or local) can be used via a thin adapter.
- Suggested approach: ship REST-first, then add MCP integration as a value-add when available.

## Safety & Idempotency
- Local state DB (e.g., `~/.local/share/skuld/state.sqlite`):
  - Records each posted worklog: `{date, issueKey, seconds, started, hash(source)}`
  - Prevents duplicate submissions on retries.
- Dry-run mode prints the plan (issues, durations, comments) for review.
- Maximum granularity (e.g., 15m minimum) to avoid noisy micro-logs.
- Daily cap rules and manual confirmation thresholds (e.g., >8h/day requires confirm).

## Time Reconciliation (WakaTime ⇄ Jira)
- Goal: ensure Jira worklogs for the period equal WakaTime totals.
- Steps per period (e.g., day):
  1) Compute WakaTime total seconds across all included projects.
  2) Fetch existing Jira worklogs you previously posted for the same period (by author).
  3) If Jira < WakaTime, propose new logs to cover the delta using attribution results.
  4) If Jira > WakaTime (edge), do not delete; instead warn and require manual resolution.
  5) Respect minimum unit as “exact parity” with WakaTime: no rounding beyond WakaTime’s stored values.

## Configuration
- File: `~/.skuld.yaml` (can be overridden per-project)
  - `jira.site`: e.g., `https://your-org.atlassian.net`
  - `jira.email` + `jira.apiToken` (REST fallback) or `mcp.endpoint` + `mcp.auth`
  - `time.zone`, `minLogMinutes`, `aggregationWindow: 60m|EOD`
  - `regex.issueKey`
  - `projects`: map local paths → WakaTime project names → Jira project key/prefix
  - `comment.maxLines`, `comment.includeCommitHashes`
  - `state.path`
  - `llm.enabled: true|false`
  - `llm.maxCommits: 10`, `llm.includeDiff: false|true (size-capped)`
  - `llm.promptTemplatePath` (optional)

## Minimal PoC (Incremental Plan)
1) Skeleton CLI (`skuld`) with `start` and `sync <period>` (dry-run first)
2) WakaTime summaries pull (period) by project/branch
3) Git scan (period): commits, branch; extract ticket keys
4) Correlate → candidate worklogs (console table)
5) MCP-first write to Jira (behind `--apply`) + state DB for idempotency
6) Optional LLM classification: refine allocations across parent/child issues
7) Reconciliation pass to ensure Jira totals match WakaTime
8) Optional commit hook sample (value-add)

## CLI Usage (Proposed)
- `skuld start` → interactive prompts for WakaTime API key, Jira site/email/token, MCP endpoint/auth. Writes `~/.skuld.yaml`.
- `skuld sync today` → analyze last 12 hours or start-of-day, reconcile to WakaTime, then apply.
- `skuld sync yesterday` → analyze yesterday.
- `skuld sync week` → analyze from start of week to now.
- `skuld sync --test` → dry-run preview: tickets, links, times, and draft comments.
- Flags: `--use-rest`, `--project <path>`, `--wakatime-file <path>`.

## Distribution
- Homebrew: create a tap with a Formula that installs a Python/bun-built binary or shims a `pipx` install.
- npm/bun: publish as an npm package with a `bin` entry (`skuld`), targeting Node 18+; or ship a bun-native script.
- Python: `pipx install skuld` (optional), ship console_scripts entry.
Note: keep runtime deps minimal to ease cross-platform installs.

## Pseudocode Sketch
```bash
# CLI
$ skuld sync today --use-rest  # example
```
```python
cfg = load_config()
wkt = wakatime.fetch_summaries(since, until, projects=cfg.projects)
git = gitlog.scan(since, until, repos=cfg.projects.keys())
issues = correlate(wkt, git, regex=cfg.issue_regex)
plan = aggregate(issues, min_granularity=cfg.min_log_minutes)
if not args.apply:
    print(plan)
    exit()
for entry in plan:
    if state.seen(entry):
        continue
    jira.add_worklog(entry)  # via MCP or REST
    if entry.comment:
        jira.add_comment(entry.issue, entry.comment)  # optional
    state.record(entry)
```

## Future Enhancements
- Pull PR metadata to include links in comments.
- Integrate calendar (exclude meetings) and focus time to improve attribution.
- Interactive TUI to preview/edit before applying.
- Team mode: shared config + per-user attribution.

## Resources
- Atlassian Remote MCP Server (announcement):
  - https://www.atlassian.com/blog/announcements/remote-mcp-server
- Jira REST API (worklogs):
  - https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-worklogs/
- WakaTime API (summaries):
  - https://wakatime.com/developers#summaries
- MCP client tooling (reference implementations):
  - https://modelcontextprotocol.io/

## Open Questions
- None pending — decisions made above.
- Handling unattributed time: skip, prompt, or fallback ticket?
- Comment policy: per-log comments vs periodic consolidated comment?

---
If you confirm trigger mode and backend (MCP vs REST), I can scaffold a minimal CLI and config next.
