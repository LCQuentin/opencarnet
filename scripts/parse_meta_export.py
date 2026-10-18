#!/usr/bin/env python3
"""Parse un export de données Instagram (Meta) et extrait la liste des posts
sauvegardés ("Saved") vers un CSV normalisé + un sidecar JSON (légendes).

Gère trois formats d'export :
  - moderne : liste d'items `{timestamp, fbid, label_values:[{label,value} | {title,dict}]}`
  - legacy  : `{saved_saved_media:[{title, string_map_data:{...}}]}`
  - HTML    : extraction des liens instagram

Usage :
    python3 parse_meta_export.py "~/Downloads/instagram-xxx/" --out items.csv
    python3 parse_meta_export.py export.zip --out items.csv

Sortie :
  items.csv   : id,url,auteur,handle,date_source,canal,legende,hashtags,collection
  items.json  : même items avec la légende complète (pour build_bundle)

Les items sans permalien gardent une colonne `url` vide : ils sont comptés
« à compléter » et compile.py les enverra dans l'inbox.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _pivot  # noqa: E402

IG_URL_RE = _pivot.IG_RE

LABEL_URL = {"url", "lien", "link"}
LABEL_CAPTION = {"légende", "legende", "caption", "texte"}
LABEL_TITLE = {"titre", "title"}


def fix_mojibake(s: str) -> str:
    """Corrige le double-encodage fréquent des exports Meta (`LÃ©gende`)."""
    if not isinstance(s, str):
        return s
    for enc in ("latin1", "cp1252"):
        try:
            return s.encode(enc).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return s


def first_ig_url(value: str) -> str | None:
    m = IG_URL_RE.search(value or "")
    return m.group(0) if m else None


def walk_json(node, path="root"):
    if isinstance(node, dict):
        yield path, node
        for k, v in node.items():
            yield from walk_json(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_json(v, f"{path}[{i}]")


def parse_modern_item(it: dict) -> dict | None:
    url, captions, title = "", [], ""
    auteur, handle, hashtags = "", "", ""
    for lv in it.get("label_values", []):
        if not isinstance(lv, dict):
            continue
        if "label" in lv:
            lbl = fix_mojibake(str(lv.get("label", ""))).strip().lower()
            val = fix_mojibake(str(lv.get("value", "")))
            if lbl in LABEL_URL and not url:
                url = first_ig_url(val) or val
            elif lbl in LABEL_CAPTION and val.strip():
                captions.append(val.strip())
            elif lbl in LABEL_TITLE and not title and val.strip():
                title = val.strip()
        elif "title" in lv:
            t = fix_mojibake(str(lv["title"])).strip().lower()
            if t in ("propriétaire", "proprietaire", "owner"):
                for block in lv.get("dict", []):
                    for x in block.get("dict", []):
                        lab = fix_mojibake(str(x.get("label", ""))).strip().lower()
                        v = fix_mojibake(str(x.get("value", "")))
                        if lab in ("nom", "name") and not auteur:
                            auteur = v
                        elif lab in ("nom de profil", "username", "handle"):
                            handle = v.lstrip("@")
                        elif lab in ("url", "lien") and not url:
                            url = first_ig_url(v) or v
            elif t == "hashtags":
                hs = []
                for block in lv.get("dict", []):
                    if isinstance(block, dict) and block.get("value"):
                        hs.append(fix_mojibake(str(block["value"])))
                    for x in block.get("dict", []) if isinstance(block, dict) else []:
                        if x.get("value"):
                            hs.append(fix_mojibake(str(x["value"])))
                hashtags = " ".join(hs)

    if not url and not auteur:
        return None
    caption = "\n".join(dict.fromkeys(captions))  # dédup en gardant l'ordre
    # id stable : fbid > url > auteur|timestamp (comme avant l'extraction du pivot)
    id_key = it.get("fbid") or (None if url else f"{auteur}|{it.get('timestamp')}")
    return _pivot.make_item(
        url, auteur=auteur or title, handle=handle,
        date_source=_pivot.iso_date(it.get("timestamp")),
        canal="reel" if "/reel" in url else "post",
        legende=caption, hashtags=hashtags, collection="saved",
        id_key=str(id_key) if id_key else None,
    )


def parse_legacy(data) -> list[dict]:
    items = []
    for path, node in walk_json(data):
        keys = {k.lower() for k in node}
        if not ({"string_map_data", "title"} & keys):
            continue
        blob = json.dumps(node, ensure_ascii=False)
        url = first_ig_url(blob) or ""
        smd = node.get("string_map_data") or {}
        # export actuel : `title` = nom de profil de l'auteur
        author = str(node.get("title") or "") if isinstance(node.get("title"), str) else ""
        saved_on = ""
        if isinstance(smd, dict):
            for k, v in smd.items():
                if isinstance(v, dict):
                    if v.get("timestamp") and not saved_on:
                        saved_on = str(v["timestamp"])
                    if not url and v.get("href"):
                        url = first_ig_url(v["href"]) or ""
                kl = k.lower()
                if ("owner" in kl or "username" in kl) and not author:
                    author = str(v.get("value", v.get("title", "")) if isinstance(v, dict) else v)
        if not url and not author:
            continue
        items.append(_pivot.make_item(
            url, auteur=author, handle=author, date_source=_pivot.iso_date(saved_on),
            canal="reel" if "/reel" in url else "post", collection=
            re.sub(r"\[.*", "", path.split(".")[1]) if "." in path else "saved",
            id_key=None if url else f"{author}|{saved_on}",
        ))
    return items


def parse_html(text: str) -> list[dict]:
    items, seen = [], set()
    for m in IG_URL_RE.finditer(html.unescape(text)):
        url = m.group(0)
        if url in seen:
            continue
        seen.add(url)
        items.append(_pivot.make_item(url, collection="saved"))
    return items


def extract_from_json(data) -> list[dict]:
    # moderne : liste d'items avec label_values
    candidates = data if isinstance(data, list) else data.get("saved_saved_media")
    if isinstance(candidates, list):
        modern = [parse_modern_item(it) for it in candidates if isinstance(it, dict) and "label_values" in it]
        modern = [m for m in modern if m]
        if modern:
            return modern
    return parse_legacy(data)


def is_target(name: str) -> bool:
    n = Path(name).name.lower()
    return ("saved" in n or "sauveg" in n) and Path(n).suffix in (".json", ".html", ".htm")


def iter_sources(root: Path):
    """(nom, texte) des fichiers « saved » — lus directement dans le .zip, sans
    extraire l'export complet (souvent plusieurs Go de médias)."""
    if root.is_file() and root.suffix.lower() == ".json":
        yield root.name, root.read_text(encoding="utf-8", errors="replace")
    else:
        for name, data in _pivot.iter_members(root, lambda n: is_target(n)):
            yield name, data.decode("utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("export", help="dossier, fichier .json, ou .zip de l'export Meta")
    ap.add_argument("--out", default="items.csv", help="CSV de sortie")
    ap.add_argument("--language", choices=("en", "fr"), default=None,
                    help="messages (en | fr; default: config/OPENCARNET_LANG/system locale)")
    args = ap.parse_args()
    _pivot.set_lang(args.language or _pivot.default_lang())

    root = Path(args.export).expanduser()
    if not root.exists():
        return _pivot.fail(_pivot.t("not_found", path=root))

    all_items, files_seen = [], 0
    for name, text in iter_sources(root):
        files_seen += 1
        try:
            if name.lower().endswith(".json"):
                all_items += extract_from_json(json.loads(text))
            else:
                all_items += parse_html(text)
        except Exception as exc:  # noqa: BLE001
            print(_pivot.t("ignore_file", path=name, err=exc), file=sys.stderr)

    rows = _pivot.dedup_items(all_items)
    out = Path(args.out).expanduser()
    _pivot.write_items(rows, out, files_seen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
