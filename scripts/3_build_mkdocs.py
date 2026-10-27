#!/usr/bin/env python3
"""Step 3: build one page per conference (my work first, then every poster/slide in
time order, tag index, related links) and rebuild the global index.md / mkdocs.yml nav.

Usage: 3_build_mkdocs.py --conf dac2026
"""
import sys
from collections import defaultdict
from datetime import datetime

import re

import yaml

from common import ROOT, conference_ids, load_conf, parse_args, site

MKDOCS = ROOT / "mkdocs.yml"


def indent(text: str) -> str:
    return "\n".join("    " + l if l else "" for l in str(text).strip().splitlines())


def slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", t.lower())


def program_url(title: str, index: dict) -> str:
    n = _norm(title)
    for t, u in index.items():
        k = _norm(t)
        if k and (k in n or n in k):
            return u
    return ""


def item_id(p: dict) -> str:
    return "p" + p["file"].rsplit(".", 1)[0].replace("_", "")


def photo_block(p: dict, a: dict, related: list[tuple[str, str]], official: dict | None = None, src: str = "", arch: str = "", page: str = "", hub: str = "") -> str:
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
    if official:
        out += ['!!! abstract "In the official DAC 2026 program"',
                indent(f"*{official['title']}*  \n{official['session']} — {official['when']}, {official['where']}"
                       + (f" · [program]({src})" if src else "")
                       + (f" · [official page]({page})" if page else "")
                       + (f" · [archive]({arch})" if arch else "")), ""]
    elif hub:
        out += [f"Official DAC 2026: [63rd DAC page]({hub})", ""]
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

    m_url = conf.meta.get("url", "")
    prog_path = conf.config / "program.yaml"
    pg = yaml.safe_load(prog_path.read_text()) if prog_path.exists() else {}
    by_photo = pg.get("by_photo", {}) or {}
    idx_path = conf.config / "program_index.yaml"
    index = (yaml.safe_load(idx_path.read_text()) or {}).get("pages", {}) if idx_path.exists() else {}

    def official(p):
        return by_photo.get(p["file"].rsplit(".", 1)[0])

    def photo_link(talk):
        for stem, o in by_photo.items():
            if o["title"] in talk:
                q = next((x for x in photos if x["file"].startswith(stem)), None)
                if q:
                    return f" — [my photo](#{item_id(q)})"
        return ""

    m = conf.meta
    lines = [f"# {conf.title}", "",
             f"{m['full_name']} · {m.get('location', '')} · {m.get('dates', '')}", "",
             f"[Official site]({m['url']}) · [Home](../index.md)" if m.get("url") else "[Home](../index.md)", "",
             f"*{m.get('tagline', '')}* — {len(photos)} posters and slides I looked at.", ""]
    if pg.get("archive"):
        lines += ["## Official DAC 2026 Archive", "",
                  "Everything here comes from the official conference; my photos below link back to it.", ""]
        lines += [f"- [{a['name']}]({a['url']})" for a in pg["archive"]]
        lines += ["", "Every talk, poster and paper has its own page, with abstract, in the searchable program; "
                  "full texts are in the ACM proceedings (research) and the Engineering Track proceedings zip.", ""]
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
                    for x in ss["talks"]:
                        u = program_url(re.sub(r"\s*\(.*?\)\s*\$", "", x), index)
                        lines.append(f"    - {f'[{x}]({u})' if u else x}{photo_link(x)}")
                lines.append("")
    if mine:
        lines += ["## My Work", ""]
        lines += [photo_block(p, analysis[p["file"]], related(p), official(p), pg.get("source", ""), "#official-dac-2026-archive" if pg.get("archive") else "",
                           program_url(official(p)["title"], index) if official(p) else "", m_url) for p in mine]
    lines += ["## Posters & Slides", ""]
    lines += [photo_block(p, analysis[p["file"]], related(p), official(p), pg.get("source", ""), "#official-dac-2026-archive" if pg.get("archive") else "",
                           program_url(official(p)["title"], index) if official(p) else "", m_url) for p in others]
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
