"""Reflection job: critique today's digest like an editor.

Reads the digest + the raw items behind it and asks:
- What did we miss or get wrong?
- Which connections were weak or forced?
- Which beats were thin — do we need better sources?
- One concrete improvement for tomorrow's run.

Saves to reflections/YYYY-MM-DD.md and the DB; the cron posts it to Notion
as the learning log.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

BIN = os.path.expanduser("~/workspace/skills/meta-model-api/bin")

PROMPT = """You are the editor reviewing today's Agentic Radar digest.

THE DIGEST:
{digest}

THE RAW ITEMS IT WAS BUILT FROM:
{items}

Write a candid reflection (under 300 words, markdown):

## Hits
What the digest got right — accurate framing, real connections.

## Misses
Stories misread, overclaimed, or missing. Connections that were forced.
Be specific and blunt.

## Coverage gaps
Beats or angles with thin sourcing. Suggest one better source or query
for tomorrow.

## One change for tomorrow
The single highest-leverage improvement to the pipeline or prompt.

No preamble, no flattery."""


def main() -> None:
    import datetime
    day = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
    digest = db.get_digest(day)
    if not digest:
        raise SystemExit(f"no digest for {day}; run the digest first")
    items = db.items_on(day)
    item_lines = [f"[{it['id']}] ({it['beat']}) {it['title']} — {it['summary']}"
                  for it in items]
    payload = {
        "model": "muse-spark-1.3",
        "reasoning_effort": "medium",
        "messages": [{"role": "user", "content": PROMPT.format(
            digest=digest, items="\n".join(item_lines))}],
    }
    with open("/tmp/radar_reflect.json", "w") as fh:
        json.dump(payload, fh)
    r = subprocess.run(
        [f"{BIN}/model-api-call", "POST", "/chat/completions", "@/tmp/radar_reflect.json"],
        capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise SystemExit(f"reflection failed: {r.stderr.strip()}")
    markdown = json.loads(r.stdout)["choices"][0]["message"]["content"]
    db.save_reflection(day, markdown)
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "reflections", f"{day}.md")
    with open(path, "w") as fh:
        fh.write(f"# Reflection — {day}\n\n{markdown}\n")
    print(f"reflection written: {path}")


if __name__ == "__main__":
    main()
