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
DRAFT = "--draft" in sys.argv  # write to drafts/<conf>/ only (never docs/, nav, mkdocs.yml)


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


def para(en: str, ko: str) -> list[str]:
    return [en, "{ .en }", "", ko, "{ .ko }", ""]


def head(level: int, en: str, ko: str, ko_id: str = "") -> list[str]:
    h = "#" * level
    return [f"{h} {en} {{ .en }}", "", f"{h} {ko} {{ .ko{' #' + ko_id if ko_id else ''} }}", ""]


def block(cls: str, inner: list[str]) -> list[str]:
    return [f'<div class="{cls}" markdown>', "", *inner, "", "</div>", ""]


def sp(en: str, ko: str) -> str:
    return f'<span class="en">{en}</span><span class="ko">{ko}</span>'


def item_id(p: dict) -> str:
    return "p" + p["file"].rsplit(".", 1)[0].replace("_", "")


def _official(official: dict, src: str, page: str, arch: str, ko: bool = False) -> str:
    lab = ("프로그램", "공식 페이지", "아카이브") if ko else ("program", "official page", "archive")
    return (f"*{official['title']}*  \n{official['session']} — {official['when']}, {official['where']}"
            + (f" · [{lab[0]}]({src})" if src else "")
            + (f" · [{lab[1]}]({page})" if page else "")
            + (f" · [{lab[2]}]({'#archive-ko' if ko else arch})" if arch else ""))


