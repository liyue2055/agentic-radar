# Agentic Radar

**Live:** https://agentic-radar.vercel.app/

A daily digest of agentic AI — not just *what* happened, but *why* it happened,
what it connects to, and where the trend points.

## How it works

1. **Collect** (cron, daily ~7am ET): gather news across beats — Claude Code,
   Codex, Meta, Muse, Gemini, OpenAI, Anthropic, and open-source labs
   (Kimi, MiniMax, GLM). Raw items land in `data/radar.db`.
2. **Digest**: the analyst prompt reads today's items *plus related history*
   from the DB, then writes `digests/YYYY-MM-DD.md` with four sections:
   what happened, why it matters, connections across time (`[id] <-> [id]`),
   and where it points ([bullish]/[bearish] predictions).
3. **Poster** (`radar/poster.py`): renders a deterministic editorial infographic
   from the digest (text model extracts story data, HTML template + headless
   Chromium screenshot) into `site/<day>-poster.png` — no image model, so all
   text renders perfectly; the reflection job gets its own visual
   (`site/<day>-reflect.png`, image model ~$0.01). Both appear on the site and in
   the Notion posts.
4. **Publish**: `radar/site.py` regenerates the static `site/`; push to GitHub
   → Vercel auto-deploys. The digest also posts to Notion.
5. **Reflect** (cron, ~9am ET): the editor prompt critiques the digest —
   hits, misses, coverage gaps, one change for tomorrow. Saved to
   `reflections/` (with its own visual) and posted to Notion as the learning log.

## The point

The database is the memory. Every digest can reach back weeks or months
("this continues the story from <date>"), so the project compounds instead
of resetting each morning. The reflection loop is how the pipeline itself
gets smarter.

## Beats

`claude-code` · `codex` · `meta` · `muse` · `gemini` · `openai` · `anthropic` ·
`kimi` · `minimax` · `glm`

## Run locally

```bash
python3 radar/db.py            # (import-only; schema auto-creates)
python3 radar/digest.py 2026-10-05
python3 radar/poster.py digest 2026-10-05   # needs: cd radar/shot && npm install
python3 radar/site.py
python3 radar/reflect.py 2026-10-05
```

## Live

- https://agentic-radar.vercel.app/ (live now)
- https://feedos.si (custom domain, nameservers updated — propagating)
