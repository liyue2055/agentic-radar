#!/usr/bin/env python3
"""Generate a visual for the digest or the reflection.

    python3 radar/poster.py digest 2026-10-05    # infographic poster
    python3 radar/poster.py reflect 2026-10-05   # editorial illustration

Digest posters are deterministic infographics: a text model extracts
structured story data from the digest markdown, an HTML template renders
it in the Agentic Radar editorial style, and headless Chromium screenshots
it to site/<day>-poster.png (1536x1024 @2x). No image model involved, so
every word renders perfectly.

Reflection visuals still use the image model (muse-image-1.0, ~$0.01).
"""
from __future__ import annotations

import base64
import html as htmlmod
import json
import os
import re
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.expanduser("~/workspace/skills/meta-model-api/bin")
SHOT = os.path.join(ROOT, "radar", "shot", "shot.js")

ACCENTS = {
    "teal":   {"main": "#0d7a79", "soft": "#d8edeb", "line": "#0d7a79"},
    "blue":   {"main": "#1c5fd6", "soft": "#dde8fa", "line": "#1c5fd6"},
    "orange": {"main": "#dd6f0e", "soft": "#fbe8d3", "line": "#dd6f0e"},
}
ACCENT_ORDER = ["teal", "blue", "orange"]


def api(payload: dict) -> dict:
    with open("/tmp/radar_poster.json", "w") as fh:
        json.dump(payload, fh)
    r = subprocess.run(
        [f"{BIN}/model-api-call", "POST", "/chat/completions", "@/tmp/radar_poster.json"],
        capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise SystemExit(f"poster text call failed: {r.stderr.strip()}")
    return json.loads(r.stdout)


EXTRACT_BRIEF = """You are laying out a news infographic poster from today's AI-agent news digest.
Read the digest and output ONLY valid JSON (no markdown fences, no commentary) with this shape:

{
  "date": "6 OCTOBER 2026",
  "tagline": "<=48 chars: the day's single arc, e.g. 'AI moves from chat to persistent work'>",
  "themes": [
    {"title": "<=22 chars, sentence case>", "items": ["<=14 chars", "<=14 chars", "<=14 chars>"], "icon": "cloud|building|layers"},
    {"title": "<=22 chars, sentence case>", "items": ["...", "..."], "icon": "cloud|building|layers"},
    {"title": "<=22 chars, sentence case>", "items": ["...", "..."], "icon": "cloud|building|layers"}
  ],
  "constraints": ["<=18 chars", "<=18 chars", "<=18 chars"],
  "stories": [
    {"org": "<=10 chars, e.g. OPENAI>",
     "category": "<=20 chars, e.g. ALWAYS-ON WORKERS>",
     "lines": ["<=120 chars factual line 1", "<=120 chars factual line 2"],
     "takeaway": "<=68 chars punchy implication>"}
  ]
}

Rules:
- Exactly 6 stories, the day's most substantive, in digest order. Merge related bullets (e.g. Codex items) into one story with 2 lines.
- Strip [id] refs and [bullish]/[bearish] tags; never mention them.
- lines[]: plain facts from "What happened", each starting with the org name or a present-tense verb (never a bare past-tense verb like "Unveiled" alone).
- takeaway: the sharp implication from "Why it matters"/"Where this points".
- themes: 3 buckets grouping the 6 stories (title + the org/product keywords inside).
- constraints: 3 tension words/phrases from the bearish points and risks.
- Proofread every string for typos. Keep every string within its char limit. Plain text only, no markdown."""


def fmt_day(day: str) -> str:
    """2026-10-05 -> '5 OCTOBER 2026' (deterministic header date)."""
    d = datetime.strptime(day, "%Y-%m-%d")
    return f"{d.day} {d.strftime('%B').upper()} {d.year}"


def extract_poster_data(markdown: str) -> dict:
    data = api({
        "model": "muse-spark-1.3",
        "reasoning_effort": "minimal",
        "max_tokens": 2200,
        "messages": [{"role": "user",
                      "content": f"{EXTRACT_BRIEF}\n\nDIGEST:\n{markdown[:6000]}"}],
    })
    content = (data["choices"][0]["message"].get("content") or "").strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        print("poster JSON parse failed, retrying once...")
        data = api({
            "model": "muse-spark-1.3",
            "reasoning_effort": "minimal",
            "max_tokens": 2200,
            "messages": [{"role": "user",
                          "content": f"{EXTRACT_BRIEF}\n\nDIGEST:\n{markdown[:6000]}"}],
        })
        content = (data["choices"][0]["message"].get("content") or "").strip()
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content).strip()
        return json.loads(content)  # raises -> caller falls back


