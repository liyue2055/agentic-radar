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
import validate

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

ONE ITEM PER BULLET — hard rule:
- Each What-happened bullet covers ONE item id only. The only exception
  is a direct follow-up: a second id may share a bullet only when it is a
  direct follow-up to the first item (same story / event sequence), for a
  maximum of TWO ids per bullet. Three-way (or larger) merges are banned —
  split distinct stories into separate bullets, even if they share a beat
  or theme.
- Never mix claim-type tags on one line: a bullet must not carry both
  [announced] and [analyst take]. If two items have different claim types,
  they are not a direct follow-up pair — give each its own bullet with its
  single claim-type tag.

DATING / SOURCE TAGS — hard rule:
- Any story whose item has no release date gets a [no date] tag on its line.
- Any story resting on a single source gets a [single source] tag on its
  line. Count sources by INDEPENDENT OUTLET, not by document: a vendor
  announcement plus that vendor's own red-team report, telemetry, or blog
  counts as ONE source (vendor telemetry quoting the vendor is not
  corroboration). Two genuinely independent outlets — vendor announcement
  plus third-party reporting, or vendor plus a different lab's public work
  — remove the tag. These tags must propagate from raw into What happened —
  never bury them elsewhere.

SOURCE FIDELITY — hard rules:
- If an item's text is truncated (a number, name, or figure cut off), do NOT
  reconstruct it. Report it as truncated/uncertain, e.g. "[amount unclear in
  source]". Never rename a role, company, or cohort beyond what the source says.
- Connections require shared mechanism or causal evidence, not theme rhyme:
  do not claim one lab's event "continues", "explains", or "feeds" another
  event unless the sources show the same underlying mechanism (shared
  product, benchmark, exploit, policy, or supply chain) or direct causal
  dependence. Same vendor alone is NOT enough — same-actor-only links are
  banned. Thematic resemblance is noted as rhyme, never causation.

PRIMARY BEATS SINGLE — hard rule:
- A primary source IS confirmation, even when it is the only source:
  an official changelog (e.g. github.blog/changelog, a vendor changelog),
  deprecation / shutdown notice, release notes, or official product post
  counts as confirmed on its own. Never Reject such an item as "needs
  vendor confirmation" or "thin sourcing", and never treat its own
  changelog as lacking the vendor's confirmation — it is that confirmation.
  Model removals / deprecations / shutdowns from a primary source are
  high-severity (they break builds): give them a What-happened line and,
  when the impact is broad, treat them as a lead / biggest story.
- NON-PRIMARY REMOVAL / MODEL-ID GATE — hard rule: the primary-source
  exception above applies ONLY when the item's own source is the official
  changelog / docs / deprecation notice itself (e.g. its URL is the
  github.blog/changelog or vendor notice). A secondary report, timeline
  note, or analyst/social summary ABOUT a removal, deprecation, or future
  model — however confident its tone — is NOT primary, and neither are
  unreleased / unverified model IDs or dates it names. If no official
  changelog/docs backs a removal / deprecation / model-ID claim, cap it
  at Missed / watch: never lead with it, never make it a biggest story in
  Why it matters, and do not state its model IDs or dates as confirmed
  fact (tag it [single source] / [unverified] instead).
- The converse also holds: a vendor benchmark, launch brief, or
  availability claim resting only on that vendor's own reporting is NOT
  confirmed by being the vendor's own post. Demote such items: they may
  appear in What happened flagged [single source] / [unverified], but do
  not make them a lead or one of the biggest stories in Why it matters
  until a second independent source corroborates them — otherwise move
  them to Missed / watch pending that second source.
- PRIMARY ARTIFACT GATE — hard rule (2026-10-20 reflection):
  Demote ALL single-source vendor/lab claims to Missed / watch unless
  the item links to a primary artifact: an official changelog/release
  notes, a public repo (with license/weights where "open-sourced" is
  claimed), a demo video, or a second independent outlet. No artifact,
  no lead: such items must NOT appear as a What-happened lead nor in
  Why it matters / Where this points as firm fact. Apply this bar
  evenly — do not reject one vendor claim for lack of corroboration
  while accepting another lab's swarm/benchmark numbers on the same
  evidence level. Never word a release as "open-sourced" unless the
  item itself cites a repo/license/weights link.
- SYNTHESIS GATE — hard rule (2026-10-24 reflection):
  Block synthesis when inputs are watch / single-source: do NOT build
  any Why it matters thesis, Connections claim, or Where this points
  prediction from an item that is Watch-listed, tagged [single source]
  or [unverified], or lacks a primary URL / commit / docs link. Such
  items stay in What happened (flagged) or Missed / watch only, until
  a primary artifact or a second independent source arrives. Lead
  Why it matters / Where this points only with verified items that
  carry a primary artifact or independent corroboration.
