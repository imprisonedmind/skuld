import argparse
import datetime as dt
import json
import os
import pathlib
from typing import Any, Dict, List, Tuple

from .git import get_commits, group_commits_by_issue
from .util import format_seconds
from .wakatime import load_total_seconds_from_file


def _default_config_path() -> pathlib.Path:
    env = os.environ.get("SKULD_CONFIG")
    if env:
        return pathlib.Path(env).expanduser()
    # Primary
    p = pathlib.Path("~/.skuld.yaml").expanduser()
    if p.exists():
        return p
    # Back-compat
    return pathlib.Path("~/.time-time.yaml").expanduser()


def load_config(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        cfg: Dict[str, Any] = {}
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line and not line.startswith("-"):
                    k, v = line.split(":", 1)
                    cfg[k.strip()] = v.strip()
        return cfg


def _period_bounds(period: str) -> Tuple[str, str]:
    now = dt.datetime.now()
    if period.lower() in ("today",):
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        twelve_hours_ago = now - dt.timedelta(hours=12)
        since = max(start, twelve_hours_ago)
        return (since.isoformat(), now.isoformat())
    if period.lower() in ("yesterday",):
        y = now - dt.timedelta(days=1)
        start = y.replace(hour=0, minute=0, second=0, microsecond=0)
        end = y.replace(hour=23, minute=59, second=59, microsecond=0)
        return (start.isoformat(), end.isoformat())
    if period.lower() in ("24h", "24hours", "24", "day"):
        since = now - dt.timedelta(hours=24)
        return (since.isoformat(), now.isoformat())
    if period.lower() in ("week", "thisweek"):
        weekday = now.weekday()
        start = (now - dt.timedelta(days=weekday)).replace(hour=0, minute=0, second=0, microsecond=0)
        return (start.isoformat(), now.isoformat())
    raise ValueError(f"Unsupported period: {period}")


def _build_preview(period: str, project: str, wakatime_file: str | None, cfg: Dict[str, Any]) -> Dict[str, Any]:
    jira = cfg.get("jira") or {}
    jira_site = jira.get("site", "") if isinstance(jira, dict) else (cfg.get("jira.site") or "")
    issue_rx = ((cfg.get("regex") or {}).get("issueKey") if isinstance(cfg.get("regex"), dict) else cfg.get("regex.issueKey")) or r"[A-Z][A-Z0-9]+-\d+"
    since, until = _period_bounds(period)

    commits = get_commits(project, since, until)
    groups = group_commits_by_issue(commits, issue_rx)
    total_seconds = load_total_seconds_from_file(wakatime_file) if wakatime_file else 0.0
    total_commits = sum(len(v) for v in groups.values())

    issues: List[Dict[str, Any]] = []
    for key, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        seconds = total_seconds * (len(items) / total_commits) if total_seconds and total_commits else 0.0
        url = f"{jira_site.rstrip('/')}/browse/{key}" if jira_site else None
        comment_lines: List[str] = []
        seen: set[str] = set()
        for c in items:
            subj = c.subject.strip()
            if subj and subj not in seen:
                comment_lines.append(subj)
                seen.add(subj)
            if len(comment_lines) >= 5:
                break
        issues.append({
            "key": key,
            "url": url,
            "seconds": int(round(seconds)),
            "comment": comment_lines,
            "commits": [c.sha for c in items],
        })

    return {
        "period": period,
        "since": since,
        "until": until,
        "project": project,
        "wakatime_seconds": int(round(total_seconds)),
        "issues": issues,
    }


def handle_start(args: argparse.Namespace) -> int:
    cfg_path = _default_config_path()
    existing = load_config(cfg_path)

    print("skuld start — configure WakaTime + Jira/MCP")
    wakatime_api = input("WakaTime API key: ").strip() or (existing.get("wakatime", {}).get("apiKey") if isinstance(existing.get("wakatime"), dict) else existing.get("wakatime.apiKey"))
    jira_site = input("Jira site (https://your-org.atlassian.net): ").strip() or ((existing.get("jira") or {}).get("site") if isinstance(existing.get("jira"), dict) else existing.get("jira.site"))
    jira_email = input("Jira email: ").strip() or ((existing.get("jira") or {}).get("email") if isinstance(existing.get("jira"), dict) else existing.get("jira.email"))
    jira_token = input("Jira API token: ").strip() or ((existing.get("jira") or {}).get("apiToken") if isinstance(existing.get("jira"), dict) else existing.get("jira.apiToken"))
    mcp_endpoint = input("MCP endpoint (optional): ").strip() or ((existing.get("mcp") or {}).get("endpoint") if isinstance(existing.get("mcp"), dict) else existing.get("mcp.endpoint", ""))
    mcp_auth = input("MCP auth (optional): ").strip() or ((existing.get("mcp") or {}).get("auth") if isinstance(existing.get("mcp"), dict) else existing.get("mcp.auth", ""))

    doc = []
    doc.append("# skuld configuration")
    doc.append("jira:")
    doc.append(f"  site: {jira_site}")
    doc.append(f"  email: {jira_email}")
    doc.append(f"  apiToken: {jira_token}")
    if mcp_endpoint or mcp_auth:
        doc.append("mcp:")
        if mcp_endpoint:
            doc.append(f"  endpoint: {mcp_endpoint}")
        if mcp_auth:
            doc.append(f"  auth: {mcp_auth}")
    doc.append("regex:")
    doc.append("  issueKey: \"[A-Z][A-Z0-9]+-\\\\d+\"")
    doc.append("time:")
    doc.append("  zone: local")
    doc.append("  minLogMinutes: parity")
    doc.append("  aggregationWindow: cli")
    doc.append("comment:")
    doc.append("  maxLines: 5")
    doc.append("  includeCommitHashes: true")
    doc.append("state:")
    doc.append("  path: ~/.local/share/skuld/state.sqlite")
    doc.append("llm:")
    doc.append("  enabled: true")
    doc.append("  maxCommits: 10")
    doc.append("  includeDiff: false")
    doc.append("wakatime:")
    doc.append(f"  apiKey: {wakatime_api}")

    cfg_path = pathlib.Path("~/.skuld.yaml").expanduser()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with cfg_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(doc) + "\n")
    print(f"Wrote config to {cfg_path}")
    return 0


