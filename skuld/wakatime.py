import json
from pathlib import Path
from typing import Any, Dict, Optional
import configparser
from urllib.parse import urlencode
from urllib.request import urlopen, Request
import ssl



def _from_summary_record(rec: Dict[str, Any]) -> float:
    if "grand_total" in rec and isinstance(rec["grand_total"], dict):
        return float(rec["grand_total"].get("total_seconds", 0.0))
    if "total_seconds" in rec:
        return float(rec.get("total_seconds", 0.0))
    return 0.0


def load_total_seconds_from_file(path: str) -> float:
    p = Path(path)
    if not p.exists():
        return 0.0
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        if "cumulative_total" in data and isinstance(data["cumulative_total"], dict):
            return float(data["cumulative_total"].get("seconds", 0.0) or data["cumulative_total"].get("total_seconds", 0.0))
        if "data" in data and isinstance(data["data"], list) and data["data"]:
            return float(sum(_from_summary_record(rec) for rec in data["data"]))
        return _from_summary_record(data)
    if isinstance(data, list) and data:
        return float(sum(_from_summary_record(rec) for rec in data))
    return 0.0


def _date_part(iso: str) -> str:
    # Expect yyyy-mm-dd from ISO string
    return iso[:10]


def fetch_total_seconds(api_key: str, since_iso: str, until_iso: str, project: Optional[str] = None, timeout: int = 10) -> float:
    if not api_key:
        return 0.0
    params = {
        "start": _date_part(since_iso),
        "end": _date_part(until_iso),
        "api_key": api_key,
    }
    if project:
        params["project"] = project
    qs = urlencode(params)
    url = f"https://wakatime.com/api/v1/users/current/summaries?{qs}"
    # Using default SSL context; WakaTime uses HTTPS
    req = Request(url)
    ctx = ssl.create_default_context()
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            data = json.load(resp)
    except Exception:
        return 0.0
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        total = 0.0
        for rec in data["data"]:
            if isinstance(rec, dict) and "grand_total" in rec:
                gt = rec.get("grand_total") or {}
                try:
                    total += float(gt.get("total_seconds", 0.0))
                except Exception:
                    pass
        return float(total)
    return 0.0


def fetch_summary(api_key: str, since_iso: str, until_iso: str, project: Optional[str] = None, timeout: int = 10) -> Dict[str, Any]:
    """
    Returns a summary dict with keys:
    {
      "total_seconds": float,
      "branches": { branch_name: seconds }
    }
    Aggregates over days in the range.
    """
    out = {
        "total_seconds": 0.0,
        "branches": {},
        "projects": {},
    }
    if not api_key:
        return out
    params = {
        "start": _date_part(since_iso),
        "end": _date_part(until_iso),
        "api_key": api_key,
    }
    if project:
        params["project"] = project
    qs = urlencode(params)
    url = f"https://wakatime.com/api/v1/users/current/summaries?{qs}"
    req = Request(url)
    ctx = ssl.create_default_context()
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            data = json.load(resp)
    except Exception:
        return out
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        return out
    total = 0.0
    branches: Dict[str, float] = {}
    projects: Dict[str, float] = {}
    for rec in data["data"]:
        if not isinstance(rec, dict):
            continue
        if "grand_total" in rec and isinstance(rec["grand_total"], dict):
            try:
                total += float(rec["grand_total"].get("total_seconds", 0.0))
            except Exception:
                pass
        # Branch breakdown if available
        for b in rec.get("branches") or []:
            name = b.get("name")
            secs = b.get("total_seconds")
            if not name:
                continue
            try:
                val = float(secs or 0.0)
            except Exception:
                val = 0.0
            branches[name] = branches.get(name, 0.0) + val
        # Project breakdown if available
        for p in rec.get("projects") or []:
            pname = p.get("name")
            psecs = p.get("total_seconds")
            if not pname:
                continue
            try:
                pval = float(psecs or 0.0)
            except Exception:
                pval = 0.0
            projects[pname] = projects.get(pname, 0.0) + pval
    out["total_seconds"] = float(total)
    out["branches"] = branches
    out["projects"] = projects
    return out


def fetch_durations_summary(api_key: str, since_iso: str, until_iso: str, project: Optional[str] = None, timeout: int = 10) -> Dict[str, Any]:
    """
    Aggregate per-branch seconds using WakaTime Durations API for the window [since, until].
    Returns { "total_seconds": float, "branches": { name: seconds } }
    Falls back to empty values on any error.
    """
    out: Dict[str, Any] = {"total_seconds": 0.0, "branches": {}}
    if not api_key:
        return out
    # Normalize window bounds
    try:
        import datetime as dt
        since_dt = dt.datetime.fromisoformat(since_iso)
        until_dt = dt.datetime.fromisoformat(until_iso)
    except Exception:
        return out
    # Ensure timezone-aware for comparisons; assume local if missing
    local_tz = dt.datetime.now().astimezone().tzinfo
    if since_dt.tzinfo is None:
        since_dt = since_dt.replace(tzinfo=local_tz)
    if until_dt.tzinfo is None:
        until_dt = until_dt.replace(tzinfo=local_tz)
    # Convert to POSIX for filtering
    since_ts = since_dt.timestamp()
    until_ts = until_dt.timestamp()

    total = 0.0
    branches: Dict[str, float] = {}

    # Iterate per-day to query durations (API is day-scoped)
    day = since_dt.date()
    end_day = until_dt.date()
    ctx = ssl.create_default_context()
    while day <= end_day:
        params = {
            "date": day.isoformat(),
            "api_key": api_key,
        }
        if project:
            params["project"] = project
        url = f"https://wakatime.com/api/v1/users/current/durations?{urlencode(params)}"
        try:
            req = Request(url)
            with urlopen(req, timeout=timeout, context=ctx) as resp:
                data = json.load(resp)
        except Exception:
            day = day.fromordinal(day.toordinal() + 1)
            continue
        # Expect list or dict with "data" list
        records = []
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict) and isinstance(data.get("data"), list):
            records = data.get("data") or []
        for rec in records:
            try:
                dur = float(rec.get("duration") or rec.get("seconds") or 0.0)
            except Exception:
                dur = 0.0
            if dur <= 0:
                continue
            # rec["time"] is a unix epoch seconds, rec["branch"] may be present
            try:
                ts = float(rec.get("time") or 0.0)
            except Exception:
                ts = 0.0
            if ts <= 0.0 or ts < since_ts or ts > until_ts:
                continue
            bname = rec.get("branch") or ""
            total += dur
            if bname:
                branches[bname] = branches.get(bname, 0.0) + dur
        day = day.fromordinal(day.toordinal() + 1)
    out["total_seconds"] = float(total)
    out["branches"] = branches
    return out


def discover_api_key() -> Optional[str]:
    """Attempt to locate a local WakaTime API key from ~/.wakatime.cfg."""
    cfg_path = Path("~/.wakatime.cfg").expanduser()
    if not cfg_path.exists():
        return None
    cp = configparser.ConfigParser()
    try:
        cp.read(cfg_path)
        for section in ("settings", cp.default_section):
            if cp.has_option(section, "api_key"):
                val = cp.get(section, "api_key").strip()
                if val:
                    return val
    except Exception:
        return None
    return None
