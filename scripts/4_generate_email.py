#!/usr/bin/env python3
"""Step 4: teaser email (table layout, inline CSS only) -> output/<conf>/email_newsletter.html.

Thumbnails use absolute URLs on the deployed site, so run `mkdocs gh-deploy` first.
Featured cards: the author's own poster first, then the first analyzed tech photos.
"""
import html
import sys
from pathlib import Path

import yaml

from common import parse_args, site

MAX_CARDS = 3
SITE = site()["base_url"]  # set per run in main()

FONT = "font-family:Arial,'Malgun Gothic',sans-serif;"


def cta() -> str:
    return (
        f'<tr><td align="center" style="padding:20px 24px;">'
        f'<a href="{SITE}" style="{FONT}display:inline-block;background:#1565c0;color:#ffffff;'
        f'text-decoration:none;font-size:15px;font-weight:bold;padding:14px 24px;border-radius:6px;">'
        f"👉 전체 시간순 타임라인 및 슬라이드 상세 분석 보러 가기 (Web Archive)</a></td></tr>"
    )


def card(img_url: str, title: str, text: str) -> str:
    return (
        '<tr><td style="padding:12px 24px;"><table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="border:1px solid #dddddd;border-radius:6px;"><tr>'
        f'<td width="200" valign="top" style="padding:10px;"><img src="{html.escape(img_url)}" width="180" '
        f'alt="{html.escape(title)}" style="display:block;border:0;"></td>'
        f'<td valign="top" style="padding:10px;{FONT}font-size:14px;color:#333333;line-height:1.5;">'
        f'<div style="font-size:15px;font-weight:bold;margin-bottom:6px;">{html.escape(title)}</div>'
        f"{html.escape(text)}</td></tr></table></td></tr>"
    )


def main() -> int:
    global SITE
    _, conf = parse_args("Generate teaser email for one conference.")
    base = site()["base_url"].rstrip("/") + "/"
    SITE = base + conf.id + "/"
    manifest = yaml.safe_load((conf.manifest).read_text())["photos"]
    analysis = (yaml.safe_load(conf.analysis.read_text()) if conf.analysis.exists() else None) or {}
    if not analysis:
        print("note: no analysis.yaml yet (run step 2); cards will be empty")
    cands = [(p, analysis[p["file"]]) for p in manifest if p["include"] and p["file"] in analysis]
    cands.sort(key=lambda pa: not pa[1].get("is_my_poster"))  # stable: my poster first

    cards = "".join(
        card(SITE + p["out"], a.get("title") or p["file"], (a.get("perspective") or "").split("\n")[0][:220])
        for p, a in cands[:MAX_CARDS]
    )
    insights = "".join(
        f'<li style="margin-bottom:6px;">{html.escape(x)}</li>'
        for x in ["INSIGHT 1 — edit me", "INSIGHT 2 — edit me", "INSIGHT 3 — edit me"]
    )
    doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{conf.title} Field Note</title></head>
<body style="margin:0;padding:0;background:#f2f2f2;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f2f2f2;"><tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff;">
<tr><td style="background:#0d2c54;padding:28px 24px;{FONT}color:#ffffff;">
<div style="font-size:22px;font-weight:bold;">{conf.title} Field Note</div>
<div style="font-size:14px;margin-top:6px;">{html.escape(conf.meta.get("tagline", ""))}</div></td></tr>
<tr><td style="padding:20px 24px 0;{FONT}font-size:15px;color:#333333;line-height:1.6;">
<b>Executive Summary</b> — {conf.title}에서 확인한 3대 인사이트
<ul style="padding-left:20px;">{insights}</ul></td></tr>
{cta()}
{cards}
{cta()}
<tr><td style="padding:12px 24px 24px;{FONT}font-size:12px;color:#888888;">Nemo Kyuho SHIM · <a href="{SITE}" style="color:#888888;">{SITE}</a></td></tr>
</table></td></tr></table></body></html>"""
    out = conf.output / "email_newsletter.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc)
    print(f"wrote {out} ({min(len(cands), MAX_CARDS)} cards). Edit the 3 insight placeholders.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
