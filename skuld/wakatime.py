import json
from pathlib import Path
from typing import Any, Dict


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