def photo_block(p: dict, a: dict, related: list[tuple[str, str]], official: dict | None = None, src: str = "", arch: str = "", page: str = "", hub: str = "") -> str:
    out = [f"### {a['title']} {{#{item_id(p)}}}", ""]
    if a.get("presenter_or_company"):
        out += [f"**{a['presenter_or_company']}**", ""]
    out += [f"![{a['title']}]({p['out']}){{ loading=lazy }}", ""]
    tags = " ".join(f"[`{t}`](#tag-{slug(t)})" for t in a.get("tags", []))
    if tags:
        out += [tags, ""]
    sum_ko = a.get("summary_ko")
    if sum_ko:
        out += block("en", ['!!! info "Slide / Poster Summary"', indent(a.get("summary", ""))])
        out += block("ko", ['!!! info "슬라이드 / 포스터 요약"', indent(sum_ko)])
    else:
        out += ['!!! info "Slide / Poster Summary"', indent(a.get("summary", "")), ""]
    if a.get("perspective") and not a["perspective"].startswith("("):
        if a.get("perspective_ko"):
            out += block("en", ['!!! tip "Front-End & Emulation Perspective"', indent(a["perspective"])])
            out += block("ko", ['!!! tip "프론트엔드 · 에뮬레이션 관점"', indent(a["perspective_ko"])])
        else:
            out += ['!!! tip "Front-End & Emulation Perspective"', indent(a["perspective"]), ""]
    if official:
        out += block("en", ['!!! abstract "In the official DAC 2026 program"', indent(_official(official, src, page, arch))])
        out += block("ko", ['!!! abstract "공식 DAC 2026 프로그램"', indent(_official(official, src, page, arch, ko=True))])
    elif hub:
        out += [f"Official DAC 2026: [63rd DAC page]({hub})", ""]
    if related:
        links = " · ".join(f"[{t}](#{i})" for t, i in related)
        out += [sp("Related:", "관련:") + " " + links, ""]
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
    n = len(photos)
    lines = [f"# {conf.title}", "",
             f"{m['full_name']} · {m.get('location', '')} · {m.get('dates', '')}", "",
             f"[Official site]({m['url']}) · [Home](../index.md)" if m.get("url") else "[Home](../index.md)", ""]
    lines += para(f"*{m.get('tagline', '')}* — {n} posters and slides I looked at.",
                  f"*{m.get('tagline_ko', m.get('tagline', ''))}* — 제가 본 포스터와 슬라이드 {n}개입니다.")
    ko_of = {i["title"]: i for i in m.get("interests", [])}
    if pg.get("archive"):
        lines += head(2, "Official DAC 2026 Archive", "공식 DAC 2026 아카이브", "archive-ko")
        lines += para("Everything here comes from the official conference; my photos below link back to it.",
                      "여기 있는 자료는 모두 공식 학회에서 나온 것이며, 아래 제 사진은 공식 자료로 연결됩니다.")
        lines += [f"- [{a['name']}]({a['url']})" for a in pg["archive"]]
        lines += [""]
        lines += para("Every talk, poster and paper has its own page, with abstract, in the searchable program; "
                      "full texts are in the ACM proceedings (research) and the Engineering Track proceedings zip.",
                      "모든 발표, 포스터, 논문은 검색 가능한 프로그램에 초록과 함께 각자의 페이지가 있고, "
                      "전문은 ACM 프로시딩(연구)과 Engineering Track 프로시딩 zip에 있습니다.")
    if m.get("interests"):
        by_stem = {p["file"].rsplit(".", 1)[0]: p for p in photos}
        lines += head(2, "What I Wanted to Learn at DAC", "DAC에서 배우고 싶었던 것")
        for it in m["interests"]:
            links = ", ".join(f"[{analysis[by_stem[s]['file']]['title']}](#{item_id(by_stem[s])})"
                              for s in it["items"] if s in by_stem)
            note = (" " + sp(it["note"], it.get("note_ko", it["note"]))) if it.get("note") else ""
            lines.append(f"- **{sp(it['title'], it.get('title_ko', it['title']))}** —{note}"
                         + (f" {links}" if links else ""))
        lines.append("")
        prog = conf.config / "program.yaml"
        if prog.exists():
            pg = yaml.safe_load(prog.read_text())
            lines += head(2, "From the Official DAC 2026 Program", "공식 DAC 2026 프로그램에서")
            lines += para(f"Titles, times and rooms only, from the [official program]({pg['source']}); "
                          "not summaries and not necessarily sessions I attended.",
                          f"[공식 프로그램]({pg['source']})에서 가져온 제목, 시간, 장소만 적었습니다. "
                          "요약이 아니고, 제가 참석한 세션이라는 뜻도 아닙니다.")
            for t in pg["topics"]:
                k = ko_of.get(t["interest"], {})
                lines += head(3, t["interest"], k.get("title_ko", t["interest"]))
                if t.get("note"):
                    lines += para(f"*{t['note']}*", f"*{t.get('note_ko', t['note'])}*")
                for ss in t["sessions"]:
                    lines.append(f"- **{ss['session']}** — {ss['when']}, {ss['where']}")
                    for x in ss["talks"]:
                        u = program_url(re.sub(r"\s*\(.*?\)\s*\$", "", x), index)
                        lines.append(f"    - {f'[{x}]({u})' if u else x}{photo_link(x)}")
                lines.append("")
    if mine:
        lines += head(2, "My Work", "내 작업")
        lines += [photo_block(p, analysis[p["file"]], related(p), official(p), pg.get("source", ""), "#official-dac-2026-archive" if pg.get("archive") else "",
                           program_url(official(p)["title"], index) if official(p) else "", m_url) for p in mine]
    lines += head(2, "Posters & Slides", "포스터와 슬라이드")
    lines += [photo_block(p, analysis[p["file"]], related(p), official(p), pg.get("source", ""), "#official-dac-2026-archive" if pg.get("archive") else "",
                           program_url(official(p)["title"], index) if official(p) else "", m_url) for p in others]
    lines += head(2, "Tags", "태그")
    for t in sorted(by_tag):
        links = ", ".join(f"[{analysis[p['file']]['title']}](#{item_id(p)})" for p in by_tag[t])
        lines += [f"### {t} {{#tag-{slug(t)}}}", "", links, ""]
    out_dir = ROOT / "drafts" / conf.id if DRAFT else conf.docs
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.md").write_text("\n".join(lines) + "\n")
    if DRAFT:
        return
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
    sys.argv = [a for a in sys.argv if a != "--draft"]
    _, conf = parse_args("Build MkDocs pages for one conference.")
    build_conf(conf)
    if not DRAFT:
        build_global()
    print(f"built {conf.id}; run `python3 -m mkdocs serve`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