ICONS = {
    "cloud": '<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8"><path d="M17.5 19a4.5 4.5 0 0 0 .4-8.98A6 6 0 0 0 6.2 8.6 4.8 4.8 0 0 0 7 18.2h10.5z"/><rect x="9" y="13" width="6" height="4" rx="1" fill="{c}" stroke="none"/></svg>',
    "building": '<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8"><rect x="5" y="3" width="10" height="18"/><rect x="15" y="9" width="5" height="12"/><path d="M8 7h1M8 11h1M8 15h1M11 7h1M11 11h1M11 15h1"/></svg>',
    "layers": '<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8"><path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/></svg>',
}


def esc(s: str) -> str:
    return htmlmod.escape(str(s), quote=False)


def render_html(d: dict, day: str) -> str:
    themes_html = []
    for i, t in enumerate(d["themes"][:3]):
        a = ACCENTS[ACCENT_ORDER[i % 3]]
        icon = ICONS.get(t.get("icon", "layers"), ICONS["layers"]).format(c=a["main"])
        items = " &bull; ".join(esc(x) for x in t["items"][:4])
        themes_html.append(f"""
        <div class="theme" style="background:{a['soft']}">
          <div class="ticon">{icon}</div>
          <div><div class="ttitle">{esc(t['title'])}</div>
          <div class="titems">{items}</div></div>
        </div>""")

    cards_html = []
    for i, s in enumerate(d["stories"][:6]):
        a = ACCENTS[ACCENT_ORDER[i % 3]]
        initial = esc((s.get("org") or "?")[:2].upper())
        lines = "".join(f"<p>{esc(x)}</p>" for x in s["lines"][:2])
        cards_html.append(f"""
        <div class="card" style="border-color:{a['soft']}">
          <div class="chead">
            <div class="mono" style="background:{a['soft']};color:{a['main']}">{initial}</div>
            <div class="kicker"><span class="org">{esc(s['org'])}</span>
              <span class="cat" style="color:{a['main']}"> / {esc(s['category'])}</span></div>
          </div>
          <div class="cbody">{lines}</div>
          <div class="take" style="color:{a['main']}">{esc(s['takeaway'])}</div>
        </div>""")

    constraints = " &nbsp;&bull;&nbsp; ".join(esc(c) for c in d["constraints"][:3])

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1536px; height:1024px; background:#faf8f1;
  font-family:'Noto Sans',sans-serif; color:#191919; padding:34px 48px 26px; }}
