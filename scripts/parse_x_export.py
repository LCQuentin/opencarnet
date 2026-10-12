#!/usr/bin/env python3
"""Parse an X / Twitter data archive and extract liked / bookmarked tweets into
a normalized CSV + JSON, with the SAME shape as parse_meta_export.py.

Usage:
    python3 parse_x_export.py ~/Downloads/twitter-YYYY-MM-DD.zip --out items.csv
    python3 parse_x_export.py ~/Downloads/twitter-archive/ --out items.csv

X archives the data as small JavaScript files in a `data/` folder, of the form:

    window.YTD.like.part0 = [ { "like": { "tweetId": "...", "fullText": "...",
        "expandedUrl": "https://twitter.com/i/web/status/..." } }, ... ]

Recognised kinds: `like`/`likes` (your likes), `bookmark`/`bookmarks`
(your bookmarks, if present), `tweet`/`tweets` (your own posts).

Output columns:
    id,url,auteur,handle,date_source,canal,legende,hashtags,collection
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

YTD_PREFIX = re.compile(r"window\.YTD\.([A-Za-z0-9_]+)\.part\d+\s*=\s*", re.I)
TWEET_DATE = "%a %b %d %H:%M:%S %z %Y"


def canonical_url(tweet_id: str) -> str:
    return f"https://x.com/i/web/status/{tweet_id}" if tweet_id else ""


def iso_date(raw: str) -> str:
    if not raw:
        return ""
    raw = raw.strip()
    for fmt in (TWEET_DATE, "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(raw, fmt).astimezone(timezone.utc).strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.match(r"\d{4}-\d{2}-\d{2}", raw)
    return m.group(0) if m else ""


def unwrap_ytd(text: str):
    """Return (kind, json_array) from a `window.YTD.<kind>.partN = [...]` file."""
    m = YTD_PREFIX.search(text)
    if not m:
        return None, None
    kind = m.group(1).lower()
    payload = text[m.end():].strip().rstrip(";").strip()
    try:
        return kind, json.loads(payload)
    except json.JSONDecodeError:
        return kind, None


def pick_kind(kind: str) -> str:
    if kind.startswith("like"):
        return "like"
    if kind.startswith("bookmark"):
        return "bookmark"
    if kind.startswith("tweet"):
        return "tweet"
    return kind


def extract_items(kind: str, arr) -> list[dict]:
    items = []
    for entry in arr or []:
        if not isinstance(entry, dict):
            continue
        node = next(iter(entry.values())) if len(entry) == 1 and isinstance(next(iter(entry.values())), dict) else entry
        tid = str(node.get("tweetId") or node.get("id") or node.get("id_str") or "")
        text = node.get("fullText") or node.get("full_text") or node.get("text") or ""
        url = node.get("expandedUrl") or node.get("url") or canonical_url(tid)
        date = iso_date(node.get("createdAt") or node.get("created_at") or "")
        handle = node.get("screenName") or (node.get("user") or {}).get("screen_name") or ""
        hashtags = " ".join(re.findall(r"#\w+", text))
        if not (tid or url or text):
            continue
        key = tid or url or hashlib.sha1(text.encode()).hexdigest()
        items.append({
            "id": hashlib.sha1(str(key).encode()).hexdigest()[:12],
            "url": canonical_url(tid) if tid else url,
            "auteur": "",
            "handle": handle,
            "date_source": date,
            "canal": "tweet",
            "legende": text,
            "hashtags": hashtags,
            "collection": pick_kind(kind),
        })
    return items


def collect_js(path: Path):
    if path.is_file() and path.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="x_export_"))
        with zipfile.ZipFile(path) as z:
            z.extractall(tmp)
        return tmp.rglob("*.js")
    return path.rglob("*.js")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("export", help="dossier décompressé ou .zip de l'archive X")
    ap.add_argument("--out", default="items.csv", help="CSV de sortie")
    args = ap.parse_args()

    root = Path(args.export).expanduser()
    if not root.exists():
        print(f"[!] introuvable : {root}", file=sys.stderr)
        return 1

    all_items, files_seen = [], 0
    for f in collect_js(root):
        try:
            head = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "window.YTD." not in head:
            continue
        kind, arr = unwrap_ytd(head)
        if arr is None:
            continue
        files_seen += 1
        all_items += extract_items(kind, arr)

    seen, rows = set(), []
    for it in all_items:
        k = it["url"] or it["id"]
        if k in seen:
            continue
        seen.add(k)
        rows.append(it)

    out = Path(args.out).expanduser()
    cols = ["id", "url", "auteur", "handle", "date_source", "canal", "legende", "hashtags", "collection"]
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    out.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    by_kind = {}
    for r in rows:
        by_kind[r["collection"]] = by_kind.get(r["collection"], 0) + 1
    print(f"[ok] {len(rows)} items depuis {files_seen} fichier(s) X -> {out}")
    for k, v in sorted(by_kind.items()):
        print(f"     {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
