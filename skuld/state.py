import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


def _expand(p: str) -> Path:
    return Path(os.path.expanduser(p)).resolve()


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"entries": [], "last_sync": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            # Normalize structure for backward compatibility
            if not isinstance(data.get("entries"), list):
                data["entries"] = []
            if not isinstance(data.get("last_sync"), dict):
                data["last_sync"] = {}
            return data
    except Exception:
        pass
    return {"entries": [], "last_sync": {}}


def _save(path: Path, data: Dict[str, Any]) -> None:
    _ensure_dir(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _entry_id(issue: str, since: str, until: str, seconds: int) -> str:
    raw = f"{issue}|{since}|{until}|{seconds}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def seen(state_path: str, issue: str, since: str, until: str, seconds: int) -> bool:
    path = _expand(state_path)
    data = _load(path)
    eid = _entry_id(issue, since, until, seconds)
    return any(e.get("id") == eid for e in data.get("entries", []))


def record(state_path: str, issue: str, since: str, until: str, seconds: int, worklog_id: str | None = None) -> None:
    path = _expand(state_path)
    data = _load(path)
    eid = _entry_id(issue, since, until, seconds)
    data.setdefault("entries", []).append({
        "id": eid,
        "issue": issue,
        "since": since,
        "until": until,
        "seconds": int(seconds),
        "worklog_id": worklog_id,
    })
    _save(path, data)


def get_last_sync(state_path: str, project_path: str) -> Optional[str]:
    """Return the last sync upper bound (ISO string) for the given project path.
    Falls back to the max 'until' across entries if no explicit last_sync exists.
    """
    path = _expand(state_path)
    data = _load(path)
    last_sync_map = data.get("last_sync") or {}
    if isinstance(last_sync_map, dict):
        val = last_sync_map.get(str(project_path))
        if isinstance(val, str) and val:
            return val
    # Fallback: compute max 'until' from entries
    best: Optional[str] = None
    for e in data.get("entries", []) or []:
        if not isinstance(e, dict):
            continue
        u = e.get("until")
        if isinstance(u, str) and u:
            if best is None or u > best:
                best = u
    return best


def set_last_sync(state_path: str, project_path: str, until: str) -> None:
    """Persist the last sync upper bound for the given project path."""
    path = _expand(state_path)
    data = _load(path)
    if not isinstance(data.get("last_sync"), dict):
        data["last_sync"] = {}
    data["last_sync"][str(project_path)] = str(until)
    _save(path, data)
