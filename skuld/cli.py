import argparse
import datetime as dt
import json
import os
import pathlib
from typing import Any, Dict, List, Tuple
import subprocess

from .git import get_commits, group_commits_by_issue, get_commits_for_branches
from .util import format_seconds, format_date, format_time
from .wakatime import load_total_seconds_from_file, fetch_total_seconds, fetch_summary, discover_api_key
from .jira import search_issues, search_issues_debug, get_myself, search_issues_noassignee, get_my_worklog_seconds, add_worklog, add_comment
from .state import seen as state_seen, record as state_record


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
    text = ""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    # Try PyYAML first if available
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
        return data or {}
    except Exception:
        pass

    # Naive YAML parser for simple nested mappings (no lists required for core usage)
    def parse_naive_yaml(src: str) -> Dict[str, Any]:
        root: Dict[str, Any] = {}
        stack: list[tuple[int, Dict[str, Any]]] = [(0, root)]
        for raw in src.splitlines():
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            line = raw.strip()
            while stack and indent < stack[-1][0]:
                stack.pop()
            if ":" not in line:
                continue
            key, rest = line.split(":", 1)
            key = key.strip()
            val = rest.strip()
            parent = stack[-1][1]
            if val == "":
                new_map: Dict[str, Any] = {}
                parent[key] = new_map
                stack.append((indent + 2, new_map))
            else:
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                parent[key] = val
        return root

    try:
        return parse_naive_yaml(text)
    except Exception:
        return {}