def handle_sync(args: argparse.Namespace) -> int:
    cfg = load_config(_default_config_path())
    period = args.period or "today"
    preview = _build_preview(period, args.project or os.getcwd(), args.wakatime_file, cfg)

    if args.test:
        # Pretty print preview
        print("Worklog Preview (dry-run)")
        print(f"Period: {preview['since']} → {preview['until']}")
        total = preview.get("wakatime_seconds", 0)
        if not preview["issues"]:
            print("No issue keys found in commit messages for this period.")
            if total:
                print(f"Unattributed WakaTime total: {format_seconds(total)}")
            return 0
        for issue in preview["issues"]:
            url = issue.get("url") or f"{issue['key']}"
            seconds = issue.get("seconds", 0)
            print("-")
            print(f"Issue: {issue['key']}")
            print(f"Link:  {url}")
            if total:
                print(f"Time:  {format_seconds(seconds)} (of {format_seconds(total)})")
            else:
                print("Time:  (no WakaTime totals provided; use --wakatime-file)")
            lines = issue.get("comment", [])
            if lines:
                print("Comment draft:")
                for ln in lines:
                    print(f"  - {ln}")
        return 0

    # Default: real sync (to be implemented). For safety, we currently noop and print guidance.
    print("Sync is not yet wired to Jira. Use --test for preview. Next step: implement REST/MCP writers.")
    print(json.dumps(preview, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="skuld", description="Skuld: WakaTime + Git → Jira worklogs")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("start", help="Initialize configuration (WakaTime + Jira/MCP)")
    sp.set_defaults(func=handle_start)

    sy = sub.add_parser("sync", help="Sync worklogs for a period")
    sy.add_argument("period", nargs="?", choices=["today", "yesterday", "week"], help="Time range to analyze")
    sy.add_argument("--test", action="store_true", default=False, help="Dry-run: print what would be logged")
    sy.add_argument("--project", default=None, help="Project/repo path (optional)")
    sy.add_argument("--wakatime-file", default=None, help="Path to a WakaTime summaries JSON file for the period")
    sy.add_argument("--use-rest", action="store_true", default=False, help="Use Jira REST instead of MCP")
    sy.set_defaults(func=handle_sync)

    return p


def main(argv: Any = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

