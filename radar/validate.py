"""Pre-publish validation for the daily digest.

Blocks publishing when the generated digest shows the failure modes flagged
by the nightly reflection:
  - too many [no date] tags (model didn't extract dates the raw items had)
  - internal editorial notes leaking into the published sections
  - citations in later sections with no matching line in What happened
    (orphan citations / recall-lock violations)
  - raw item ids that appear nowhere in the digest (recall-gate
    violations: silently dropped items must instead be listed as
    "Rejected [id] — reason" in Missed / watch, or, for versioned
    release claims, "Watch [id] — need primary URL: reason")

Used by digest.py before it saves anything; on failure it exits non-zero so
the cron fails loud instead of publishing a broken digest.
"""
from __future__ import annotations

import re

MAX_NO_DATE = 2

# Snippets that are model-internal drafting artifacts, never publishable.
LEAK_PATTERNS = [
    re.compile(r, re.IGNORECASE)
    for r in [
        r"rhyme not shown",
        r"omitted; instead",
        r"\bINTERNAL\b",
        r"\bTODO\b",
        r"\bFIXME\b",
        r"note to (self|editor)",
        r"draft(ing)? (note|comment)",
        r"\{editor[-\s]?only\}",
    ]
]

ID_RE = re.compile(r"\[(\d{2,4})\]")
NO_DATE_RE = re.compile(r"\[no date\]", re.IGNORECASE)
NO_PRIMARY_RE = re.compile(r"\[no primary link\]", re.IGNORECASE)

# Hosts that ARE a primary source when they are an item's own URL
# (2026-11-08 reflection): an official changelog / docs / engineering
# blog / repo on one of these is the primary artifact itself, so a
# line citing that item must never be tagged [no primary link].
PRIMARY_HOSTS = (
    "github.blog", "github.com", "huggingface.co",
    "developers.openai.com", "openai.com", "platform.openai.com",
    "anthropic.com", "claude.com", "support.claude.com",
    "docs.cloud.google.com", "cloud.google.com", "ai.google.dev",
    "developers.google.com", "blog.google", "research.google.com",
    "mistral.ai", "ai.meta.com", "engineering.fb.com",
    "learn.microsoft.com", "azure.microsoft.com", "microsoft.com",
)

# Phrases in a raw summary that cite a primary source even when the
# item's own URL is a secondary report of it, e.g. [793] "Google Jules
# Turndown notice Oct 29" or [802] "rebuilt from Mistral's own
# deprecation page" (both falsely tagged [no primary link] on
# 2026-11-08).
PRIMARY_CITATION_RE = re.compile(
    r"(turndown|shutdown|deprecation|sunset)\s+notice"
    r"|\bown\s+(deprecation|shutdown|changelog|docs|documentation|release\s+notes)"
    r"|deprecation\s+page"
    r"|engineering\s+blog"
    r"|official\s+(changelog|release\s+notes|docs|documentation|blog|notice|announcement)",
    re.IGNORECASE)


def _raw_cites_primary(item) -> bool:
    """True when a raw item itself carries / cites a primary source."""
    if not item:
        return False
    url = (item.get("url") or "").lower()
    host = re.sub(r"^https?://", "", url).split("/")[0].split(":")[0]
    if host in PRIMARY_HOSTS or any(
            host == h or host.endswith("." + h) for h in PRIMARY_HOSTS):
        return True
    text = f"{item.get('title') or ''} {item.get('summary') or ''}"
    return bool(PRIMARY_CITATION_RE.search(text))