.header {{ display:flex; align-items:center; white-space:nowrap; }}
.brand {{ font-size:54px; font-weight:900; letter-spacing:-1.5px; flex:none; }}
.sep {{ color:#9a9a9a; font-size:28px; margin:0 18px; font-weight:300; flex:none; }}
.date {{ font-size:29px; font-weight:800; color:#1c5fd6; flex:none; }}
.tagline {{ font-size:25px; font-weight:600; overflow:hidden; text-overflow:ellipsis; }}
.themes {{ display:flex; gap:40px; margin-top:20px; }}
.theme {{ flex:1; border-radius:14px; padding:18px 22px; display:flex;
  gap:16px; align-items:center; }}
.ttitle {{ font-size:26px; font-weight:800; }}
.titems {{ font-size:21px; color:#3c3c3c; margin-top:2px; }}
.mid {{ position:relative; height:104px; }}
.mid svg.wires {{ position:absolute; inset:0; }}
.pill {{ position:absolute; left:50%; top:50%; transform:translate(-50%,-50%);
  background:#0a2540; color:#fff; border-radius:999px; padding:14px 40px;
  font-size:26px; font-weight:800; letter-spacing:3px; white-space:nowrap; }}
.constraints {{ background:#dfe4ef; border-radius:10px; text-align:center;
  padding:10px; font-size:22px; font-weight:600; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:18px; margin-top:16px; }}
.card {{ background:#fff; border:2px solid #eee; border-radius:14px;
  padding:16px 18px; height:248px; overflow:hidden; }}
.chead {{ display:flex; gap:12px; align-items:center; }}
.mono {{ width:46px; height:46px; border-radius:11px; font-weight:900;
  font-size:22px; display:flex; align-items:center; justify-content:center;
  flex:none; }}
.kicker {{ font-size:18.5px; font-weight:800; line-height:1.25; }}
.kicker .org {{ color:#141414; }}
.cbody {{ margin-top:8px; }}
.cbody p {{ font-size:17.5px; line-height:1.42; color:#2e2e2e; margin-bottom:6px; }}
.take {{ font-size:17.5px; font-weight:800; margin-top:6px; line-height:1.35; }}
.footer {{ display:flex; justify-content:space-between; margin-top:14px;
  font-size:17px; color:#777; }}
</style></head><body>
<div class="header"><span class="brand">AGENTIC RADAR</span><span class="sep">|</span><span class="date">{esc(d['date'])}</span><span class="sep">|</span><span class="tagline">{esc(d['tagline'])}</span></div>
<div class="themes">{''.join(themes_html)}</div>
<div class="mid">
<svg class="wires" viewBox="0 0 1440 104" width="1440" height="104">
<path d="M224,6 C224,62 470,88 505,94" stroke="#0d7a79" stroke-width="4" fill="none"/>
<path d="M720,6 C720,52 720,70 720,82" stroke="#1c5fd6" stroke-width="4" fill="none"/>
<path d="M1216,6 C1216,62 970,88 935,94" stroke="#dd6f0e" stroke-width="4" fill="none"/>
<circle cx="224" cy="6" r="8" fill="#0d7a79"/><circle cx="720" cy="6" r="8" fill="#1c5fd6"/><circle cx="1216" cy="6" r="8" fill="#dd6f0e"/>
<circle cx="505" cy="94" r="8" fill="#0d7a79"/><circle cx="720" cy="82" r="8" fill="#1c5fd6"/><circle cx="935" cy="94" r="8" fill="#dd6f0e"/>
</svg>
<div class="pill">&#129302; AGENTS THAT DO WORK</div>
</div>
<div class="constraints"><b>Constraints:</b> {constraints}</div>
<div class="grid">{''.join(cards_html)}</div>
<div class="footer"><span>Source: Agentic Radar &bull; {esc(day)} digest</span><span>Summary of the page&rsquo;s reporting</span></div>
</body></html>"""


def screenshot(html_path: str, out_path: str) -> None:
    r = subprocess.run(
        ["node", SHOT, html_path, out_path, "1536", "1024"],
        capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not os.path.exists(out_path):
        raise SystemExit(f"screenshot failed: {r.stderr.strip()[-500:]}")


def legacy_image_poster(markdown: str, out: str) -> None:
    """Old artistic image-model path, kept as fallback for digest."""
    data = api({
        "model": "muse-spark-1.3",
        "reasoning_effort": "minimal",
        "max_tokens": 600,
        "messages": [{"role": "user", "content":
            "Write a single-paragraph image prompt for an editorial poster / "
            "infographic that captures the single biggest story below. Bold "
            "minimalist style, symbolic imagery, almost no text in the image "
            f"(a short headline at most).\n\nSOURCE:\n{markdown[:4000]}"}],
    })
    prompt = (data["choices"][0]["message"].get("content") or "").strip()
    sys.path.insert(0, BIN)
    from _client import post  # noqa: E402
    img = post("/images/generations",
               {"model": "muse-image-1.0", "prompt": prompt, "size": "1024x1024"})
    with open(out, "wb") as fh:
        fh.write(base64.b64decode(img["data"][0]["b64_json"]))


def make_digest_poster(day: str) -> str:
    src = os.path.join(ROOT, "digests", f"{day}.md")
    markdown = open(src).read()
    out = os.path.join(ROOT, "site", f"{day}-poster.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        print("extracting poster data...")
        pdata = extract_poster_data(markdown)
        pdata["date"] = fmt_day(day)  # pin date to the digest day, not the LLM's guess
        html_path = f"/tmp/radar_poster_{day}.html"
        with open(html_path, "w") as fh:
            fh.write(render_html(pdata, day))
        print("rendering infographic...")
        screenshot(html_path, out)
    except Exception as e:
        print(f"infographic path failed ({e}); falling back to image model...")
        legacy_image_poster(markdown, out)
    print(f"saved {out} ({os.path.getsize(out)//1024} KB)")
    return out


def make_reflect_visual(day: str) -> str:
    src = os.path.join(ROOT, "reflections", f"{day}.md")
    markdown = open(src).read()
    out = os.path.join(ROOT, "site", f"{day}-reflect.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    data = api({
        "model": "muse-spark-1.3",
        "reasoning_effort": "minimal",
        "max_tokens": 600,
        "messages": [{"role": "user", "content":
            "Write a single-paragraph image prompt for an editorial "
            "illustration about a newsroom editor reviewing the day's work "
            "with a red pen \u2014 learning from mistakes, sharper tomorrow. "
            "Symbolic, minimal, almost no text in the image."
            f"\n\nSOURCE:\n{markdown[:4000]}"}],
    })
    prompt = (data["choices"][0]["message"].get("content") or "").strip()
    sys.path.insert(0, BIN)
    from _client import post  # noqa: E402
    img = post("/images/generations",
               {"model": "muse-image-1.0", "prompt": prompt, "size": "1024x1024"})
    with open(out, "wb") as fh:
        fh.write(base64.b64decode(img["data"][0]["b64_json"]))
    print(f"saved {out} ({os.path.getsize(out)//1024} KB)")
    return out


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ("digest", "reflect"):
        print("usage: poster.py <digest|reflect> YYYY-MM-DD", file=sys.stderr)
        sys.exit(2)
    kind, day = sys.argv[1], sys.argv[2]
    if kind == "digest":
        src = os.path.join(ROOT, "digests", f"{day}.md")
        if not os.path.exists(src):
            raise SystemExit(f"missing {src}; run the digest first")
        make_digest_poster(day)
    else:
        src = os.path.join(ROOT, "reflections", f"{day}.md")
        if not os.path.exists(src):
            raise SystemExit(f"missing {src}; run the reflection first")
        make_reflect_visual(day)


if __name__ == "__main__":
    main()