def _save_config_prefer_skuld(data: Dict[str, Any]) -> pathlib.Path:
    """Write config to ~/.skuld.yaml, using PyYAML if available, otherwise a simple dumper."""
    cfg_path = pathlib.Path("~/.skuld.yaml").expanduser()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    # Backup existing file once per write
    if cfg_path.exists():
        try:
            bak = cfg_path.with_suffix(cfg_path.suffix + ".bak")
            bak.write_text(cfg_path.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
    # Merge with existing on disk to avoid overwrites
    try:
        existing_text = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else None
    except Exception:
        existing_text = None

    def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                _deep_merge(dst[k], v)
            else:
                dst[k] = v
        return dst

    if existing_text:
        try:
            import yaml  # type: ignore
            existing = yaml.safe_load(existing_text) or {}
        except Exception:
            # Fallback to naive loader
            existing = load_config(cfg_path)
        if not isinstance(existing, dict):
            existing = {}
        merged = _deep_merge(existing, data)
    else:
        merged = data
    try:
        import yaml  # type: ignore
        with cfg_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(merged, f, sort_keys=False)
        return cfg_path
    except Exception:
        pass

    def dump_map(d: Dict[str, Any], indent: int = 0) -> List[str]:
        lines: List[str] = []
        sp = " " * indent
        for k, v in d.items():
            if isinstance(v, dict):
                lines.append(f"{sp}{k}:")
                lines.extend(dump_map(v, indent + 2))
            else:
                sval = str(v)
                # Quote if contains special chars
                if any(ch in sval for ch in [":", "#", "\"", "'", "\n"]):
                    sval = sval.replace("\\", "\\\\").replace("\"", "\\\"")
                    sval = f'"{sval}"'
                lines.append(f"{sp}{k}: {sval}")
        return lines

    text = "\n".join(dump_map(merged)) + "\n"
    with cfg_path.open("w", encoding="utf-8") as f:
        f.write(text)
    return cfg_path


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


def _project_mapping(cfg: Dict[str, Any], project_path: str) -> str | None:
    # Config shape: projects: { "/path/to/repo": { wakatimeProject: "name", jiraProjectKey: "SOT" } }
    projs = cfg.get("projects")
    if not isinstance(projs, dict):
        return None
    # Only exact path match (normalized). No basename fallback to avoid cross‑repo bleed.
    pp = os.path.realpath(os.path.abspath(os.path.expanduser(project_path)))
    # Also check normalized keys in config
    for k, v in projs.items():
        if not isinstance(v, dict):
            continue
        kk = os.path.realpath(os.path.abspath(os.path.expanduser(k)))
        if kk == pp:
            return v.get("wakatimeProject")
    return None


def _git_remote_repo_name(project_path: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", project_path, "remote", "get-url", "origin"], capture_output=True, text=True, check=False)
    except Exception:
        return None
    if out.returncode != 0 or not out.stdout:
        return None
    url = out.stdout.strip()
    # Extract last path segment
    name = url
    if ":" in url and not url.startswith("http"):
        name = url.split(":", 1)[-1]
    if "/" in name:
        name = name.rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    # Sanitize
    return name or None


def _prompt(msg: str, default: str | None = None) -> str:
    sfx = f" [{default}]" if default else ""
    val = input(f"{msg}{sfx}: ").strip()
    return val or (default or "")


def handle_add(args: argparse.Namespace) -> int:
    """Add a per-repo mapping to ~/.skuld.yaml for faster, more reliable syncs."""
    cfg = load_config(_default_config_path())
    if not isinstance(cfg, dict):
        cfg = {}
    repo = os.path.abspath(os.path.expanduser(args.project or os.getcwd()))

    # Ensure wakatime API key available (for project discovery)
    wk = cfg.get("wakatime") if isinstance(cfg.get("wakatime"), dict) else {}
    api_key = wk.get("apiKey") if isinstance(wk, dict) else None
    if not api_key:
        api_key = cfg.get("wakatime.apiKey") if isinstance(cfg, dict) else None
    if not api_key:
        api_key = discover_api_key() or ""
    if not api_key:
        api_key = _prompt("WakaTime API key (for project discovery)")
        if api_key:
            if not isinstance(wk, dict):
                wk = {}
            wk["apiKey"] = api_key
            cfg["wakatime"] = wk

    # Collect candidate projects from WakaTime (last 14 days)
    chosen_project = None
    base = os.path.basename(repo)
    remote = _git_remote_repo_name(repo) or ""
    if api_key:
        since = (dt.datetime.now() - dt.timedelta(days=14)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        until = dt.datetime.now().isoformat()
        summary_all = fetch_summary(api_key, since, until, project=None)
        projects = summary_all.get("projects", {}) or {}
        candidates: List[tuple[int, float, str]] = []
        def norm(s: str) -> str:
            return "".join(ch.lower() for ch in s if ch.isalnum())
        for pname, psecs in projects.items():
            score = 0
            if pname == base: score += 2
            if remote and pname == remote: score += 2
            if norm(pname) == norm(base) or (remote and norm(pname) == norm(remote)): score += 1
            candidates.append((score, float(psecs or 0.0), pname))
        candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
        top = candidates[:10]
        if top:
            print("Detected WakaTime projects (by similarity and recent time):")
            for idx, (_sc, secs, pname) in enumerate(top, start=1):
                print(f"  {idx}. {pname}  ({format_seconds(secs)})")
            choice = _prompt("Choose a project number or enter a name", default=str(1))
            if choice.isdigit():
                ci = int(choice)
                if 1 <= ci <= len(top):
                    chosen_project = top[ci-1][2]
            if not chosen_project:
                chosen_project = choice
    if not chosen_project:
        chosen_project = _prompt("WakaTime project name (manual)")

    jira_key = _prompt("Jira project key prefix (optional)", default="")

    # Merge into config under projects
    projects_map = cfg.get("projects") if isinstance(cfg.get("projects"), dict) else None
    if not isinstance(projects_map, dict):
        projects_map = {}
        cfg["projects"] = projects_map
    entry = {"wakatimeProject": chosen_project}
    if jira_key:
        entry["jiraProjectKey"] = jira_key
    projects_map[repo] = entry

    path = _save_config_prefer_skuld(cfg)
    print(f"Added mapping for {repo}\n  wakatimeProject: {chosen_project}\n  jiraProjectKey: {jira_key or '(none)'}\nSaved to {path}")
    return 0


def _build_preview(period: str, project: str, wakatime_file: str | None, cfg: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(cfg, dict):
        cfg = {}
    jira = cfg.get("jira") or {}
    jira_site = jira.get("site", "") if isinstance(jira, dict) else (cfg.get("jira.site") or "")
    issue_rx_raw = ((cfg.get("regex") or {}).get("issueKey") if isinstance(cfg.get("regex"), dict) else cfg.get("regex.issueKey")) or r"[A-Z][A-Z0-9]+-\d+"
    # Normalize escaped sequences like "\\d" → "\d" without triggering warnings
    issue_rx = issue_rx_raw.replace("\\\\", "\\")
    since, until = _period_bounds(period)

    commits = get_commits(project, since, until)
    groups = group_commits_by_issue(commits, issue_rx)

    # Determine last recorded upload window per issue (from local state) to bound comment commits.
    state_path = (cfg.get("state", {}).get("path") if isinstance(cfg.get("state"), dict) else cfg.get("state.path")) or "~/.local/share/skuld/state.json"
    last_until_by_issue: Dict[str, str] = {}
    try:
        p = pathlib.Path(os.path.expanduser(state_path)).resolve()
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            entries = data.get("entries") if isinstance(data, dict) else None
            if isinstance(entries, list):
                for e in entries:
                    if not isinstance(e, dict):
                        continue
                    key = e.get("issue")
                    u = e.get("until")
                    if not key or not u:
                        continue
                    # Track the max until per issue
                    prev = last_until_by_issue.get(key)
                    if not prev or (str(u) > str(prev)):
                        last_until_by_issue[key] = str(u)
    except Exception:
        # If state cannot be read, proceed without additional bounding
        last_until_by_issue = {}

    # If Jira credentials exist, fetch summaries and filter to current user's assignments.
    jira_email = (jira.get("email") if isinstance(jira, dict) else cfg.get("jira.email")) or ""
    jira_token = (jira.get("apiToken") if isinstance(jira, dict) else cfg.get("jira.apiToken")) or ""
    jira_info: Dict[str, Dict[str, str]] = {}
    ownership_verified = False
    debug_info: Dict[str, Any] = {
        "jira": {
            "site_configured": bool(jira_site),
            "email_configured": bool((jira.get("email") if isinstance(jira, dict) else cfg.get("jira.email")) or ""),
            "token_configured": bool((jira.get("apiToken") if isinstance(jira, dict) else cfg.get("jira.apiToken")) or ""),
            "ownership_verified": False,
        },
        "git": {
            "repo": project,
            "since": since,
            "until": until,
            "commits_scanned": len(commits),
            "keys_from_commits": sorted(list(groups.keys())),
        },
        "wakatime": {
            "api_key_source": None,
            "chosen_project": None,
            "projects": {},
            "branches": {},
        },
        "keys": {
            "candidate": [],
            "from_branches": [],
        },
        "regex": {
            "configured": issue_rx_raw,
            "normalized": issue_rx,
        },
        "jira_filtered_keys": [],
    }
    # Candidate keys from commits so far; will union with WakaTime keys below
    candidate_keys: set[str] = set(groups.keys())
    if jira_site and jira_email and jira_token and candidate_keys:
        keys = sorted(candidate_keys)
        # First, resolve current user to get accountId and validate token
        me, me_err = get_myself(jira_site, jira_email, jira_token)
        debug_info["jira"]["whoami_error"] = me_err
        debug_info["jira"]["whoami_accountId"] = me.get("accountId") if me else None
        # Fetch issues without assignee filter; filter locally by accountId if available
        jira_all, meta = search_issues_noassignee(jira_site, jira_email, jira_token, keys)
        debug_info["jira"]["meta"] = meta
        jira_info = {}
        if jira_all and me and me.get("accountId"):
            acct = me["accountId"]
            for k, v in jira_all.items():
                if v.get("assigneeAccountId") == acct:
                    jira_info[k] = {"summary": v.get("summary"), "url": v.get("url")}
        elif jira_all and jira_email:
            # Fallback to email match if accountId not available
            for k, v in jira_all.items():
                if v.get("assigneeEmail") == jira_email:
                    jira_info[k] = {"summary": v.get("summary"), "url": v.get("url")}
        if jira_info:
            ownership_verified = True
            groups = {k: v for k, v in groups.items() if k in jira_info}
            debug_info["jira_filtered_keys"] = sorted(list(jira_info.keys()))
    debug_info["jira"]["ownership_verified"] = ownership_verified
    # Pull WakaTime: prefer explicit JSON file; else try API if key configured
    total_seconds = 0.0
    branch_seconds: Dict[str, float] = {}
    branches_by_key: Dict[str, List[str]] = {}
    if wakatime_file:
        total_seconds = load_total_seconds_from_file(wakatime_file)
    else:
        wk = cfg.get("wakatime") or {}
        api_key = wk.get("apiKey") if isinstance(wk, dict) else cfg.get("wakatime.apiKey")
        if not api_key:
            api_key = discover_api_key() or api_key
        if api_key:
            debug_info["wakatime"]["api_key_source"] = "config" if (wk.get("apiKey") if isinstance(wk, dict) else cfg.get("wakatime.apiKey")) else "wakatime.cfg"
            mapped_project = _project_mapping(cfg, project)
            if mapped_project:
                summary = fetch_summary(api_key, since, until, project=mapped_project)
                debug_info["wakatime"]["chosen_project"] = mapped_project
                total_seconds = float(summary.get("total_seconds", 0.0))
                branch_seconds = dict(summary.get("branches", {}))
                debug_info["wakatime"]["branches"] = branch_seconds
            else:
                # No auto-detection: require an explicit per-repo mapping via `skuld add`.
                debug_info["wakatime"]["chosen_project"] = None
                debug_info["wakatime"]["note"] = "No repo mapping found; run `skuld add` in this repo."
    # Build allocation strictly from WakaTime branches → issue keys. No fabricated splits.
    import re as _re
    rx = _re.compile(issue_rx)
    alloc_by_key: Dict[str, float] = {}
    for bname, secs in (branch_seconds or {}).items():
        matches = rx.findall(bname or "")
        if not matches:
            continue
        for m in matches:
            alloc_by_key[m] = alloc_by_key.get(m, 0.0) + float(secs or 0.0)
            branches_by_key.setdefault(m, []).append(bname)
            candidate_keys.add(m)
    debug_info["keys"]["candidate"] = sorted(list(candidate_keys))
    debug_info["keys"]["from_branches"] = sorted(list(alloc_by_key.keys()))

    # If we have WakaTime-derived candidate keys but have not yet verified ownership, try now
    if jira_site and jira_email and jira_token and candidate_keys and not ownership_verified:
        # As a last resort, try the previous filtered search (may fail 410 in some setups)
        keys = sorted(candidate_keys)
        jira_info2, meta2 = search_issues_debug(jira_site, jira_email, jira_token, keys)
        if jira_info2:
            ownership_verified = True
            groups = {k: v for k, v in groups.items() if k in jira_info2}
            debug_info["jira_filtered_keys"] = sorted(list(jira_info2.keys()))
        debug_info["jira"]["meta_fallback"] = meta2

    issues: List[Dict[str, Any]] = []
    # Build final key set: union of commit keys and WakaTime keys
    final_keys = sorted(candidate_keys)
    for key in final_keys:
        # Enforce ownership if verified
        if ownership_verified and key not in jira_info:
            continue
        items = groups.get(key, [])
        # Also pull commits that are on any WakaTime-observed branches matching this key
        branch_list = branches_by_key.get(key, [])
        if branch_list:
            try:
                bcommits = get_commits_for_branches(project, branch_list, since, until)
                if bcommits:
                    # Merge with items (dedupe by sha)
                    have = {c.sha for c in items}
                    for c in bcommits:
                        if c.sha not in have:
                            items.append(c)
                            have.add(c.sha)
            except Exception:
                pass
        # Filter commit items to only those after the last recorded upload for this issue (if any)
        last_u = last_until_by_issue.get(key)
        if last_u:
            try:
                # Dates are ISO 8601 strings; safe to compare as datetimes
                last_dt = dt.datetime.fromisoformat(last_u)
                filt: List[Any] = []
                for c in items:
                    try:
                        cd = dt.datetime.fromisoformat(c.date)
                        if cd > last_dt:
                            filt.append(c)
                    except Exception:
                        # If parsing fails, keep the commit (avoid hiding data)
                        filt.append(c)
                items = filt
            except Exception:
                pass
        seconds = alloc_by_key.get(key, 0.0)
        if seconds <= 0:
            continue  # Skip keys without WakaTime-backed time
        url = jira_info.get(key, {}).get("url") if jira_info else (f"{jira_site.rstrip('/')}/browse/{key}" if jira_site else None)
        summary = jira_info.get(key, {}).get("summary") if jira_info else None
        # Determine already logged seconds for current user in period
        already = 0
        acct = debug_info.get("jira", {}).get("whoami_accountId")
        if acct and jira_site and jira_email and jira_token:
            logged, _err = get_my_worklog_seconds(jira_site, jira_email, jira_token, key, acct, since, until)
            already = int(logged or 0)
        delta = max(0, int(round(seconds)) - already)
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
            "summary": summary,
            "seconds": int(round(seconds)),
            "already_logged": already,
            "delta": delta,
            "comment": comment_lines,
            "commits": [c.sha for c in items],
        })

    notes: List[str] = []
    if not ownership_verified:
        msg = "Jira ownership verification failed."
        if debug_info.get("jira", {}).get("meta", {}).get("chunks"):
            errs = [c for c in debug_info["jira"]["meta"]["chunks"] if c.get("error")]
            if errs:
                msg += f" Error: {errs[0]['error']}"
        notes.append(msg)
    if not alloc_by_key:
        notes.append("No WakaTime branch matches found for issue keys; no time allocated.")

    return {
        "period": period,
        "since": since,
        "until": until,
        "project": project,
        "wakatime_seconds": int(round(total_seconds)),
        "issues": issues,
        "notes": notes,
        "ownership_verified": ownership_verified,
        "candidate_keys": debug_info["keys"]["candidate"],
        "allocation": {k: int(round(v)) for k, v in alloc_by_key.items()},
        "debug": debug_info,
    }


def handle_start(args: argparse.Namespace) -> int:
    cfg_path = _default_config_path()
    existing = load_config(cfg_path)
    if not isinstance(existing, dict):
        existing = {}

    print("skuld start — configure WakaTime + Jira/MCP")
    # Safe accessors for defaults
    def _dget(mapobj, path_keys, default=""):
        cur = mapobj
        for k in path_keys:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(k)
        return cur or default

    wakatime_api = input("WakaTime API key: ").strip() or _dget(existing, ["wakatime", "apiKey"]) or existing.get("wakatime.apiKey", "")
    jira_site = input("Jira site (https://your-org.atlassian.net): ").strip() or _dget(existing, ["jira", "site"]) or existing.get("jira.site", "")
    jira_email = input("Jira email: ").strip() or _dget(existing, ["jira", "email"]) or existing.get("jira.email", "")
    jira_token = input("Jira API token: ").strip() or _dget(existing, ["jira", "apiToken"]) or existing.get("jira.apiToken", "")

    # Merge fields back into config and save
    cfg = existing.copy()
    if not isinstance(cfg.get("jira"), dict):
        cfg["jira"] = {}
    cfg["jira"]["site"] = jira_site
    cfg["jira"]["email"] = jira_email
    cfg["jira"]["apiToken"] = jira_token
    if not isinstance(cfg.get("regex"), dict):
        cfg["regex"] = {"issueKey": "[A-Z][A-Z0-9]+-\\d+"}
    if not isinstance(cfg.get("time"), dict):
        cfg["time"] = {"zone": "local", "minLogMinutes": "parity", "aggregationWindow": "cli"}
    if not isinstance(cfg.get("comment"), dict):
        cfg["comment"] = {"maxLines": 5, "includeCommitHashes": True}
    if not isinstance(cfg.get("state"), dict):
        cfg["state"] = {"path": "~/.local/share/skuld/state.json"}
    if not isinstance(cfg.get("wakatime"), dict):
        cfg["wakatime"] = {}
    cfg["wakatime"]["apiKey"] = wakatime_api

    out_path = _save_config_prefer_skuld(cfg)
    print(f"Wrote config to {out_path}")
    return 0


def handle_sync(args: argparse.Namespace) -> int:
    cfg = load_config(_default_config_path())
    if not isinstance(cfg, dict):
        cfg = {}
    period = args.period or "today"
    # Require per-repo mapping for all syncs; no auto-detect or fallback.
    project_path = os.path.abspath(os.path.expanduser(args.project or os.getcwd()))
    mapped = _project_mapping(cfg, project_path)
    if not mapped:
        print("This repo is not configured for Skuld.\nRun `skuld add` in this repo to map it to a WakaTime project (and optional Jira key).")
        return 2
    preview = _build_preview(period, project_path, args.wakatime_file, cfg)

    if args.test:
        # Printer: follow docs/printer.md formatting
        print("Worklog Preview (dry-run)")
        print(f"Period: {preview['since']} → {preview['until']}")
        total_all = preview.get("wakatime_seconds", 0)
        for n in preview.get("notes", []) or []:
            print(f"Note: {n}")
        if not preview["issues"]:
            if not preview.get("ownership_verified"):
                print("No issues to show because Jira ownership verification failed.")
            elif not preview.get("allocation"):
                print("No WakaTime branch matches for any issue keys in this period.")
            else:
                print("No issue keys found in commit messages for this period.")
            if total_all:
                print(f"Unattributed WakaTime total: {format_seconds(total_all)}")
            if getattr(args, "debug", False):
                print("\n[DEBUG] Details:")
                print(json.dumps(preview.get("debug", {}), indent=2))
            return 0
        if getattr(args, "debug", False):
            print("\n[DEBUG] Issues in preview (key → seconds):")
            print(json.dumps({i["key"]: i["seconds"] for i in preview["issues"]}, indent=2))
            print("\n[DEBUG] Full details:")
            print(json.dumps(preview.get("debug", {}), indent=2))
        now = dt.datetime.now()
        date_str = format_date(now)
        time_str = format_time(now)
        sep = "-" * 89
        printed_any = False
        for issue in preview["issues"]:
            seconds = int(issue.get("seconds", 0))
            already = int(issue.get("already_logged", 0))
            delta = int(issue.get("delta", seconds))
            if delta <= 0:
                continue
            # Use Jira summary when available (preferred)
            name = issue.get("summary")
            lines = issue.get("comment", []) or []
            print(sep)
            print(f"Issue: {issue['key']}")
            print(f"Name:  {name or ''}")
            print(f"Time to add:  {format_seconds(delta)}")
            print(f"Total Time: {format_seconds(seconds)}")
            if already:
                print(f"Already Logged: {format_seconds(already)}")
            print("Comment:")
            print(f"  [SKULD] - Adding `{format_seconds(delta)}` on `{date_str}` at `{time_str}`  ")
            for ln in lines[:5]:
                print(f"  - {ln}")
            printed_any = True
        if not printed_any:
            print("Nothing to add — all covered by existing Jira worklogs.")
        print(sep)
        return 0

    # Apply mode: upload Jira worklogs for positive deltas only, idempotently.
    if not preview.get("ownership_verified"):
        print("Aborting: Jira ownership verification failed; not uploading.")
        return 2

    state_path = (cfg.get("state", {}).get("path") if isinstance(cfg.get("state"), dict) else cfg.get("state.path")) or "~/.local/share/skuld/state.json"

    now = dt.datetime.now().astimezone()
    date_str = format_date(now)
    time_str = format_time(now)

    uploaded = []
    skipped = []
    errors = []
    # Extract Jira auth once
    jira_site = (cfg.get("jira") or {}).get("site") if isinstance(cfg.get("jira"), dict) else cfg.get("jira.site")
    jira_email = (cfg.get("jira") or {}).get("email") if isinstance(cfg.get("jira"), dict) else cfg.get("jira.email")
    jira_token = (cfg.get("jira") or {}).get("apiToken") if isinstance(cfg.get("jira"), dict) else cfg.get("jira.apiToken")

    for issue in preview["issues"]:
        seconds = int(issue.get("seconds", 0))
        delta = int(issue.get("delta", seconds))
        if delta <= 0:
            skipped.append({"key": issue["key"], "reason": "no_delta"})
            continue

        # Idempotency: if we already recorded this exact (issue, window, delta), skip
        if state_seen(state_path, issue["key"], preview["since"], preview["until"], delta):
            skipped.append({"key": issue["key"], "reason": "already_recorded"})
            continue

        # Build comment text per docs/printer.md
        lines = issue.get("comment", []) or []
        comment = f"[SKULD] - Adding `{format_seconds(delta)}` on `{date_str}` at `{time_str}`\n"
        for ln in lines[:5]:
            comment += f"- {ln}\n"

        data, err = add_worklog(
            site=jira_site,
            email=jira_email,
            api_token=jira_token,
            key=issue["key"],
            seconds=delta,
            started=now,
            comment=comment,
        )
        if err:
            errors.append({"key": issue["key"], "error": err})
            continue
        worklog_id = (data or {}).get("id") if isinstance(data, dict) else None
        state_record(state_path, issue["key"], preview["since"], preview["until"], delta, worklog_id=str(worklog_id) if worklog_id else None)
        # Also add an issue comment with the same content
        cdata, cerr = add_comment(
            site=jira_site,
            email=jira_email,
            api_token=jira_token,
            key=issue["key"],
            comment_text=comment,
        )
        if cerr:
            errors.append({"key": issue["key"], "error": f"comment: {cerr}"})
        comment_id = (cdata or {}).get("id") if isinstance(cdata, dict) else None
        uploaded.append({"key": issue["key"], "seconds": delta, "worklog_id": worklog_id, "comment_id": comment_id})

    # Summary
    print("Upload summary:")
    if uploaded:
        for u in uploaded:
            print(f"  + {u['key']}: {format_seconds(u['seconds'])} (worklog {u.get('worklog_id') or '-'}, comment {u.get('comment_id') or '-'})")
    else:
        print("  + No uploads (nothing to add)")
    if skipped:
        for s in skipped:
            print(f"  - {s['key']}: skipped ({s['reason']})")
    if errors:
        print("Errors:")
        for e in errors:
            print(f"  ! {e['key']}: {e['error']}")
    return 0 if uploaded and not errors else (1 if errors else 0)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="skuld", description="Skuld: WakaTime + Git → Jira worklogs")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("start", help="Initialize configuration (WakaTime + Jira/MCP)")
    sp.set_defaults(func=handle_start)

    ap = sub.add_parser("add", help="Add per-repo mapping for faster syncs")
    ap.add_argument("--project", default=None, help="Project/repo path (defaults to CWD)")
    ap.set_defaults(func=handle_add)

    sy = sub.add_parser("sync", help="Sync worklogs for a period")
    sy.add_argument("period", nargs="?", choices=["today", "yesterday", "week"], help="Time range to analyze")
    sy.add_argument("--test", action="store_true", default=False, help="Dry-run: print what would be logged")
    sy.add_argument("--project", default=None, help="Project/repo path (optional)")
    sy.add_argument("--wakatime-file", default=None, help="Path to a WakaTime summaries JSON file for the period")
    sy.add_argument("--debug", action="store_true", default=False, help="Print debug info about allocation")
    sy.set_defaults(func=handle_sync)

    return p


def main(argv: Any = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
