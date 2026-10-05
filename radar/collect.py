#!/usr/bin/env python3
"""Collector CLI: store one news item per call.

The daily cron (an agent run) searches each beat with browser_search and
calls this for every story worth keeping:

    python3 radar/collect.py add 2026-10-05 openai "Title here" \\
        --url https://example.com/story --summary "one-line summary"

Beats are defined in radar/config.py.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
from config import BEATS


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add")
    add.add_argument("day")
    add.add_argument("beat", choices=sorted(BEATS))
    add.add_argument("title")
    add.add_argument("--url", default="")
    add.add_argument("--summary", default="")

    show = sub.add_parser("show")
    show.add_argument("day")

    args = p.parse_args()
    if args.cmd == "add":
        item_id = db.add_item(args.day, args.beat, args.title, args.url, args.summary)
        print(f"stored item {item_id}")
    elif args.cmd == "show":
        for it in db.items_on(args.day):
            print(f"[{it['id']}] ({it['beat']}) {it['title']}")


if __name__ == "__main__":
    main()
