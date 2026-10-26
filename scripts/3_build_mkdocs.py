#!/usr/bin/env python3
"""Step 3: build one page per conference (my work first, then every poster/slide in
time order, tag index, related links) and rebuild the global index.md / mkdocs.yml nav.

Usage: 3_build_mkdocs.py --conf dac2026
"""
import sys
from collections import defaultdict
from datetime import datetime

import yaml

from common import ROOT, conference_ids, load_conf, parse_args, site

MKDOCS = ROOT / "mkdocs.yml"


def indent(text: str) -> str:
    return "\n".join("    " + l if l else "" for l in str(text).strip().splitlines())


def slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")


def item_id(p: dict) -> str:
    return "p" + p["file"].rsplit(".", 1)[0].replace("_", "")


def photo_block(p: dict, a: dict, related: list[tuple[str, str]]) -> str:
    out = [f"### {a['title']} {{#{item_id(p)}}}", ""]
    if a.get("presenter_or_company"):
        out += [f"**{a['presenter_or_company']}**", ""]
    out += [f"![{a['title']}]({p['out']}){{ loading=lazy }}", ""]
    tags = " ".join(f"[`{t}`](#tag-{slug(t)})" for t in a.get("tags", []))
    if tags:
        out += [tags, ""]
    out += ['!!! info "Slide / Poster Summary"', indent(a.get("summary", "")), ""]
    if a.get("perspective") and not a["perspective"].startswith("("):
        out += ['!!! tip "Front-End & Emulation Perspective"', indent(a["perspective"]), ""]
    if related:
        out += ["Related: " + " · ".join(f"[{t}](#{i})" for t, i in related), ""]
    return "\n".join(out)


def build_conf(conf) -> None:
    photos = [p for p in yaml.safe_load(conf.manifest.read_text())["photos"] if p["include"]]
    analysis = (yaml.safe_load(conf.analysis.read_text()) if conf.analysis.exists() else None) or {}
    photos = [p for p in photos if p["file"] in analysis]
    mine = [p for p in photos if analysis[p["file"]].get("is_my_poster")]
    others = [p for p in photos if not analysis[p["file"]].get("is_my_poster")]

    by_tag = defaultdict(list)
    for p in photos:
        for t in analysis[p["file"]].get("tags", []):
            if t != "my-work":
                by_tag[t].append(p)

    def related(p):
        mytags = set(analysis[p["file"]].get("tags", [])) - {"my-work"}
        scored = [(len(mytags & set(analysis[q["file"]].get("tags", []))), q) for q in photos if q is not p]
        scored = [(n, q) for n, q in scored if n]
        scored.sort(key=lambda x: -x[0])
        return [(analysis[q["file"]]["title"], item_id(q)) for _, q in scored[:3]]

    m = conf.meta
    lines = [f"# {conf.title}", "",
             f"{m['full_name']} · {m.get('location', '')} · {m.get('dates', '')}", "",
             f"[Official site]({m['url']}) · [Home](../index.md)" if m.get("url") else "[Home](../index.md)", "",
             f"*{m.get('tagline', '')}* — {len(photos)} posters and slides I looked at.", ""]
    if m.get("interests"):
        by_stem = {p["file"].rsplit(".", 1)[0]: p for p in photos}
        lines += ["## What I Wanted to Learn at DAC", ""]
        for it in m["interests"]:
            links = ", ".join(f"[{analysis[by_stem[s]['file']]['title']}](#{item_id(by_stem[s])})"
                              for s in it["items"] if s in by_stem)
            lines.append(f"- **{it['title']}**" + (f" — {it['note']}" if it.get("note") else "")
                         + (f" {links}" if links else ""))
        lines.append("")
        prog = conf.config / "program.yaml"
        if prog.exists():
            pg = yaml.safe_load(prog.read_text())
            lines += ["## From the Official DAC 2026 Program", "",
                      f"Titles, times and rooms only, from the [official program]({pg['source']}); "
                      "not summaries and not necessarily sessions I attended.", ""]
            for t in pg["topics"]:
                lines += [f"### {t['interest']}", ""]
                if t.get("note"):
                    lines += [f"*{t['note']}*", ""]
                for ss in t["sessions"]:
                    lines.append(f"- **{ss['session']}** — {ss['when']}, {ss['where']}")
                    lines += [f"    - {x}" for x in ss["talks"]]
                lines.append("")
    if mine:
        lines += ["## My Work", ""]
        lines += [photo_block(p, analysis[p["file"]], related(p)) for p in mine]
    lines += ["## Posters & Slides", ""]
    lines += [photo_block(p, analysis[p["file"]], related(p)) for p in others]
    lines += ["## Tags", ""]
    for t in sorted(by_tag):
        links = ", ".join(f"[{analysis[p['file']]['title']}](#{item_id(p)})" for p in by_tag[t])
        lines += [f"### {t} {{#tag-{slug(t)}}}", "", links, ""]
    conf.docs.mkdir(parents=True, exist_ok=True)
    (conf.docs / "index.md").write_text("\n".join(lines) + "\n")
    conf.nav.write_text(yaml.safe_dump({"title": conf.title, "nav": [{"Overview": f"{conf.id}/index.md"}]},
                                       allow_unicode=True, sort_keys=False))


def build_global() -> None:
    s = site()
    confs = [load_conf(c) for c in conference_ids()]
    confs = [c for c in confs if c.nav.exists()]
    confs.sort(key=lambda c: str(c.meta.get("dates", "")), reverse=True)  # newest first

    home = [f"# {s['site_name']}", "", f"*{s['tagline']}*", "", f"!!! quote \"\"\n    {s['intro']}", ""]
    nav = [{"Home": "index.md"}]
    for c in confs:
        nav.append({c.title: f"{c.id}/index.md"})
        m = c.meta
        kind = m.get("type", "event").capitalize()
        topics = " ".join(f"`{t}`" for t in m.get("topics", []))
        home.append(f"- **[{c.title}]({c.id}/index.md)** · {kind} — {m['full_name']}, "
                    f"{m.get('location', '')} ({m.get('dates', '')}) {topics}".rstrip())
    for label, url in (s.get("links") or {}).items():
        nav.append({label: url})
        home.append(f"- [{label}]({url})")
    (ROOT / "docs" / "index.md").write_text("\n".join(home) + "\n")

    cfg = yaml.safe_load(MKDOCS.read_text())
    cfg["site_name"], cfg["site_author"], cfg["nav"] = s["site_name"], s["author"], nav
    MKDOCS.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))


def main() -> int:
    _, conf = parse_args("Build MkDocs pages for one conference.")
    build_conf(conf)
    build_global()
    print(f"built {conf.id}; run `python3 -m mkdocs serve`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