def _sections(markdown: str) -> dict[str, str]:
    """Split digest markdown into its ## sections."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in markdown.splitlines():
        m = re.match(r"##\s+(.+)", line)
        if m:
            current = m.group(1).strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {k: "\n".join(v) for k, v in sections.items()}


def check_digest(markdown: str, expected_ids=None, items=None) -> list[str]:
    """Return a list of blocking problems; empty means the digest is clean.

    expected_ids: raw item ids collected for the day. When given, every
    one must appear somewhere in the digest (recall gate).
    items: raw item dicts for the day. When given, the primary-URL
    propagation gate (section 7) can check [no primary link] tags
    against what the raw items actually cite.
    """
    problems: list[str] = []

    # 1. [no date] budget — raw items carry dates; the model must extract them.
    no_date = len(NO_DATE_RE.findall(markdown))
    if no_date > MAX_NO_DATE:
        problems.append(
            f"{no_date} [no date] tags (limit {MAX_NO_DATE}): "
            "dates were in the raw items, extraction failed"
        )

    # 2. Internal drafting notes leaked into publishable text.
    for line in markdown.splitlines():
        for pat in LEAK_PATTERNS:
            if pat.search(line):
                problems.append(
                    f"internal note leaked into digest: {line.strip()[:120]}"
                )
                break

    # 3. Recall lock: every id cited outside What happened must also be
    #    introduced there.
    sections = _sections(markdown)
    what_happened = sections.get("What happened", "")
    if what_happened:
        introduced = set(ID_RE.findall(what_happened))
        for name, body in sections.items():
            # Missed / watch is the rejection log (recall gate): ids listed
            # there as Rejected are accounted for, not orphan citations.
            # Watch appendix (2026-11-04 reflection) holds the overflow
            # beyond the top-3 Watch cap and is likewise a rejection log.
            if name in ("What happened", "Missed / watch", "Watch appendix"):
                continue
            for cited in set(ID_RE.findall(body)):
                if cited not in introduced:
                    problems.append(
                        f"orphan citation [{cited}] in '{name}': "
                        "no matching line in What happened"
                    )
    else:
        problems.append("digest has no 'What happened' section")

    # 4. Recall gate: every raw item id must appear somewhere — included
    #    in What happened or explicitly Rejected in Missed / watch.
    if expected_ids:
        present = set(ID_RE.findall(markdown))
        for eid in expected_ids:
            if str(eid) not in present:
                problems.append(
                    f"recall gate: raw item [{eid}] appears nowhere — "
                    "include it or list it as Rejected / Watch in Missed / watch"
                )

    # 6. Tag hygiene — dated primary for announced-live (2026-11-05
    #    reflection): an [announced-live] line tagged [no date] has no
    #    dated primary announcement, so it cannot carry announced-live.
    if what_happened:
        bullets = [ln for ln in what_happened.splitlines()
                   if ln.lstrip().startswith("- ")]
        for ln in bullets:
            if (re.search(r"\[announced-live\]", ln, re.IGNORECASE)
                    and re.search(r"\[no date\]", ln, re.IGNORECASE)):
                problems.append(
                    "tag hygiene: [announced-live] line also tagged "
                    f"[no date]: {ln.strip()[:120]} — announced-live "
                    "requires a dated primary announcement, "
                    "otherwise demote to Watch"
                )

    # 5. Lead / claimed-live primary gate (2026-11-02 reflection):
    #    never headline a [no primary link] item, and a claimed-live
    #    [announced-live] line must not also admit it has no primary link.
    #    Exception (2026-11-06 reflection): a safety-critical lead —
    #    a Preparedness / safety-framework Critical classification or
    #    exploit-benchmark (e.g. ExploitGym) results in its own line —
    #    may lead even if primary docs are pending; it still may not
    #    carry [announced-live] without a primary link (checked below).
    if what_happened:
        bullets = [ln for ln in what_happened.splitlines()
                   if ln.lstrip().startswith("- ")]
        safety_critical = re.compile(
            r"(preparedness.{0,40}critical|critical.{0,40}preparedness"
            r"|exploitgym|cyber.{0,30}critical)",
            re.IGNORECASE)
        if (bullets and re.search(r"\[no primary link\]", bullets[0], re.IGNORECASE)
                and not safety_critical.search(bullets[0])):
            problems.append(
                "lead gate: first What happened bullet is tagged "
                "[no primary link] — never headline a no-primary item; "
                "demote it to Watch"
            )
        for ln in bullets:
            if (re.search(r"\[announced-live\]", ln, re.IGNORECASE)
                    and re.search(r"\[no primary link\]", ln, re.IGNORECASE)):
                problems.append(
                    "claimed-live gate: [announced-live] line also tagged "
                    f"[no primary link]: {ln.strip()[:120]} — claimed-live "
                    "requires a primary URL / live-proof artifact, "
                    "otherwise demote to Watch"
                )

    # 8. Retirement / cutoff / billing primary-or-demote
    #    (2026-11-09 reflection): a single-source, no-primary item
    #    claiming a retirement, deprecation, shutdown, access cutoff,
    #    reroute, or billing / allowance / pricing change must not
    #    appear in What happened at all — demote it to Watch until a
    #    changelog / docs / help page is fetched. Multi-outlet
    #    secondary-only items keep the 2026-11-07 auto-promotion
    #    non-lead line, so this gate requires BOTH tags.
    if what_happened:
        category_re = re.compile(
            r"(retir|deprecat|shutdown|sunset|cutoff|cut-off"
            r"|reroute|re-route|billing|allowance|price change"
            r"|pricing change|loses .{0,30}access"
            r"|fails after|closed to new users)",
            re.IGNORECASE)
        safety_critical = re.compile(
            r"(preparedness.{0,40}critical|critical.{0,40}preparedness"
            r"|exploitgym|cyber.{0,30}critical)",
            re.IGNORECASE)
        for ln in [b for b in what_happened.splitlines()
                   if b.lstrip().startswith("- ")]:
            if (re.search(r"\[single source\]", ln, re.IGNORECASE)
                    and re.search(r"\[no primary link\]", ln, re.IGNORECASE)
                    and category_re.search(ln)
                    and not safety_critical.search(ln)):
                problems.append(
                    "primary-or-demote: single-source no-primary "
                    f"retirement / cutoff / billing line in What "
                    f"happened: {ln.strip()[:120]} — demote to Watch "
                    "until a linked changelog / docs page is fetched"
                )

    # 7. Primary-URL propagation (2026-11-08 reflection): if a raw item
    #    itself carries or cites a primary source, its line must not be
    #    tagged [no primary link] — that tag would falsely claim the
    #    source is missing when the pipeline merely dropped the URL in
    #    summarising ([793] Jules turndown notice, [802] Mistral's own
    #    deprecation page). Bounce the digest back instead of
    #    publishing the false missing-source flag: propagate the
    #    primary URL, or send the item to the fetch queue.
    if items:
        by_id = {str(it["id"]): it for it in items}
        for line in markdown.splitlines():
            if not NO_PRIMARY_RE.search(line):
                continue
            for cited in ID_RE.findall(line):
                if _raw_cites_primary(by_id.get(cited)):
                    problems.append(
                        f"primary-url propagation: [{cited}] tagged "
                        "[no primary link] but its raw item cites a "
                        "primary source — propagate that primary URL "
                        "instead of publishing a false missing-source "
                        f"flag: {line.strip()[:120]}"
                    )

    return sorted(set(problems))


if __name__ == "__main__":
    import sys

    day = sys.argv[1] if len(sys.argv) > 1 else None
    if not day:
        raise SystemExit("usage: validate.py YYYY-MM-DD")
    with open(f"../digests/{day}.md") as fh:
        text = fh.read()
    expected_ids = None
    items = None
    try:
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import db
        items = db.items_on(day)
        expected_ids = [str(it["id"]) for it in items]
    except Exception:
        pass
    problems = check_digest(text, expected_ids=expected_ids, items=items)
    if problems:
        print("VALIDATION FAILED:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print("digest passes validation")
