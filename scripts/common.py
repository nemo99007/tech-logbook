"""Shared helpers: per-conference paths and config loading.

Layout (<conf> = e.g. dac2026):
  raw_photos/<conf>/            input photos (gitignored)
  config/site.yaml              site-wide settings
  config/persona.md             author lens, shared by all conferences
  config/<conf>/conference.yaml name, dates, location, my_work, ...
  config/<conf>/persona.md      optional conference-specific additions
  config/<conf>/manifest.yaml   step 1 output
  config/<conf>/analysis.yaml   step 2 output
  config/<conf>/nav.yaml        step 3 output (merged into mkdocs.yml)
  docs/<conf>/                  generated pages + assets/images
  output/<conf>/                email newsletter
"""
import argparse
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Conf:
    id: str
    raw: Path
    config: Path
    docs: Path
    images: Path
    output: Path
    manifest: Path
    analysis: Path
    nav: Path
    meta: dict

    @property
    def title(self) -> str:
        return self.meta.get("short_name") or self.id.upper()


def site() -> dict:
    return yaml.safe_load((ROOT / "config" / "site.yaml").read_text())


def conference_ids() -> list[str]:
    return sorted(p.parent.name for p in (ROOT / "config").glob("*/conference.yaml"))


def load_conf(conf_id: str) -> Conf:
    cfg = ROOT / "config" / conf_id
    if not (cfg / "conference.yaml").exists():
        raise SystemExit(f"unknown conference '{conf_id}' (no config/{conf_id}/conference.yaml); "
                         f"known: {', '.join(conference_ids()) or 'none'}")
    return Conf(
        id=conf_id,
        raw=ROOT / "raw_photos" / conf_id,
        config=cfg,
        docs=ROOT / "docs" / conf_id,
        images=ROOT / "docs" / conf_id / "assets" / "images",
        output=ROOT / "output" / conf_id,
        manifest=cfg / "manifest.yaml",
        analysis=cfg / "analysis.yaml",
        nav=cfg / "nav.yaml",
        meta=yaml.safe_load((cfg / "conference.yaml").read_text()),
    )


def parse_args(description: str, *extra) -> tuple[argparse.Namespace, Conf]:
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--conf", required=True, help="conference id, e.g. dac2026")
    for flags, kw in extra:
        ap.add_argument(*flags, **kw)
    args = ap.parse_args()
    return args, load_conf(args.conf)
