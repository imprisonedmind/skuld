def format_seconds(secs: float) -> str:
    total = int(round(secs))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    parts = []
    if h:
        parts.append(f"{h}h")
    if m or (h and s):
        parts.append(f"{m}m")
    if s and not h:
        parts.append(f"{s}s")
    return " ".join(parts) if parts else "0m"

