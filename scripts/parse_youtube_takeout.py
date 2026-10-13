#!/usr/bin/env python3
"""Parse a Google Takeout export ("YouTube and YouTube Music" → playlists) and
extract the saved videos as a normalized pivot CSV + JSON.

Each playlist is a CSV (`Video ID`, `Playlist video creation timestamp`, …).
The playlist folder/file names are **localized** in Takeout, so files are
recognized by their *structure*: a CSV that has a video-id column **and** a
column mentioning "playlist" (the playlist timestamp). Watch history has a
video-id column but no "playlist" column — it is **not** a save signal and is
skipped (see the privacy rule in the SKILL).

Output: `collection = playlist:<name>`, `canal = youtube`,
`url = https://www.youtube.com/watch?v=<id>`. The archive can be read without
extracting it. A video present in several playlists is kept once (first one).

Usage:
    python3 parse_youtube_takeout.py ~/Downloads/takeout-XXXXXXXX.zip --out items.csv
    python3 parse_youtube_takeout.py ~/Downloads/Takeout/ --out items.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _pivot  # noqa: E402

ID_KEYS = ("video id", "videoid", "video url", "video  id")
PLAYLIST_HINT = "playlist"
DATE_HINT = ("timestamp", "time", "date")
VID_RE = re.compile(r"([A-Za-z0-9_-]{6,})")


def norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(h).lower()).strip()


def video_id_of(row: dict, id_col: str) -> str:
    raw = (row.get(id_col) or "").strip()
    if not raw:
        return ""
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{6,})", raw, re.I)
    if m:
        return m.group(1)
    m = VID_RE.match(raw)
    return m.group(1) if m else ""


def parse_playlist_csv(text: str, name: str) -> list[dict]:
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    if not lines:
        return []
    rows = list(csv.DictReader(io.StringIO("\n".join(lines))))
    if not rows:
        return []
    headers = list(rows[0].keys())
    norm = {h: norm_header(h) for h in headers}
    id_col = next((h for h in headers if any(k in norm[h] for k in ID_KEYS)), None)
    has_playlist_col = any(PLAYLIST_HINT in norm[h] for h in headers)
    if not id_col or not has_playlist_col:
        return []  # watch history, subscriptions… not a playlist
    date_col = next((h for h in headers if any(k in norm[h] for k in DATE_HINT)), None)

    items = []
    for row in rows:
        vid = video_id_of(row, id_col)
        if not vid:
            continue
        date = _pivot.iso_date(row.get(date_col, "")) if date_col else ""
        items.append(_pivot.make_item(
            f"https://www.youtube.com/watch?v={vid}", canal="youtube",
            date_source=date, collection=f"playlist:{name}"))
    return items


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("export", help="dossier Takeout ou .zip")
    ap.add_argument("--out", default="items.csv", help="CSV de sortie")
    ap.add_argument("--language", choices=("en", "fr"), default=None,
                    help="messages (en | fr; default: config/OPENCARNET_LANG/system locale)")
    args = ap.parse_args()
    _pivot.set_lang(args.language or _pivot.default_lang())

    root = Path(args.export).expanduser()
    if not root.exists():
        return _pivot.fail(_pivot.t("not_found", path=root))

    all_items, files_seen = [], 0
    for name, data in _pivot.iter_members(root, lambda n: n.lower().endswith(".csv")):
        text = data.decode("utf-8-sig", errors="replace")
        found = parse_playlist_csv(text, Path(name).stem)
        if found:
            files_seen += 1
            all_items += found

    rows = _pivot.dedup_items(all_items)
    if files_seen == 0:
        print(_pivot.t("no_playlist"), file=sys.stderr)
    _pivot.write_items(rows, Path(args.out), files_seen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
