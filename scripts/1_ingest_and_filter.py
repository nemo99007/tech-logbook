#!/usr/bin/env python3
"""Step 1: ingest raw photos -> manifest.yaml + privacy-scrubbed web images.

- Photos only (jpg/png/heic); videos are ignored.
- Time: EXIF DateTimeOriginal -> filename YYYYMMDD_HHMMSS -> file mtime.
- Faces (OpenCV Haar) are Gaussian-blurred, plus the badge area below small faces.
  A large face (portrait) marks the photo kind=skip.
- Output is re-encoded without EXIF (no GPS) into docs/<conf>/assets/images/.

Usage: 1_ingest_and_filter.py --conf dac2026
Re-running keeps manual edits to `kind` / `include` / `blur` in the manifest.
`blur: none` disables the automatic blur; `blur: [[x0,y0,x1,y1], ...]` (fractions
0..1 of the image) blurs those boxes instead of the detected faces.
`crop: [x0,y0,x1,y1]` (fractions) keeps only that region (e.g. the poster) and
skips blurring.
`--only a.jpg b.jpg` reprocesses just those files.
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
import yaml
from PIL import Image, ImageOps

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

from common import parse_args

EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
CLUSTER_GAP = timedelta(minutes=30)
MAX_SIDE = 2000
PORTRAIT_FACE_RATIO = 0.08  # face area / image area above this -> skip as portrait
NAME_RE = re.compile(r"(\d{8})[_-](\d{6})")


def photo_time(path: Path, img: Image.Image) -> tuple[datetime, str]:
    try:
        raw = img.getexif().get_ifd(0x8769).get(0x9003) or img.getexif().get(0x0132)
        if raw:
            return datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S"), "exif"
    except Exception:
        pass
    m = NAME_RE.search(path.stem)
    if m:
        try:
            return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S"), "filename"
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime), "mtime"


def detect_faces(bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
    gray = cv2.equalizeHist(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
    h, w = gray.shape
    scale = 1000 / max(h, w)
    small = cv2.resize(gray, None, fx=scale, fy=scale) if scale < 1 else gray
    s = scale if scale < 1 else 1.0
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    found = cascade.detectMultiScale(small, scaleFactor=1.1, minNeighbors=6, minSize=(24, 24))
    return [(int(x / s), int(y / s), int(fw / s), int(fh / s)) for x, y, fw, fh in found]


def blur_region(bgr: np.ndarray, x: int, y: int, w: int, h: int) -> None:
    H, W = bgr.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0:
        return
    roi = bgr[y0:y1, x0:x1]
    k = max(15, (min(roi.shape[:2]) // 2) | 1)
    bgr[y0:y1, x0:x1] = cv2.GaussianBlur(roi, (k, k), 0)


def scrub(bgr: np.ndarray, faces) -> np.ndarray:
    for x, y, w, h in faces:
        pad = int(w * 0.25)
        blur_region(bgr, x - pad, y - pad, w + 2 * pad, h + 2 * pad)
        blur_region(bgr, x - w // 2, y + h + pad, 2 * w, int(1.6 * h))  # name badge area
    return bgr


def main() -> int:
    args, conf = parse_args("Ingest, scrub and cluster photos.",
                            (["--only"], {"nargs": "+", "help": "reprocess only these files"}))
    RAW, OUT, MANIFEST = conf.raw, conf.images, conf.manifest
    if not RAW.is_dir():
        print(f"missing {RAW}", file=sys.stderr)
        return 1
    files = sorted(p for p in RAW.iterdir() if p.suffix.lower() in EXTS)
    skipped = [p.name for p in RAW.iterdir() if p.is_file() and p.suffix.lower() not in EXTS]
    if skipped:
        print(f"ignored {len(skipped)} non-photo files (e.g. {skipped[0]})")

    prev = {}
    if MANIFEST.exists():
        prev = {i["file"]: i for i in (yaml.safe_load(MANIFEST.read_text()) or {}).get("photos", [])}

    OUT.mkdir(parents=True, exist_ok=True)
    items = []
    for p in files:
        if args.only and p.name not in args.only and p.name in prev:
            items.append({k: v for k, v in prev[p.name].items() if k != "cluster"})
            continue
        img = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
        taken, src = photo_time(p, img)
        old = prev.get(p.name, {})
        if old.get("crop"):
            x0, y0, x1, y1 = old["crop"]
            w0, h0 = img.size
            img = img.crop((int(x0 * w0), int(y0 * h0), int(x1 * w0), int(y1 * h0)))
        bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        faces = detect_faces(bgr)
        H, W = bgr.shape[:2]
        biggest = max((w * h for _, _, w, h in faces), default=0) / (W * H)
        if biggest > PORTRAIT_FACE_RATIO:
            kind = "skip"
        elif faces:
            kind = "scene"
        else:
            kind = "tech"
        mode = "none" if old.get("crop") else old.get("blur", "auto")
        if mode == "auto":
            bgr = scrub(bgr, faces)
        elif mode != "none":
            for x0, y0, x1, y1 in mode:
                blur_region(bgr, int(x0 * W), int(y0 * H), int((x1 - x0) * W), int((y1 - y0) * H))
        out_img = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        out_img.thumbnail((MAX_SIDE, MAX_SIDE))
        out_name = p.stem + ".jpg"
        out_img.save(OUT / out_name, "JPEG", quality=85, optimize=True)  # no exif passed -> stripped
        items.append({
            "file": p.name,
            "out": f"assets/images/{out_name}",
            "taken": taken.isoformat(),
            "time_source": src,
            "faces": len(faces),
            "kind": old.get("kind", kind),
            "include": old.get("include", kind != "skip"),
            **{k: old[k] for k in ("blur", "crop", "note") if k in old},
        })
        print(f"{p.name}: {taken:%m-%d %H:%M} ({src}) faces={len(faces)} kind={items[-1]['kind']}")

    items.sort(key=lambda i: i["taken"])
    cluster, last = 0, None
    for i in items:
        t = datetime.fromisoformat(i["taken"])
        if last and t - last > CLUSTER_GAP:
            cluster += 1
        i["cluster"] = cluster
        last = t

    MANIFEST.parent.mkdir(exist_ok=True)
    MANIFEST.write_text(yaml.safe_dump({"photos": items}, allow_unicode=True, sort_keys=False))
    print(f"wrote {MANIFEST} ({len(items)} photos, {cluster + 1 if items else 0} clusters)")
    print("Review kinds (tech | scene | skip) and `include` in the manifest before step 2.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
