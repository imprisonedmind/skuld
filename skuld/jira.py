import base64
import json
from typing import Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import ssl
import datetime as dt


def _auth_header(email: str, api_token: str) -> str:
    token = base64.b64encode(f"{email}:{api_token}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def search_issues(site: str, email: str, api_token: str, keys: List[str], timeout: int = 10) -> Dict[str, Dict[str, str]]:
    """
    Return mapping: key -> { 'summary': str, 'url': str }
    Filters to issues assigned to the current user via JQL.
    Swallows errors and returns empty mapping on failure.
    """
    if not (site and email and api_token and keys):
        return {}
    ctx = ssl.create_default_context()
    headers = {
        "Authorization": _auth_header(email, api_token),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    results: Dict[str, Dict[str, str]] = {}

    # Chunk keys to avoid JQL length limits
    CHUNK = 50
    for i in range(0, len(keys), CHUNK):
        chunk = keys[i : i + CHUNK]
        # JQL: key in (K1,K2,...) AND assignee=currentUser()
        jql_keys = ",".join(chunk)
        jql = f"key in ({jql_keys}) AND assignee = currentUser()"
        body = {
            "jql": jql,
            "maxResults": len(chunk),
            "fields": ["summary", "key"],
        }
        url = f"{site.rstrip('/')}/rest/api/3/search"
        req = Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        try:
            with urlopen(req, timeout=timeout, context=ctx) as resp:
                data = json.load(resp)
        except Exception:
            continue
        for issue in (data.get("issues") or []):
            key = issue.get("key")
            fields = issue.get("fields") or {}
            summary = fields.get("summary") or ""
            if key:
                results[key] = {
                    "summary": summary,
                    "url": f"{site.rstrip('/')}/browse/{key}",
                }
    return results


def search_issues_debug(site: str, email: str, api_token: str, keys: List[str], timeout: int = 10):
    """
    Like search_issues, but returns (results, meta) where meta includes errors/status.
    """
    results: Dict[str, Dict[str, str]] = {}
    meta: Dict[str, any] = {"chunks": []}
    if not (site and email and api_token and keys):
        meta["error"] = "missing_params"
        return results, meta
    ctx = ssl.create_default_context()
    headers = {
        "Authorization": _auth_header(email, api_token),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    CHUNK = 50
    for i in range(0, len(keys), CHUNK):
        chunk = keys[i : i + CHUNK]
        jql_keys = ",".join(chunk)
        jql = f"key in ({jql_keys}) AND assignee = currentUser()"
        body = {"jql": jql, "maxResults": len(chunk), "fields": ["summary", "key"]}
        url = f"{site.rstrip('/')}/rest/api/3/search"
        entry = {"jql": jql, "keys": chunk, "status": None, "error": None}
        try:
            req = Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
            with urlopen(req, timeout=timeout, context=ctx) as resp:
                entry["status"] = getattr(resp, "status", None)
                data = json.load(resp)
        except Exception as e:
            entry["error"] = str(e)
            meta["chunks"].append(entry)
            continue
        for issue in (data.get("issues") or []):
            key = issue.get("key")
            fields = issue.get("fields") or {}
            summary = fields.get("summary") or ""
            if key:
                results[key] = {"summary": summary, "url": f"{site.rstrip('/')}/browse/{key}"}
        meta["chunks"].append(entry)
    return results, meta


def get_myself(site: str, email: str, api_token: str, timeout: int = 10):
    ctx = ssl.create_default_context()
    headers = {
        "Authorization": _auth_header(email, api_token),
        "Accept": "application/json",
    }
    url = f"{site.rstrip('/')}/rest/api/3/myself"
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            data = json.load(resp)
            return {
                "accountId": data.get("accountId"),
                "emailAddress": data.get("emailAddress"),
                "displayName": data.get("displayName"),
            }, None
    except Exception as e:
        return None, str(e)


def search_issues_noassignee(site: str, email: str, api_token: str, keys: List[str], timeout: int = 10):
    """Search issues by keys without assignee filter; return mapping key -> fields.
    Falls back to per-issue GET if search fails.
    """
    ctx = ssl.create_default_context()
    headers = {
        "Authorization": _auth_header(email, api_token),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    url = f"{site.rstrip('/')}/rest/api/3/search"
    results: Dict[str, Dict[str, str]] = {}
    meta: Dict[str, any] = {"chunks": []}
    CHUNK = 50
    for i in range(0, len(keys), CHUNK):
        chunk = keys[i : i + CHUNK]
        jql_keys = ",".join(chunk)
        jql = f"key in ({jql_keys})"
        body = {"jql": jql, "maxResults": len(chunk), "fields": ["summary", "key", "assignee"]}
        entry = {"jql": jql, "keys": chunk, "status": None, "error": None}
        try:
            req = Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
            with urlopen(req, timeout=timeout, context=ctx) as resp:
                entry["status"] = getattr(resp, "status", None)
                data = json.load(resp)
        except Exception as e:
            entry["error"] = str(e)
            meta["chunks"].append(entry)
            # Fallback to per-issue GETs for this chunk
            for key in chunk:
                info, err = get_issue(site, email, api_token, key, timeout=timeout)
                if info:
                    results[key] = info
            continue
        for issue in (data.get("issues") or []):
            key = issue.get("key")
            fields = issue.get("fields") or {}
            summary = fields.get("summary") or ""
            assignee = fields.get("assignee") or {}
            acct = assignee.get("accountId")
            email_addr = assignee.get("emailAddress")
            if key:
                results[key] = {
                    "summary": summary,
                    "url": f"{site.rstrip('/')}/browse/{key}",
                    "assigneeAccountId": acct,
                    "assigneeEmail": email_addr,
                }
        meta["chunks"].append(entry)
    return results, meta


def get_issue(site: str, email: str, api_token: str, key: str, timeout: int = 10):
    ctx = ssl.create_default_context()
    headers = {
        "Authorization": _auth_header(email, api_token),
        "Accept": "application/json",
    }
    url = f"{site.rstrip('/')}/rest/api/3/issue/{key}?fields=summary,assignee"
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            data = json.load(resp)
            fields = data.get("fields") or {}
            summary = fields.get("summary") or ""
            assignee = fields.get("assignee") or {}
            acct = assignee.get("accountId")
            email_addr = assignee.get("emailAddress")
            return {
                "summary": summary,
                "url": f"{site.rstrip('/')}/browse/{key}",
                "assigneeAccountId": acct,
                "assigneeEmail": email_addr,
            }, None
    except Exception as e:
        return None, str(e)


def _parse_jira_datetime(s: str) -> dt.datetime | None:
    # Jira format example: 2025-10-15T12:34:56.000+0000
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return dt.datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def get_my_worklog_seconds(site: str, email: str, api_token: str, key: str, account_id: str | None,
                           since_iso: str, until_iso: str, timeout: int = 10) -> tuple[int, str | None]:
    """Sum timeSpentSeconds for current user on issue within [since, until]."""
    ctx = ssl.create_default_context()
    headers = {
        "Authorization": _auth_header(email, api_token),
        "Accept": "application/json",
    }
    url = f"{site.rstrip('/')}/rest/api/3/issue/{key}/worklog?startAt=0&maxResults=1000"
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            data = json.load(resp)
    except Exception as e:
        return 0, str(e)

    # Normalize window to UTC-aware datetimes, assuming since/until are in local time
    try:
        _start = dt.datetime.fromisoformat(since_iso)
    except Exception:
        _start = None
    try:
        _end = dt.datetime.fromisoformat(until_iso)
    except Exception:
        _end = None
    local_tz = dt.datetime.now().astimezone().tzinfo
    start = _start.replace(tzinfo=local_tz).astimezone(dt.timezone.utc) if _start and local_tz else None
    end = _end.replace(tzinfo=local_tz).astimezone(dt.timezone.utc) if _end and local_tz else None

    total = 0
    for wl in (data.get("worklogs") or []):
        author = wl.get("author") or {}
        if account_id and author.get("accountId") != account_id:
            continue
        started_str = wl.get("started")
        d = _parse_jira_datetime(started_str) if started_str else None
        if d is None:
            continue
        # Convert Jira time to UTC for comparison
        d_utc = d.astimezone(dt.timezone.utc) if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
        if start and d_utc < start:
            continue
        if end and d_utc > end:
            continue
        try:
            secs = int(wl.get("timeSpentSeconds") or 0)
        except Exception:
            secs = 0
        total += secs
    return total, None
