"""SQLite log of fire extinguishers and their monthly inspections."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

SCHEMA = """
CREATE TABLE IF NOT EXISTS extinguisher (
    tag TEXT PRIMARY KEY,
    building TEXT NOT NULL,
    location TEXT NOT NULL,
    kind TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inspection (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag TEXT NOT NULL REFERENCES extinguisher(tag),
    inspected_on TEXT NOT NULL,
    passed INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
"""

# A monthly inspection is overdue after this many days since the last one.
INTERVAL_DAYS = 31


class LogError(ValueError):
    """Raised for unknown tags, bad dates or duplicate tags."""


@dataclass(frozen=True)
class Status:
    """Inspection state of one extinguisher on a given day."""

    tag: str
    building: str
    location: str
    last_inspected: date | None
    last_passed: bool | None
    days_since: int | None
    state: str  # ok, overdue, never, failed


def connect(path: str = ":memory:") -> sqlite3.Connection:
    """Open the database and make sure the tables exist."""
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def parse_date(text: str) -> date:
    """Parse YYYY-MM-DD or raise LogError."""
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise LogError(f"bad date '{text}', use YYYY-MM-DD") from exc


def add_extinguisher(conn: sqlite3.Connection, tag: str, building: str, location: str, kind: str) -> None:
    """Register an extinguisher. Tags must be unique."""
    try:
        with conn:
            conn.execute("INSERT INTO extinguisher VALUES (?,?,?,?)", (tag, building, location, kind))
    except sqlite3.IntegrityError as exc:
        raise LogError(f"tag {tag} already exists") from exc


def record_inspection(conn: sqlite3.Connection, tag: str, when: str, passed: bool, note: str = "") -> None:
    """Record one inspection for a registered tag."""
    day = parse_date(when)
    if conn.execute("SELECT 1 FROM extinguisher WHERE tag=?", (tag,)).fetchone() is None:
        raise LogError(f"unknown tag {tag}")
    with conn:
        conn.execute("INSERT INTO inspection (tag, inspected_on, passed, note) VALUES (?,?,?,?)",
                     (tag, day.isoformat(), int(passed), note))


def statuses(conn: sqlite3.Connection, today: date) -> list[Status]:
    """Return the status of every extinguisher as of today, worst first."""
    result: list[Status] = []
    for tag, building, location in conn.execute(
            "SELECT tag, building, location FROM extinguisher ORDER BY tag").fetchall():
        row = conn.execute(
            "SELECT inspected_on, passed FROM inspection WHERE tag=? "
            "ORDER BY inspected_on DESC, id DESC LIMIT 1", (tag,)).fetchone()
        if row is None:
            result.append(Status(tag, building, location, None, None, None, "never"))
            continue
        last = date.fromisoformat(row[0])
        days = (today - last).days
        if not row[1]:
            state = "failed"
        elif days > INTERVAL_DAYS:
            state = "overdue"
        else:
            state = "ok"
        result.append(Status(tag, building, location, last, bool(row[1]), days, state))
    order = {"failed": 0, "never": 1, "overdue": 2, "ok": 3}
    return sorted(result, key=lambda s: (order[s.state], s.tag))


def format_report(items: list[Status]) -> str:
    """Plain text table of statuses."""
    lines = [f"{'Tag':<8}{'Building':<12}{'Location':<22}{'Last':<12}{'Days':>5}  State"]
    for s in items:
        last = s.last_inspected.isoformat() if s.last_inspected else "-"
        days = str(s.days_since) if s.days_since is not None else "-"
        lines.append(f"{s.tag:<8}{s.building:<12}{s.location:<22}{last:<12}{days:>5}  {s.state.upper()}")
    return "\n".join(lines)
