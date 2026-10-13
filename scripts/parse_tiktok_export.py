#!/usr/bin/env python3
"""Parse a TikTok data export ("Download your data", JSON) and extract the
saved signals as a normalized pivot CSV + JSON — same shape as the Instagram
and X parsers.

Kept by default: **Favorite Videos** (`collection: favorite`).
Your **likes** (`Like List`) are a weak, high-volume signal: included only with
`--include-likes` (`collection: like`). Everything else (watch history,
searches, comments, shares…) is ignored — see the privacy rule in the SKILL.

TikTok's export key names change between versions (case, spacing, nesting), so
the parser walks the JSON tolerantly and looks for *sections whose name contains
"favorite" or "like"*, then for the video links inside them. Share links
(`tiktokv.com/...`) are rewritten to the canonical `tiktok.com/@user/video/<id>`
before de-duplication.

Usage:
    python3 parse_tiktok_export.py ~/Downloads/tiktok-data.zip --out items.csv
    python3 parse_tiktok_export.py ~/Downloads/tiktok-data/ --out items.csv [--include-likes]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _pivot  # noqa: E402

TT_URL_TEXT = re.compile(r"https?://[^\s\"'<>]*tiktok(?:v)?\.com/[^\s\"'<>]+", re.I)
DATE_KEYS = {"date", "timestamp", "savetime", "savedate", "time"}


def norm_key(k: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(k).lower())


def first_tt_url(value) -> str:
    if isinstance(value, str):
        m = TT_URL_TEXT.search(value)
        return _pivot.canonical_tiktok(m.group(0)) if m else ""
    return ""


def find_sections(node):
    """Yield `(collection, subtree)` for every section named favorite/like.
    A matched section is not searched further (its subtree is captured whole);
    this avoids mislabelling an inner list (e.g. `ItemFavoriteList` inside the
    like section) as another collection."""
    if isinstance(node, dict):
        for k, v in node.items():
            kl = norm_key(k)
            if "favorite" in kl:
                yield "favorite", v
            elif "like" in kl and "dislike" not in kl and "unlike" not in kl:
                yield "like", v
            else:
                yield from find_sections(v)
    elif isinstance(node, list):
        for v in node:
            yield from find_sections(v)


def extract_entries(node):
    """Yield `(url, date)` for every dict holding a TikTok link."""
    if isinstance(node, dict):
        url = ""
        date = ""
        for k, v in node.items():
            if not url:
                url = first_tt_url(v)
            if not date and norm_key(k) in DATE_KEYS and isinstance(v, str):
                date = _pivot.iso_date(v)
        if url:
            yield url, date
        for v in node.values():
            yield from extract_entries(v)
    elif isinstance(node, list):
        for v in node:
            yield from extract_entries(v)


def parse_document(data, include_likes: bool) -> list[dict]:
    items = []
    for collection, subtree in find_sections(data):
        if collection == "like" and not include_likes:
            continue
        for url, date in extract_entries(subtree):
            if url:
                items.append(_pivot.make_item(
                    url, canal="tiktok", date_source=date, collection=collection))
    return items


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("export", help="dossier, .json ou .zip de l'export TikTok")
    ap.add_argument("--out", default="items.csv", help="CSV de sortie")
    ap.add_argument("--include-likes", action="store_true",
                    help="inclure aussi vos « J'aime » (signal faible, volume élevé)")
    args = ap.parse_args()

    root = Path(args.export).expanduser()
    if not root.exists():
        return _pivot.fail(f"introuvable : {root}")

    all_items, files_seen = [], 0
    for name, data in _pivot.iter_members(root, lambda n: n.lower().endswith(".json")):
        try:
            payload = json.loads(data.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        found = parse_document(payload, args.include_likes)
        if found:
            files_seen += 1
            all_items += found

    rows = _pivot.dedup_items(all_items)
    _pivot.write_items(rows, Path(args.out), files_seen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
