"""Command line for the extinguisher log.

  python -m fexlog --db log.db add FE-01 "Building A" "Lobby" ABC
  python -m fexlog --db log.db inspect FE-01 2026-11-02 --pass
  python -m fexlog --db log.db report --today 2026-11-19
  python -m fexlog --db log.db load data/sample.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date

from .log import (LogError, add_extinguisher, connect, format_report, record_inspection,
                  statuses, parse_date)


def load_csv(conn, path: str) -> int:
    """Load a CSV (kind, tag, building, location, type, date, passed, note) of mixed rows."""
    count = 0
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["kind"] == "extinguisher":
                add_extinguisher(conn, row["tag"], row["building"], row["location"], row["type"])
            elif row["kind"] == "inspection":
                record_inspection(conn, row["tag"], row["date"], row["passed"].lower() == "yes", row["note"])
            else:
                raise LogError(f"unknown row kind '{row['kind']}'")
            count += 1
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fexlog", description="Fire extinguisher inspection log")
    parser.add_argument("--db", default="fexlog.db")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    for name in ("tag", "building", "location", "kind"):
        add.add_argument(name)
    insp = sub.add_parser("inspect")
    insp.add_argument("tag")
    insp.add_argument("date")
    insp.add_argument("--pass", dest="passed", action="store_true")
    insp.add_argument("--note", default="")
    rep = sub.add_parser("report")
    rep.add_argument("--today", help="YYYY-MM-DD, default is today")
    rep.add_argument("--problems", action="store_true", help="hide units that are ok")
    load = sub.add_parser("load")
    load.add_argument("csv_file")
    args = parser.parse_args(argv)
    conn = connect(args.db)
    try:
        if args.command == "add":
            add_extinguisher(conn, args.tag, args.building, args.location, args.kind)
            print(f"added {args.tag}")
        elif args.command == "inspect":
            record_inspection(conn, args.tag, args.date, args.passed, args.note)
            print(f"recorded {args.tag} {'pass' if args.passed else 'FAIL'}")
        elif args.command == "load":
            print(f"loaded {load_csv(conn, args.csv_file)} rows")
        else:
            today = parse_date(args.today) if args.today else date.today()
            items = statuses(conn, today)
            if args.problems:
                items = [s for s in items if s.state != "ok"]
            print(format_report(items))
    except (LogError, OSError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
