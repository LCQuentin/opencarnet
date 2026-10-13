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

MSG = {
    "en": {
        "meta": "## METADATA", "caption": "## CAPTION", "transcript": "## TRANSCRIPT (audio)",
        "screen": "## SCREEN READ (frame sheet)", "bundle": "Bundle — {iid}",
        "no_frames": "_(no frames)_", "empty": "_(empty)_",
        "not_transcribed": "_(not transcribed — run transcribe.py)_",
        "screen_hint": "_The technical substance (tool names, prompts, code, UI) is in the "
                       "sheet above: read it visually before producing the analysis._",
        "source": "Source", "author": "author", "duration": "duration",
        "no_info": "[!] no *.info.json in {work}", "ok": "[ok] {path}",
        "done": "[ok] {n} bundle(s) -> {out}",
    },
    "fr": {
        "meta": "## MÉTADONNÉES", "caption": "## LÉGENDE", "transcript": "## TRANSCRIPT (audio)",
        "screen": "## LECTURE ÉCRAN (planche de frames)", "bundle": "Bundle — {iid}",
        "no_frames": "_(pas de frames)_", "empty": "_(vide)_",
        "not_transcribed": "_(non transcrit — lancer transcribe.py)_",
        "screen_hint": "_La substance technique (noms d'outils, prompts, code, UI) se lit dans "
                       "la planche ci-dessus : la lire visuellement avant de produire l'analyse._",
        "source": "Source", "author": "auteur", "duration": "durée",
        "no_info": "[!] aucun *.info.json dans {work}", "ok": "[ok] {path}",
        "done": "[ok] {n} bundle(s) -> {out}",
    },
}


def M(lang: str, key: str, **kw) -> str:
    text = (MSG.get(lang) or MSG["en"]).get(key) or MSG["en"].get(key, key)
    return text.format(**kw) if kw else text


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


def build_one(info_path: Path, work: Path, out: Path, lang: str = "en") -> Path:
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
    sheet_line = f"![[{sheet.name}]]" if sheet.exists() else M(lang, "no_frames")

    q = json.dumps  # chaîne JSON = scalaire YAML valide (protège « : », « # »…)
    canal = _pivot.canal_from_url(url) or "post"
    md = f"""---
id: {q(iid)}
url: {q(url)}
author: {q(author, ensure_ascii=False)}
handle: {q(handle, ensure_ascii=False)}
date_source: {q(date)}
canal: {q(canal)}
duration_s: {duration if duration is not None else ""}
---

# {M(lang, "bundle", iid=iid)}

> {M(lang, "source")} : {url or "n/a"} — {author or "?"} {('(@' + handle + ')') if handle else ''} — {date or "?"}

{M(lang, "meta")}
- url: {url}
- {M(lang, "author")}: {author}
- handle: {('@' + handle) if handle else "—"}
- date: {date}
- {M(lang, "duration")}: {duration if duration is not None else "?"}s
- hashtags: {hashtags or "—"}

{M(lang, "caption")}
{caption or M(lang, "empty")}

{M(lang, "transcript")}
{transcript or M(lang, "not_transcribed")}

{M(lang, "screen")}
{sheet_line}

{M(lang, "screen_hint")}
"""
    dest = out / f"{iid}.md"
    dest.write_text(md, encoding="utf-8")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--language", choices=("en", "fr"), default=None,
                    help="bundle language (default: config/OPENCARNET_LANG/system locale)")
    args = ap.parse_args()
    lang = args.language or _pivot.default_lang()

    work = Path(args.work).expanduser()
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    infos = sorted(work.glob("*.info.json"))
    if not infos:
        print(M(lang, "no_info", work=work))
        return 1
    for p in infos:
        print(M(lang, "ok", path=build_one(p, work, out, lang)))
    print(M(lang, "done", n=len(infos), out=out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
