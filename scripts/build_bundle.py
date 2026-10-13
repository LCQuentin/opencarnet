#!/usr/bin/env python3
"""Assemble les artefacts d'un item en un bundle Markdown prêt à analyser.

Entrée : un dossier de travail produit par fetch_media.sh + transcribe.py :
    <id>.info.json    (yt-dlp : légende, auteur, date, hashtags)
    <id>.txt          (transcript, optionnel)
    <id>_sheet.jpg    (planche de frames, optionnel)
Sortie : bundles/<id>.md

Usage :
    python3 build_bundle.py --work ./work --out ./bundles
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _pivot  # noqa: E402


def load_info(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def fmt_date(info: dict) -> str:
    ts = info.get("timestamp") or info.get("upload_date")
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    if isinstance(ts, str) and len(ts) >= 8:
        return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
    return ""


def build_one(info_path: Path, work: Path, out: Path) -> Path:
    iid = info_path.name[: -len(".info.json")]
    info = load_info(info_path)

    caption = (info.get("description") or "").strip()
    author = info.get("uploader") or ""
    handle = info.get("channel") or info.get("uploader_id") or ""
    url = info.get("webpage_url") or ""
    date = fmt_date(info)
    duration = info.get("duration")
    hashtags = " ".join(info.get("tags") or [])

    transcript = ""
    t = work / f"{iid}.txt"
    if t.exists():
        transcript = t.read_text(encoding="utf-8", errors="replace").strip()

    sheet = work / f"{iid}_sheet.jpg"
    sheet_line = f"![[{sheet.name}]]" if sheet.exists() else "_(pas de frames)_"

    q = json.dumps  # chaîne JSON = scalaire YAML valide (protège « : », « # »…)
    canal = _pivot.canal_from_url(url) or "post"
    md = f"""---
id: {q(iid)}
url: {q(url)}
auteur: {q(author, ensure_ascii=False)}
handle: {q(handle, ensure_ascii=False)}
date_source: {q(date)}
canal: {q(canal)}
duree_s: {duration if duration is not None else ""}
---

# Bundle — {iid}

> Source : {url or "n/a"} — {author or "?"} {('(@' + handle + ')') if handle else ''} — {date or "?"}

## MÉTADONNÉES
- url: {url}
- auteur: {author}
- handle: {('@' + handle) if handle else "—"}
- date: {date}
- durée: {duration if duration is not None else "?"}s
- hashtags: {hashtags or "—"}

## LÉGENDE
{caption or "_(vide)_"}

## TRANSCRIPT (audio)
{transcript or "_(non transcrit — lancer transcribe.py)_"}

## LECTURE ÉCRAN (planche de frames)
{sheet_line}

_La substance technique (noms d'outils, prompts, code, UI) se lit dans la planche
ci-dessus : la lire visuellement avant de produire l'analyse._
"""
    dest = out / f"{iid}.md"
    dest.write_text(md, encoding="utf-8")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    work = Path(args.work).expanduser()
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    infos = sorted(work.glob("*.info.json"))
    if not infos:
        print(f"[!] aucun *.info.json dans {work}")
        return 1
    for p in infos:
        print(f"[ok] {build_one(p, work, out)}")
    print(f"[ok] {len(infos)} bundle(s) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
