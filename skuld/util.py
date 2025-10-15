def format_seconds(secs: float) -> str:
    total = int(round(secs))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    parts = []
    if h:
        parts.append(f"{h}h")
    if m or h:
        parts.append(f"{m}m")
    if s:
        parts.append(f"{s}s")
    return " ".join(parts) if parts else "0m"


def format_date(dtobj) -> str:
    # dd/mm/yy
    return dtobj.strftime("%d/%m/%y")


def format_time(dtobj) -> str:
    # 12-hour time with AM/PM (no leading zero hour)
    return dtobj.strftime("%-I:%M %p") if hasattr(dtobj, "strftime") else str(dtobj)
