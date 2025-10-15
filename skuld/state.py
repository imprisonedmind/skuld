import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Any


def _expand(p: str) -> Path:
    return Path(os.path.expanduser(p)).resolve()


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"entries": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            return data
    except Exception:
        pass
    return {"entries": []}


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

