"""Generate the daily insight digest.

Reads today's collected items from the DB, pulls related history, and asks
the Meta Model API for a digest that goes beyond 'what happened':
why it happened, what it connects to, and where the trend points.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

BIN = os.path.expanduser("~/workspace/skills/meta-model-api/bin")

BEATS = ["claude-code", "codex", "meta", "muse", "gemini",
         "openai", "anthropic", "kimi", "minimax", "glm"]

PROMPT = """You are the analyst behind Agentic Radar, a daily digest of agentic AI.
Today is {day}. Below are today's collected news items, each with an id.

TODAY'S ITEMS:
{items}

Use the item ids when you reference a story. Your digest must have:

## What happened
3-7 bullets, one line each: the news, no fluff.

SOURCE FIDELITY — hard rules:
- If an item's text is truncated (a number, name, or figure cut off), do NOT
  reconstruct it. Report it as truncated/uncertain, e.g. "[amount unclear in
  source]". Never rename a role, company, or cohort beyond what the source says.
- Connections must be same-actor evidence, not theme rhyme: do not claim one
  lab's event "continues", "explains", or "feeds" another lab's event unless the
  sources share the actor. Thematic resemblance is noted as rhyme, never
  causation.

## Why it matters
For the 2-3 biggest stories: what is actually driving this? (competitive
pressure, capability unlock, business model shift, regulation...)

## Connections
Link today's stories to EARLIER ones when they continue, contradict, or
rhyme with them. Format each as: [idA] <-> [idB] — relation — one-line note.
Only link when the connection is real.

## Where this points
1-3 short predictions: what trend is accelerating, and is it good or bad
for builders? Mark each [bullish] or [bearish] with one line of reasoning.

## Missed / watch
Anything that looks thin or missing — beats with no news, stories that need
a second source.

Keep the whole thing under 600 words. Markdown, no preamble."""


def build_digest(day: str) -> str:
    items = db.items_on(day)
    if not items:
        raise SystemExit(f"no items collected for {day}; run the collector first")
    item_lines = []
    for it in items:
        item_lines.append(
            f"[{it['id']}] ({it['beat']}) {it['title']}\n    {it['summary']}\n    {it['url']}")
    payload = {
        "model": "muse-spark-1.3",
        "reasoning_effort": "medium",
        "messages": [{"role": "user", "content": PROMPT.format(
            day=day, items="\n\n".join(item_lines))}],
    }
    with open("/tmp/radar_digest.json", "w") as fh:
        json.dump(payload, fh)
    r = subprocess.run(
        [f"{BIN}/model-api-call", "POST", "/chat/completions", "@/tmp/radar_digest.json"],
        capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise SystemExit(f"digest generation failed: {r.stderr.strip()}")
    data = json.loads(r.stdout)
    return data["choices"][0]["message"]["content"]


def main() -> None:
    import datetime
    day = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
    markdown = build_digest(day)
    db.save_digest(day, markdown)
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "digests", f"{day}.md")
    with open(path, "w") as fh:
        fh.write(f"# Agentic Radar — {day}\n\n{markdown}\n")
    print(f"digest written: {path}")


if __name__ == "__main__":
    main()
