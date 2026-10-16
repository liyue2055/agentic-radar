"""Pre-publish validation for the daily digest.

Blocks publishing when the generated digest shows the failure modes flagged
by the nightly reflection:
  - too many [no date] tags (model didn't extract dates the raw items had)
  - internal editorial notes leaking into the published sections
  - citations in later sections with no matching line in What happened
    (orphan citations / recall-lock violations)
  - raw item ids that appear nowhere in the digest (recall-gate
    violations: silently dropped items must instead be listed as
    "Rejected [id] — reason" in Missed / watch)

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


def check_digest(markdown: str, expected_ids=None) -> list[str]:
    """Return a list of blocking problems; empty means the digest is clean.

    expected_ids: raw item ids collected for the day. When given, every
    one must appear somewhere in the digest (recall gate).
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
            if name in ("What happened", "Missed / watch"):
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
                    "include it or list it as Rejected in Missed / watch"
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
    try:
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import db
        expected_ids = [str(it["id"]) for it in db.items_on(day)]
    except Exception:
        pass
    problems = check_digest(text, expected_ids=expected_ids)
    if problems:
        print("VALIDATION FAILED:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print("digest passes validation")
