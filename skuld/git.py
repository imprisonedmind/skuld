import re
import subprocess
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Commit:
    sha: str
    date: str  # ISO string
    subject: str


def extract_issue_keys(text: str, pattern: str) -> List[str]:
    try:
        rx = re.compile(pattern)
    except re.error:
        rx = re.compile(r"[A-Z][A-Z0-9]+-\d+")
    return rx.findall(text or "")


def get_commits(repo: str, since_iso: str, until_iso: str) -> List[Commit]:
    fmt = "%H\x1f%ad\x1f%s\x1e"
    cmd = [
        "git",
        "-C",
        repo,
        "log",
        f"--since={since_iso}",
        f"--until={until_iso}",
        "--date=iso-strict",
        f"--pretty=format:{fmt}",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if out.returncode != 0:
        return []
    records = out.stdout.strip("\n\x1e").split("\x1e") if out.stdout else []
    commits: List[Commit] = []
    for rec in records:
        if not rec:
            continue
        parts = rec.split("\x1f")
        if len(parts) != 3:
            continue
        sha, date, subject = parts
        commits.append(Commit(sha=sha, date=date, subject=subject))
    return commits


def group_commits_by_issue(commits: List[Commit], pattern: str) -> Dict[str, List[Commit]]:
    groups: Dict[str, List[Commit]] = {}
    for c in commits:
        keys = extract_issue_keys(c.subject, pattern)
        if not keys:
            continue
        for k in keys:
            groups.setdefault(k, []).append(c)
    return groups

