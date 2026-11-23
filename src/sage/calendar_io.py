"""Safe, file-based iCalendar import/export helpers for SAGE."""
from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

from .core import SageStore


def _unescape_ical(value: str) -> str:
    return (value.replace("\\n", "\n").replace("\\N", "\n")
            .replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip())


def import_icalendar_proposals(
    store: SageStore, source: str | Path, project_id: int, limit: int = 100
) -> dict[str, int]:
    """Import dated VEVENTs as pending task proposals; never create tasks directly.

    Recurring events are skipped because this importer does not expand RRULEs.
    Repeated imports are idempotent through a stable source UID/hash.
    """
    if not 1 <= limit <= 500:
        raise ValueError("Calendar event import limit must be between 1 and 500.")
    if not any(project["id"] == project_id for project in store.list_projects()):
        raise ValueError(f"Project {project_id} does not exist.")
    path = Path(source).expanduser().resolve()
    if path.suffix.lower() != ".ics" or not path.is_file():
        raise ValueError("Calendar source must be an existing .ics file.")
    if path.stat().st_size > 2_000_000:
        raise ValueError("Calendar file exceeds the 2 MB import limit.")
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Calendar file must be valid UTF-8 text.") from error
    if "BEGIN:VCALENDAR" not in raw.upper() or "END:VCALENDAR" not in raw.upper():
        raise ValueError("File is not a complete iCalendar document.")
    physical = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines: list[str] = []
    for line in physical:
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    events: list[list[str]] = []
    current: list[str] | None = None
    for line in lines:
        upper = line.upper()
        if upper == "BEGIN:VEVENT":
            current = []
        elif upper == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
        elif current is not None:
            current.append(line)
    if len(events) > limit:
        raise ValueError(f"Calendar contains more than the {limit} event import limit.")

    created = skipped = duplicates = 0
    existing_sources = {
        proposal.get("source_uid") for proposal in store.list_task_proposals()
        if proposal.get("source_uid")
    }
    for event in events:
        fields: dict[str, str] = {}
        for line in event:
            if ":" not in line:
                continue
            left, value = line.split(":", 1)
            key = left.split(";", 1)[0].upper()
            if key in {"SUMMARY", "DTSTART", "UID", "RRULE", "STATUS"} and key not in fields:
                fields[key] = value
        summary = _unescape_ical(fields.get("SUMMARY", ""))
        start = fields.get("DTSTART", "")
        if not summary or len(summary) > 500 or not start or "RRULE" in fields or fields.get("STATUS", "").upper() == "CANCELLED":
            skipped += 1
            continue
        try:
            due = date.fromisoformat(start[:10]) if "-" in start[:10] else date(int(start[:4]), int(start[4:6]), int(start[6:8]))
        except (ValueError, TypeError):
            skipped += 1
            continue
        uid = fields.get("UID", "").strip()
        stable = f"{project_id}|{uid}" if uid else f"{project_id}|{summary}|{start}"
        source_uid = "ics:" + hashlib.sha256(stable.encode("utf-8")).hexdigest()
        if source_uid in existing_sources:
            duplicates += 1
            continue
        store.create_task_proposal(
            project_id, summary,
            f"Imported from {path.name}; review before adding to execution. [iCalendar:{source_uid}]",
            3, due.isoformat(), source_uid,
        )
        existing_sources.add(source_uid)
        created += 1
    return {"created": created, "duplicates": duplicates, "skipped": skipped}