- CVE / MODEL-ID / COUNT CLAIM GATE — hard rule (2026-10-22 reflection):
  Require a primary artifact link for any CVE, model-ID, or count claim
  before promotion — no primary, no headline, stays in Watch. Specifically:
  a CVE ID needs an NVD / vendor-advisory entry, a specific (especially
  unreleased) model ID needs an official changelog / model card / docs
  page, and a quantitative count claim (e.g. "10 projects", "70+
  platforms", "1M skills", "10M setups") needs a foundation repo /
  registry / marketplace listing or other primary registry record —
  a single vendor/lab post reporting its own CVE, model ID, or count
  is NOT that artifact. If no such primary artifact is linked in the
  item, cap it at Missed / watch as
  "Watch [id] — need primary artifact: <one-line reason>", never as a
  What-happened headline and never as firm fact in Why it matters /
  Where this points (tag any retained mention [single source] /
  [unverified]).
- VERSIONED RELEASE WATCH GATE — hard rule (2026-10-21 reflection):
  Replace binary Reject with "Watch - need primary URL" for any
  versioned release claim (an item naming a specific version, e.g.
  Claude Code 2.1.302 or Codex CLI 0.163): do NOT Reject it for thin
  sourcing alone. List it in Missed / watch as
  "Watch [id] — need primary URL: <one-line reason>" and keep it
  there until a primary changelog/repo confirms or denies it.
  Preserve version ordering — a higher version is newer, never
  invert chronology (e.g. 2.1.302 > 2.1.299, so 2.1.302 is not
  older / superseded by 2.1.299).

CLAIM TYPING + FRESHNESS — hard rule:
- Freshness: any item whose release date is more than 7 days before today is
  context, not news — move it out of What happened into Connections or
  Missed / watch, labelled [older] with its date. Never present a stale
  item flat alongside same-day news.
- Type every launch/capability claim on its What-happened line as either
  [announced] (a vendor or primary outlet states it happened) or
  [analyst take] (an analyst or reporter infers/argues it). Never build a
  thesis on an [analyst take] item — treat it as opinion, not fact.
- Vendor numbers (benchmarks, scores, caps, pricing, traffic multiples)
  require a second independent source to print bare. Otherwise label them
  [unverified] inline, e.g. "72.4% [unverified]". One tag per line: use
  [single source] when the whole story lacks corroboration, [unverified]
  when only the vendor numbers do — never both.
- "Frontier" gate: do NOT call a model/product "frontier" unless its item
  cites benchmarks/evals or an independent second source corroborates the
  claim. Otherwise downgrade the wording to "vendor-claimed frontier" —
  never take a vendor's "frontier" framing at face value with no evals.

RECALL LOCK — hard rule:
- Every item id cited in any section (Why it matters, Connections, Where this
  points, Missed / watch) must also appear in What happened. No orphan
  citations: if a story is worth citing, give it one line in What happened.
  Sole exception: a "Rejected [id]" or "Watch [id] — need primary URL"
  line in Missed / watch (see RECALL GATE).

RECALL GATE — hard rule:
- Every raw item id must be accounted for somewhere in the digest: either
  it appears in What happened, or Missed / watch lists it as
  "Rejected [id] — <one-line reason>" (duplicate, stale, off-beat, thin
  sourcing, or low impact) — except versioned release claims, which
  Missed / watch lists as "Watch [id] — need primary URL: <reason>"
  under the VERSIONED RELEASE WATCH GATE instead of Rejecting them.
  No silent drops: an id that appears nowhere
  fails pre-publish validation and blocks the digest.

CITATION INTEGRITY — hard rule:
- Every id cited in Why it matters, Connections, or Where this points must
  itself contain the predicate claimed for it. Before citing an id for a
  claim (e.g. "persistent identity", "Gemini push", "model routing"), check
  that id's own What-happened line / raw item actually states that predicate
  — never borrow a predicate from a neighbouring item, a shared beat, or the
  vendor's wider narrative. If no cited id contains the claimed predicate,
  drop the claim or re-scope it to only the ids that do. A pairing of two
  ids must have the claimed mechanism present in BOTH ids, not just one.

SPEC FIDELITY — hard rule:
- Every attribute in Why it matters, Connections, or Where this points —
  context size, parameter/active counts, pricing, tier names, agent counts,
  traffic multiples, capability labels — must trace verbatim to that same
  item's raw title/summary. Never transfer a spec from a paired item to
  complete a rhyme (e.g. do not give a model a 1M context its own item
  never states), and never re-read a feature name (e.g. review tiers) as a
  different mechanism (e.g. multi-agent steering).
- Rejected items are quarantined: no predicate, framing, or vocabulary
  from a Rejected item may appear in Why it matters, Connections, or
  Where this points, even re-cited to a different id. If a prediction
  needs that predicate, it must be stated by a What-happened item itself
  or the prediction is dropped.
- REJECTED-ID BAN — hard rule (2026-10-23 reflection): a Rejected [id]
  must not be cited by id, nor drive a thesis, takeaway, or prediction,
  in Why it matters or Where this points. If a rejected item supports
  the thesis, do not keep it Rejected and use it anyway — promote it in
  Missed / watch to "Watch [id] — need primary URL: <reason>" (or
  "Watch [id] — need primary artifact: <reason>") and treat any retained
  mention only as flagged [single source] / [unverified] watch-level,
  never as firm fact.

COVERAGE LOCK — hard rule:
- Every item id in What happened must be used in Why it matters, Connections,
  or Where this points — or the digest ends with "## Orphaned" listing each
  unused id with one line explaining why it deserved no further analysis.
  No drop-and-run synthesis: if a story merited a What-happened line, it must
  either be analyzed or explicitly marked orphaned.

CONTRADICTION RULE — hard rule:
- Any launch/capability story must surface its paired risk item in the same
  digest section (alignment failures, cancelled models, delayed disclosures,
  distillation accusations, gated cyber releases), e.g. in Connections or
  Why it matters. Paired risks are cross-cutting, not cluster-local: an
  alignment failure or exploit-parity finding elsewhere counts. The phrase
  "no paired risk found" is banned — never claim absence when a risk item
  exists in another cluster. Never present a launch story as clean when a
  sibling risk story exists unreferenced.

NO SILENT OMITS — hard rule:
- High-severity items (security escapes, training halts, cancelled models,
  model removals / deprecations / shutdowns, exploit parity findings,
  broken interop defaults) must never be dropped
  silently from What happened. If one does not get a full line, it MUST
  appear under Missed / watch with a caveat explaining why it was
  deprioritized (thin sourcing, single outlet) rather than omitted.

## Why it matters
For the 2-3 biggest stories: what is actually driving this? (competitive
pressure, capability unlock, business model shift, regulation...)

## Connections
Link today's stories to EARLIER ones when they continue, contradict, or
rhyme with them. Format each as: [idA] <-> [idB] — relation — one-line note.
Only link when the connection is real.
CONTRADICTS LABEL — hard rule: use "contradicts" ONLY for a direct factual
conflict — the two items make incompatible claims about the same fact,
metric, date, or capability. Thematic tension, throughput-vs-auditability,
speed-vs-safety, or any other vibe contrast is NOT a contradiction: label
that "rhymes" / thematic, or drop the link. Ban "contradicts" for thematic
tension.

## Where this points
1-3 short predictions: what trend is accelerating, and is it good or bad
for builders? Mark each [bullish] or [bearish] with one line of reasoning.

## Missed / watch
Anything that looks thin or missing — beats with no news, stories that need
a second source. Plus one "Rejected [id] — <reason>" line for every raw
item not used in What happened (RECALL GATE), except versioned release
claims, which get a "Watch [id] — need primary URL: <reason>" line instead.

Keep the whole thing under 600 words. Markdown, no preamble."""


def build_digest(day: str) -> str:
    items = db.items_on(day)
    if not items:
        raise SystemExit(f"no items collected for {day}; run the collector first")
    item_lines = []
    for it in items:
        date_line = (f"\n    Published: {it['date_published']}"
                     if it.get("date_published") else "\n    Published: unknown")
        item_lines.append(
            f"[{it['id']}] ({it['beat']}) {it['title']}{date_line}\n"
            f"    {it['summary']}\n    {it['url']}")
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
    expected_ids = [str(it["id"]) for it in db.items_on(day)]
    problems = validate.check_digest(markdown, expected_ids=expected_ids)
    if problems:
        print(f"digest failed pre-publish validation for {day}:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(2)
    db.save_digest(day, markdown)
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "digests", f"{day}.md")
    with open(path, "w") as fh:
        fh.write(f"# Agentic Radar — {day}\n\n{markdown}\n")
    print(f"digest written: {path}")


if __name__ == "__main__":
    main()
