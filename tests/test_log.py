from datetime import date

import pytest

from fexlog.__main__ import load_csv, main
from fexlog.log import (LogError, add_extinguisher, connect, format_report,
                        parse_date, record_inspection, statuses)

TODAY = date(2026, 11, 19)


@pytest.fixture
def conn():
    c = connect()
    add_extinguisher(c, "FE-1", "A", "Lobby", "ABC")
    return c


def test_never_inspected(conn):
    assert statuses(conn, TODAY)[0].state == "never"


def test_recent_pass_is_ok(conn):
    record_inspection(conn, "FE-1", "2026-11-10", True)
    s = statuses(conn, TODAY)[0]
    assert s.state == "ok" and s.days_since == 9


def test_31_days_is_not_overdue_and_older_record_ignored(conn):
    record_inspection(conn, "FE-1", "2026-10-19", True)  # exactly 31 days
    assert statuses(conn, TODAY)[0].state == "ok"
    record_inspection(conn, "FE-1", "2026-10-18", True)  # older record does not change latest
    assert statuses(conn, TODAY)[0].state == "ok"


def test_overdue(conn):
    record_inspection(conn, "FE-1", "2026-10-01", True)
    assert statuses(conn, TODAY)[0].state == "overdue"


def test_failed_overrides_recent(conn):
    record_inspection(conn, "FE-1", "2026-11-18", False, "low pressure")
    assert statuses(conn, TODAY)[0].state == "failed"


def test_latest_inspection_wins(conn):
    record_inspection(conn, "FE-1", "2026-11-01", False)
    record_inspection(conn, "FE-1", "2026-11-12", True)
    assert statuses(conn, TODAY)[0].state == "ok"


def test_worst_first_ordering(conn):
    add_extinguisher(conn, "FE-2", "A", "Hall", "ABC")
    record_inspection(conn, "FE-1", "2026-11-12", True)
    record_inspection(conn, "FE-2", "2026-11-12", False)
    assert [s.tag for s in statuses(conn, TODAY)] == ["FE-2", "FE-1"]


def test_duplicate_tag_rejected(conn):
    with pytest.raises(LogError, match="already exists"):
        add_extinguisher(conn, "FE-1", "A", "x", "ABC")


def test_unknown_tag_rejected(conn):
    with pytest.raises(LogError, match="unknown tag"):
        record_inspection(conn, "FE-9", "2026-11-01", True)


def test_bad_date_rejected():
    with pytest.raises(LogError):
        parse_date("11/19/2026")


def test_report_text(conn):
    out = format_report(statuses(conn, TODAY))
    assert "FE-1" in out and "NEVER" in out


def test_load_csv_and_cli_report(tmp_path, capsys):
    db = str(tmp_path / "t.db")
    assert main(["--db", db, "load", "data/sample.csv"]) == 0
    assert main(["--db", db, "report", "--today", "2026-11-19", "--problems"]) == 0
    out = capsys.readouterr().out
    assert "FE-03" in out and "FAILED" in out and "FE-04" not in out


def test_cli_unknown_tag_returns_1(tmp_path, capsys):
    assert main(["--db", str(tmp_path / "t.db"), "inspect", "ZZ", "2026-11-01", "--pass"]) == 1
    assert "unknown tag" in capsys.readouterr().err
