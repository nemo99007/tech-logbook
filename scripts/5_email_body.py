"""Build a paste-ready HTML body (inline images) for pasting into an email client."""
import base64, io, html, re
import yaml
from PIL import Image, ImageOps
from common import parse_args, load_conf

_, conf = parse_args("Build email-pasteable HTML")
meta = yaml.safe_load((conf.config / "conference.yaml").read_text())
ana = yaml.safe_load(conf.analysis.read_text())
man = yaml.safe_load(conf.manifest.read_text())
names = [n for n in sorted(ana) if ana[n].get("is_technical")]
names.sort(key=lambda n: (not ana[n].get("is_my_poster"), n))

LOBBY = "20260726_084622.jpg"   # email only: raw panorama, re-encoded (no EXIF); not on the site

def img(name):
    if name == LOBBY:
        im = ImageOps.exif_transpose(Image.open(conf.raw / name)).convert("RGB")
        im.thumbnail((1200, 1200))
    else:
        im = Image.open(conf.images / name).convert("RGB")
        im.thumbnail((800, 800))
    b = io.BytesIO(); im.save(b, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()

e = html.escape
out = [f'<div style="font-family:Arial,sans-serif;max-width:760px;font-size:14px;line-height:1.5">',
       f'<h2>{e(meta["short_name"])} field note</h2>',
       f'<p>{e(meta["full_name"])} · {e(meta["location"])}<br>Full notes: <a href="https://nemo99007.github.io/tech-logbook/{conf.id}/">nemo99007.github.io/tech-logbook/{conf.id}/</a></p>']
for n in names:
    a = ana[n]
    out.append(f'<hr><h3>{"★ " if a.get("is_my_poster") else ""}{e(a["title"])}</h3>')
    if a.get("presenter_or_company"): out.append(f'<p><b>{e(a["presenter_or_company"])}</b></p>')
    out.append(f'<img src="{img(n)}" style="max-width:100%"><p>{e(a["summary"])}</p><p><i>{e(a["perspective"])}</i></p>')
out.append("</div>")
dst = conf.output; dst.mkdir(parents=True, exist_ok=True)
(dst / "email_body.html").write_text("\n".join(out))
print(dst / "email_body.html", len(names), "items")

# Overview with a few sentences and two photos of other people's work
pick = [LOBBY, "20260728_172318.jpg"]
d = ['<div style="font-family:Arial,sans-serif;max-width:640px;font-size:14px;line-height:1.5">',
     f'<h3>{e(meta["short_name"])} · {e(meta["location"])}</h3>',
     '<p>DAC is one of the world&#39;s leading conferences on chip design and design automation. '
     'The 63rd edition was held July 26–29, 2026 in Long Beach, California.</p>']
for n in pick:
    cap = "Long Beach Convention Center lobby" if n == LOBBY else f'{ana[n]["title"]} ({ana[n]["presenter_or_company"]})'
    d.append(f'<p><img src="{img(n)}" style="max-width:100%"><br>{e(cap)}</p>')
d.append(f'<p>More photos and notes: <a href="https://nemo99007.github.io/tech-logbook/{conf.id}/">nemo99007.github.io/tech-logbook/{conf.id}/</a></p></div>')
(dst / "email_summary.html").write_text("\n".join(d))
print(dst / "email_summary.html")

B = f"https://nemo99007.github.io/tech-logbook/{conf.id}"
md = [f"# {meta['short_name']} · {meta['location']}", ""]
for t in d[2:5]:
    md += [re.sub(r"<[^>]+>", "", t).replace("&#39;", "'"), ""]
for n in pick:
    if n != LOBBY:
        md += [f"![{ana[n]['title']} ({ana[n]['presenter_or_company']})]({B}/assets/images/{n})", ""]
md.append(f"More photos and notes: {B}/")
(dst / "email_summary.md").write_text("\n".join(md))
print(dst / "email_summary.md")
