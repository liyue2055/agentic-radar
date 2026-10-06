"""Regenerate the static site from digests/*.md.

Output goes to site/: index.html (latest first) + one page per day.
Vercel serves site/ as the web root.
"""
from __future__ import annotations

import html
import os
import re
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIGESTS = os.path.join(ROOT, "digests")
SITE = os.path.join(ROOT, "site")

STYLE = """
:root{
  --paper:#f8f5ee; --ink:#1b1e26; --muted:#6f7280; --line:#e5e0d3;
  --card:#ffffff; --navy:#10243e; --blue:#1c5fd6; --teal:#0e7d7b;
  --orange:#c96a12; --green:#1e7f43; --red:#b3352b;
}
*{box-sizing:border-box}
body{font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  background:var(--paper);color:var(--ink);margin:0;line-height:1.65;font-size:16.5px}
a{color:var(--blue);text-decoration:none} a:hover{text-decoration:underline}
.wrap{max-width:860px;margin:0 auto;padding:0 22px}
.site-header{background:var(--navy);color:#fff;padding:18px 0;margin-bottom:34px}
.site-header .wrap{display:flex;align-items:center;justify-content:space-between}
.brand{font-weight:800;letter-spacing:2.5px;font-size:15px}
.brand small{color:#8fb4ff;letter-spacing:1px;font-weight:600;margin-left:10px}
.site-header nav a{color:#cdd9f5;margin-left:18px;font-size:14px}
.date-line{color:var(--muted);font-size:14.5px;margin:-4px 0 26px}
.poster{border-radius:14px;box-shadow:0 18px 50px rgba(16,36,62,.16);
  margin:0 0 34px;overflow:hidden}
.poster img{display:block;width:100%;height:auto}
.section{margin:0 0 34px}
.section>h2{font-size:13px;letter-spacing:2.2px;text-transform:uppercase;
  color:var(--muted);margin:0 0 14px;padding-bottom:8px;border-bottom:2px solid var(--line)}
.story{background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:13px 16px;margin:0 0 10px;display:flex;gap:12px;align-items:flex-start}
.story .ids{flex:none;display:flex;gap:5px;flex-wrap:wrap;padding-top:3px}
.id{background:#eef3fe;color:var(--blue);border-radius:6px;font-size:11.5px;
  font-weight:700;padding:2px 7px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;white-space:nowrap}
.why{border-left:4px solid var(--teal)}
.conn{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13.5px;
  color:#3d4a5c;background:var(--card);border:1px solid var(--line);
  border-radius:10px;padding:12px 16px;margin:0 0 10px}
.pill{display:inline-block;font-size:11.5px;font-weight:800;letter-spacing:.8px;
  border-radius:20px;padding:2px 10px;margin-right:8px;text-transform:uppercase}
.bullish{background:#e3f3e9;color:var(--green)}
.bearish{background:#fbe4e2;color:var(--red)}
.point{background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:13px 16px;margin:0 0 10px}
.watch{color:var(--muted);font-size:15px;margin:0 0 8px}
.navline{margin:38px 0 60px;display:flex;justify-content:space-between;font-size:14.5px}
footer.site-footer{border-top:1px solid var(--line);color:var(--muted);
  font-size:13.5px;padding:22px 0 40px;margin-top:20px}
/* index */
.hero{margin:6px 0 30px}
.hero h1{font-size:34px;margin:0 0 6px;letter-spacing:-.5px}
.hero p{color:var(--muted);font-size:17px;margin:0}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));
  gap:18px;margin-bottom:60px}
.day-card{background:var(--card);border:1px solid var(--line);border-radius:12px;
  overflow:hidden;display:block;color:inherit;transition:transform .15s,box-shadow .15s}
.day-card:hover{text-decoration:none;transform:translateY(-2px);
  box-shadow:0 12px 30px rgba(16,36,62,.12)}
.day-card img{width:100%;aspect-ratio:3/2;object-fit:cover;object-position:top;display:block}
.day-card .meta{padding:13px 16px}
.day-card .d{font-weight:700;font-size:15px}
.day-card .s{color:var(--muted);font-size:13px}
.day-card .go{color:var(--blue);font-size:13.5px;font-weight:600;margin-top:6px;display:block}
@media(max-width:600px){.hero h1{font-size:26px}}
"""

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Agentic Radar</title>
<meta name="description" content="A daily digest of agentic AI — what happened, why, and where it points.">
<style>{style}</style></head>
<body>
<header class="site-header"><div class="wrap">
<div class="brand">AGENTIC RADAR <small>DAILY DIGEST</small></div>
<nav><a href="index.html">All days</a><a href="https://github.com/liyue2055/agentic-radar">GitHub</a></nav>
</div></header>
<main class="wrap">{body}</main>
<footer class="site-footer"><div class="wrap">Agentic Radar · a daily digest of agentic AI · summary of the day's reporting</div></footer>
</body></html>"""


def fmt_date(day: str) -> str:
    return datetime.strptime(day, "%Y-%m-%d").strftime("%A, %B %-d, %Y")


def rich_line(line: str) -> str:
    """Escape, then badge [id] refs, pill [bullish]/[bearish], linkify URLs."""
    line = html.escape(line)
    line = re.sub(r"\[bullish\]", '<span class="pill bullish">bullish</span>', line)
    line = re.sub(r"\[bearish\]", '<span class="pill bearish">bearish</span>', line)
    line = re.sub(r"\[(\d+)\]", r'<span class="id">[\1]</span>', line)
    line = re.sub(r"(https?://\S+)", r'<a href="\1">\1</a>', line)
    return line


def md_to_html(md: str) -> str:
    out, section, in_section = [], None, False
    for line in md.split("\n"):
        if line.startswith("## "):
            if in_section:
                out.append("</div>")
            in_section = True
            section = line[3:].strip().lower()
            out.append(f'<div class="section"><h2>{html.escape(line[3:])}</h2>')
        elif line.startswith("# "):
            out.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif re.match(r"^(\d+\.|-|\*) ", line):
            body = re.sub(r"^(\d+\.|-|\*) ", "", line)
            if section == "what happened":
                ids = re.findall(r"\[(\d+)\]", body)
                badges = "".join(f'<span class="id">[{i}]</span>' for i in ids)
                text = re.sub(r"\[\d+\]\s*(<->\s*)?", "", body).strip()
                out.append(f'<div class="story"><div class="ids">{badges}</div>'
                           f"<div>{rich_line(text)}</div></div>")
            elif section == "why it matters":
                out.append(f'<div class="story why"><div>{rich_line(body)}</div></div>')
            elif section == "connections":
                out.append(f'<div class="conn">{rich_line(body)}</div>')
            elif section == "where this points":
                out.append(f'<div class="point">{rich_line(body)}</div>')
            elif section and section.startswith("missed"):
                out.append(f'<p class="watch">{rich_line(body)}</p>')
            else:
                out.append(f"<p>{rich_line(body)}</p>")
        elif line.strip() == "":
            out.append("")
        else:
            out.append(f"<p>{rich_line(line)}</p>")
    if in_section:
        out.append("</div>")
    return "\n".join(out)


def page(title: str, body: str) -> str:
    return PAGE.format(title=title, style=STYLE, body=body)


def main() -> None:
    os.makedirs(SITE, exist_ok=True)
    days = sorted((f[:-3] for f in os.listdir(DIGESTS) if f.endswith(".md")),
                  reverse=True)
    taglines = {}
    for day in days:
        md = open(os.path.join(DIGESTS, f"{day}.md")).read()
        poster = f"{day}-poster.png"
        hero = (f'<figure class="poster"><img src="{poster}" alt="infographic poster for {day}"></figure>'
                if os.path.exists(os.path.join(SITE, poster)) else "")
        # tagline = first line of digest body after the h1
        lines = [l for l in md.split("\n") if l.strip() and not l.startswith("#")]
        taglines[day] = lines[0][:120] if lines else ""
        rlink = (f'<div class="navline"><a href="{day}-reflection.html">'
                 f"Editor's reflection →</a><a href=\"index.html\">← all days</a></div>"
                 if os.path.exists(os.path.join(ROOT, "reflections", f"{day}.md"))
                 else f'<div class="navline"><span></span><a href="index.html">← all days</a></div>')
        body = (f"<h1 style='font-size:28px;margin:0 0 4px'>{fmt_date(day)}</h1>"
                f'<p class="date-line">Daily digest</p>' + hero + md_to_html(md) + rlink)
        open(os.path.join(SITE, f"{day}.html"), "w").write(page(day, body))
    # reflection pages
    rdir = os.path.join(ROOT, "reflections")
    if os.path.isdir(rdir):
        for f in os.listdir(rdir):
            if not f.endswith(".md"):
                continue
            day = f[:-3]
            md = open(os.path.join(rdir, f)).read()
            rimg = f"{day}-reflect.png"
            hero = (f'<figure class="poster"><img src="{rimg}" alt="reflection visual for {day}"></figure>'
                    if os.path.exists(os.path.join(SITE, rimg)) else "")
            body = (f"<h1 style='font-size:28px;margin:0 0 4px'>Editor's reflection</h1>"
                    f'<p class="date-line">{fmt_date(day)}</p>' + hero + md_to_html(md) +
                    f'<div class="navline"><a href="{day}.html">← digest</a>'
                    f'<a href="index.html">all days</a></div>')
            open(os.path.join(SITE, f"{day}-reflection.html"), "w").write(
                page(f"Reflection {day}", body))
    cards = []
    for d in days:
        thumb = (f'<img src="{d}-poster.png" alt="">' if
                 os.path.exists(os.path.join(SITE, f"{d}-poster.png")) else "")
        cards.append(
            f'<a class="day-card" href="{d}.html">{thumb}'
            f'<div class="meta"><div class="d">{fmt_date(d)}</div>'
            f'<div class="s">Daily digest</div>'
            f'<span class="go">Read the digest →</span></div></a>')
    index = (f'<div class="hero"><h1>Agentic Radar</h1>'
             f"<p>A daily digest of agentic AI — what happened, why, and where it points.</p></div>"
             f'<div class="cards">{"".join(cards) or "No digests yet."}</div>')
    open(os.path.join(SITE, "index.html"), "w").write(page("Agentic Radar", index))
    print(f"site regenerated: {len(days)} day(s)")


if __name__ == "__main__":
    main()
