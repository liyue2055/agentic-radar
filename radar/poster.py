#!/usr/bin/env python3
"""Generate a visual for the digest or the reflection.

    python3 radar/poster.py digest 2026-10-05    # poster of the day's main story
    python3 radar/poster.py reflect 2026-10-05  # visual for the reflection

Two API calls per run: one cheap text call to turn the markdown into a tight
image prompt, then /images/generations (muse-image-1.0, ~$0.01).
Saves site/<day>-poster.png / site/<day>-reflect.png (1024x1024) so the
images publish with the static site.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.expanduser("~/workspace/skills/meta-model-api/bin")


def api(payload: dict) -> dict:
    with open("/tmp/radar_poster.json", "w") as fh:
        json.dump(payload, fh)
    r = subprocess.run(
        [f"{BIN}/model-api-call", "POST", "/chat/completions", "@/tmp/radar_poster.json"],
        capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise SystemExit(f"poster text call failed: {r.stderr.strip()}")
    return json.loads(r.stdout)


def make_image_prompt(markdown: str, kind: str) -> str:
    if kind == "digest":
        brief = ("Write a single-paragraph image prompt for an editorial "
                 "poster / infographic that captures the single biggest story "
                 "below. Bold minimalist style, symbolic imagery, almost no "
                 "text in the image (a short headline at most).")
    else:
        brief = ("Write a single-paragraph image prompt for an editorial "
                 "illustration about a newsroom editor reviewing the day's "
                 "work with a red pen — learning from mistakes, sharper "
                 "tomorrow. Symbolic, minimal, almost no text in the image.")
    data = api({
        "model": "muse-spark-1.3",
        "reasoning_effort": "minimal",
        "max_tokens": 600,
        "messages": [{"role": "user",
                      "content": f"{brief}\n\nSOURCE:\n{markdown[:4000]}"}],
    })
    content = (data["choices"][0]["message"].get("content") or "").strip()
    if content:
        return content
    print("empty prompt draft, retrying once...")
    data = api({
        "model": "muse-spark-1.3",
        "reasoning_effort": "minimal",
        "max_tokens": 600,
        "messages": [{"role": "user",
                      "content": f"{brief}\n\nSOURCE:\n{markdown[:4000]}"}],
    })
    content = (data["choices"][0]["message"].get("content") or "").strip()
    if content:
        return content
    # last-resort canned prompts so the pipeline never breaks
    return ("Bold minimalist editorial poster, symbolic imagery, almost no "
            "text." if kind == "digest" else
            "Minimalist editorial illustration of an editor's red pen "
            "reviewing newspaper layouts, symbolic, almost no text.")


def generate(prompt: str) -> bytes:
    sys.path.insert(0, BIN)
    from _client import post  # noqa: E402
    data = post("/images/generations",
                {"model": "muse-image-1.0", "prompt": prompt,
                 "size": "1024x1024"})
    return base64.b64decode(data["data"][0]["b64_json"])


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ("digest", "reflect"):
        print("usage: poster.py <digest|reflect> YYYY-MM-DD", file=sys.stderr)
        sys.exit(2)
    kind, day = sys.argv[1], sys.argv[2]
    src = os.path.join(ROOT, "digests" if kind == "digest" else "reflections",
                       f"{day}.md")
    if not os.path.exists(src):
        raise SystemExit(f"missing {src}; run the {kind} first")
    markdown = open(src).read()
    print("drafting image prompt...")
    prompt = make_image_prompt(markdown, kind)
    print(f"prompt: {prompt[:160]}...")
    print("generating image (~$0.01)...")
    img = generate(prompt)
    name = f"{day}-{'poster' if kind == 'digest' else 'reflect'}.png"
    out = os.path.join(ROOT, "site", name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as fh:
        fh.write(img)
    print(f"saved {out} ({len(img)//1024} KB)")


if __name__ == "__main__":
    main()
