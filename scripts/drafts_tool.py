#!/usr/bin/env python3
"""Local draft pages: status tracking and promotion into docs/.

A draft is unpublished when its first heading ends with " (unpublished)"; otherwise it is a
draft under review. `mark` adds or removes that suffix, so the state is visible in the page title.
Nothing here pushes or deploys; `publish` only copies files into docs/ and edits nav/home.

  drafts_tool.py list
  drafts_tool.py mark <slug> draft|unpublished
  drafts_tool.py publish <slug> [<slug> ...]   (nav and home end up newest event first)
"""
import re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS, DOCS = ROOT / "drafts", ROOT / "docs"
MARK = " (unpublished)"


def pages():
    return sorted(p.parent for p in DRAFTS.glob("*/index.md"))


def read(slug_dir):
    body = (slug_dir / "index.md").read_text()
    title = re.search(r"^# (.+)$", body, re.M).group(1)
    if title.endswith(MARK):
        return "unpublished", title[: -len(MARK)], body
    return "draft", title, body


def write(slug_dir, status, body):
    title = re.search(r"^# (.+)$", body, re.M).group(1)
    clean = title[: -len(MARK)] if title.endswith(MARK) else title
    new = clean + (MARK if status == "unpublished" else "")
    (slug_dir / "index.md").write_text(body.replace(f"# {title}", f"# {new}", 1))


def refresh_index():
    lines = ["# Drafts (local preview only)", ""]
    items = sorted((read(d)[0] == "unpublished", read(d)[1], d.name) for d in pages())
    for unpub, title, name in items:  # unpublished drafts go to the bottom
        lines.append(f"- [{title}{MARK if unpub else ''}]({name}/index.md)")
    (DRAFTS / "index.md").write_text("\n".join(lines) + "\n")


def cmd_list():
    for d in pages():
        status, title, _ = read(d)
        print(f"{status:12} {d.name:28} {title}")


def cmd_mark(slug, status):
    assert status in ("draft", "unpublished"), status
    d = DRAFTS / slug
    _, _, body = read(d)
    write(d, status, body)
    refresh_index()


def event_date(slug):
    """Latest YYYY-MM-DD in the page's opening lines (a range or two-day event sorts by its last day)."""
    for base in (DOCS, DRAFTS):
        f = base / slug / "index.md"
        if f.exists():
            dates = re.findall(r"20\d\d-\d\d-\d\d", "\n".join(f.read_text().splitlines()[:8]))
            if dates:
                return max(dates)
    return ""


def sort_newest_first():
    """Published pages go newest event first, in the nav and on the home page."""
    mk = ROOT / "mkdocs.yml"
    lines = mk.read_text().splitlines(keepends=True)
    ev = [i for i, l in enumerate(lines) if re.match(r"- .+: [\w-]+/index\.md$", l.strip())]
    if ev:
        block = sorted((lines[i] for i in ev), key=lambda l: event_date(re.search(r"([\w-]+)/index\.md", l).group(1)), reverse=True)
        lines[ev[0] : ev[-1] + 1] = block
        mk.write_text("".join(lines))
    home = DOCS / "index.md"
    lines = home.read_text().splitlines(keepends=True)
    ev = [i for i, l in enumerate(lines) if re.match(r"- \*\*\[.+\]\([\w-]+/index\.md\)", l)]
    if ev:
        block = sorted((lines[i] for i in ev), key=lambda l: event_date(re.search(r"\(([\w-]+)/index\.md\)", l).group(1)), reverse=True)
        lines[ev[0] : ev[-1] + 1] = block
        home.write_text("".join(lines))


def cmd_publish(slugs):
    for slug in slugs:
        d = DRAFTS / slug
        status, title, body = read(d)
        if status == "unpublished":
            print(f"skip {slug}: marked unpublished")
            continue
        dest = DOCS / slug
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(d, dest)
        (dest / "index.md").write_text(body)  # status is "draft" here, so the title is clean
        mk = ROOT / "mkdocs.yml"
        s = mk.read_text()
        entry = f"- {title}: {slug}/index.md\n"
        if entry not in s:
            s = s.replace("- Papers (yt-paper):", entry + "- Papers (yt-paper):")
            mk.write_text(s)
        home = DOCS / "index.md"
        h = home.read_text()
        meta = next(l for l in body.splitlines()[1:] if l.strip())
        item = f"- **[{title}]({slug}/index.md)** · {meta}\n"
        if f"({slug}/index.md)" not in h:
            h = h.replace("- [Papers (yt-paper)]", item + "- [Papers (yt-paper)]")
            home.write_text(h)
        print(f"published (local files only): {slug}")
    sort_newest_first()


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["list"]:
        cmd_list()
    elif a[:1] == ["mark"]:
        cmd_mark(a[1], a[2])
    elif a[:1] == ["publish"]:
        cmd_publish(a[1:])
    else:
        print(__doc__)
