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
    # Use %aI (author date, strict ISO 8601 with timezone offset like +00:00)
    fmt = "%H\x1f%aI\x1f%s\x1e"
    cmd = [
        "git",
        "-C",
        repo,
        "log",
        f"--since={since_iso}",
        f"--until={until_iso}",
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


def get_commits_for_branches(repo: str, branches: List[str], since_iso: str, until_iso: str) -> List[Commit]:
    """Return commits reachable from any of the given local branches within the window.

    Runs one log per branch to tolerate missing refs. Dedupe by SHA.
    """
    if not branches:
        return []
    # Use %aI for strict ISO timestamps
    fmt = "%H\x1f%aI\x1f%s\x1e"
    seen: Dict[str, bool] = {}
    out_commits: List[Commit] = []
    # Use unique branches to avoid redundant work
    uniq = [b for i, b in enumerate(branches) if b and b not in branches[:i]]
    for br in uniq:
        cmd = [
            "git",
            "-C",
            repo,
            "log",
            br,
            f"--since={since_iso}",
            f"--until={until_iso}",
            f"--pretty=format:{fmt}",
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if out.returncode != 0 or not out.stdout:
            continue
        records = out.stdout.strip("\n\x1e").split("\x1e") if out.stdout else []
        for rec in records:
            if not rec:
                continue
            parts = rec.split("\x1f")
            if len(parts) != 3:
                continue
            sha, date, subject = parts
            if sha in seen:
                continue
            seen[sha] = True
            out_commits.append(Commit(sha=sha, date=date, subject=subject))
    return out_commits

def group_commits_by_issue(commits: List[Commit], pattern: str) -> Dict[str, List[Commit]]:
    groups: Dict[str, List[Commit]] = {}
    for c in commits:
        keys = extract_issue_keys(c.subject, pattern)
        if not keys:
            continue
        for k in keys:
            groups.setdefault(k, []).append(c)
    return groups
