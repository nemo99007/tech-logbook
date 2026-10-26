#!/usr/bin/env python3
"""Step 2: Vision-LLM analysis of kind=tech photos -> config/analysis.yaml.

Usage: 2_analyze_slides.py --conf dac2026 [--force] [--limit N]. Needs ANTHROPIC_API_KEY.
Prompt = config/persona.md + config/<conf>/persona.md + conference.yaml. Already-analyzed photos are skipped, so hand edits in
analysis.yaml survive re-runs. Use --force to redo everything.
"""
import base64
import json
import sys
from pathlib import Path

import anthropic
import yaml

from common import parse_args

MODEL = "claude-sonnet-5-5"

def system_prompt(conf) -> str:
    parts = [(conf.config.parent / "persona.md").read_text()]
    extra = conf.config / "persona.md"
    if extra.exists():
        parts.append(extra.read_text())
    parts.append(f"Conference: {conf.meta['full_name']} ({conf.meta['short_name']}), "
                 f"{conf.meta.get('location', '')}, {conf.meta.get('dates', '')}.")
    if conf.meta.get("my_work"):
        parts.append("The author's own work at this conference: " + str(conf.meta["my_work"]).strip())
    return "\n\n".join(parts)


PROMPT = """Analyze this photo. If it is not a slide/poster/architecture board, set is_technical=false.
Reply with ONLY a JSON object:
{"is_technical": bool, "title": str|null, "presenter_or_company": str|null,
 "is_my_poster": bool  /* the author's own work, see system prompt */,
 "summary": str  /* 3-4 lines of facts + data flow of the diagram */,
 "perspective": str  /* front-end & emulation take: why interesting, bottleneck/limits, 3-5 lines */}"""


def ask(client, system: str, path: Path) -> dict:
    data = base64.standard_b64encode(path.read_bytes()).decode()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}},
            {"type": "text", "text": PROMPT},
        ]}],
    )
    text = msg.content[0].text.strip()
    text = text[text.find("{"): text.rfind("}") + 1]
    return json.loads(text)


def main() -> int:
    args, conf = parse_args("Vision analysis of slides.",
                            (("--force",), {"action": "store_true", "help": "redo already analyzed photos"}),
                            (("--limit",), {"type": int, "default": 0, "help": "analyze at most N photos (trial run)"}))
    force, MANIFEST, ANALYSIS = args.force, conf.manifest, conf.analysis
    system = system_prompt(conf)
    photos = yaml.safe_load(MANIFEST.read_text())["photos"]
    done = {} if force or not ANALYSIS.exists() else (yaml.safe_load(ANALYSIS.read_text()) or {})
    client = anthropic.Anthropic()
    todo = [p for p in photos if p["include"] and p["kind"] == "tech" and p["file"] not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} photos to analyze")
    for p in todo:
        try:
            done[p["file"]] = ask(client, system, conf.docs / p["out"])
        except Exception as e:  # keep going; rerun picks up failures
            print(f"  FAIL {p['file']}: {e}")
            continue
        ANALYSIS.write_text(yaml.safe_dump(done, allow_unicode=True, sort_keys=False))
        print(f"  ok   {p['file']}: {done[p['file']].get('title')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
