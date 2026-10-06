#!/usr/bin/env python3
"""Post the digest or reflection to Notion.

    python3 radar/notify.py digest 2026-10-05
    python3 radar/notify.py reflect 2026-10-05

Creates a private draft page (Notion 'draft' creation_mode) titled
"Agentic Radar — <day>" / "Agentic Radar reflection — <day>".
Set RADAR_NOTION_PARENT to a page ID to file them under a parent instead.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

PARENT = os.environ.get("RADAR_NOTION_PARENT", "")
SITE_URL = os.environ.get("RADAR_SITE_URL",
                          "https://feedos.si")


def create_page(title: str, markdown: str) -> str:
    page: dict = {"properties": {"title": title}, "content": markdown}
    if PARENT:
        page["parent"] = {"page_id": PARENT}
        body = {"pages": [page]}
    else:
        body = {"pages": [page], "creation_mode": "draft"}
    with open("/tmp/radar_notion.json", "w") as fh:
        json.dump(body, fh)
    r = subprocess.run(
        ["notion-cli", "call-tool", "--name", "notion-create-pages",
         "--arguments-json", open("/tmp/radar_notion.json").read()],
        capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise SystemExit(f"notion post failed: {r.stderr.strip()}")
    return r.stdout.strip()


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ("digest", "reflect"):
        print("usage: notify.py <digest|reflect> YYYY-MM-DD", file=sys.stderr)
        sys.exit(2)
    kind, day = sys.argv[1], sys.argv[2]
    if kind == "digest":
        md = db.get_digest(day)
        if not md:
            raise SystemExit(f"no digest for {day}")
        title = f"Agentic Radar — {day}"
        img = f"{SITE_URL}/{day}-poster.png"
        body = f"# {title}\n\n![Day poster]({img})\n\n{md}"
    else:
        conn = db.connect()
        row = conn.execute(
            "SELECT markdown FROM reflections WHERE day=? ORDER BY id DESC LIMIT 1",
            (day,)).fetchone()
        conn.close()
        if not row:
            raise SystemExit(f"no reflection for {day}")
        title = f"Agentic Radar reflection — {day}"
        img = f"{SITE_URL}/{day}-reflect.png"
        body = f"# {title}\n\n![Reflection visual]({img})\n\n{row[0]}"
    out = create_page(title, body)
    print(out[:500])


if __name__ == "__main__":
    main()
