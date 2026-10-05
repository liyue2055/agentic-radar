"""Regenerate the static site from digests/*.md.

Output goes to site/: index.html (latest first) + one page per day.
Vercel serves site/ as the web root.
"""
from __future__ import annotations

import html
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIGESTS = os.path.join(ROOT, "digests")
SITE = os.path.join(ROOT, "site")

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Agentic Radar</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;max-width:760px;margin:0 auto;padding:24px;line-height:1.6}}
h1{{font-size:1.5rem}} .day{{color:#888}} a{{color:#0a66c2}}
ul.days{{list-style:none;padding:0}} ul.days li{{margin:8px 0}}
pre{{white-space:pre-wrap}}
</style></head><body>{body}</body></html>"""


def md_to_html(md: str) -> str:
    out = []
    for line in md.split("\n"):
        if line.startswith("### "):
            out.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif re.match(r"^(\d+\.|-|\*) ", line):
            out.append(f"<p>{html.escape(line)}</p>")
        elif line.strip() == "":
            out.append("")
        else:
            # linkify [12] item refs and urls
            line = html.escape(line)
            line = re.sub(r"(https?://\S+)", r'<a href="\1">\1</a>', line)
            out.append(f"<p>{line}</p>")
    return "\n".join(out)


def main() -> None:
    os.makedirs(SITE, exist_ok=True)
    days = sorted((f[:-3] for f in os.listdir(DIGESTS) if f.endswith(".md")),
                  reverse=True)
    for day in days:
        md = open(os.path.join(DIGESTS, f"{day}.md")).read()
        body = md_to_html(md) + '<p><a href="index.html">← all days</a></p>'
        open(os.path.join(SITE, f"{day}.html"), "w").write(
            PAGE.format(title=day, body=body))
    lis = "".join(f'<li><a href="{d}.html">{d}</a></li>' for d in days) or \
        "<li>No digests yet.</li>"
    index = (f"<h1>Agentic Radar</h1>"
             f"<p class='day'>A daily digest of agentic AI — what happened, why, "
             f"and where it points.</p><ul class='days'>{lis}</ul>")
    open(os.path.join(SITE, "index.html"), "w").write(
        PAGE.format(title="Agentic Radar", body=index))
    print(f"site regenerated: {len(days)} day(s)")


if __name__ == "__main__":
    main()
