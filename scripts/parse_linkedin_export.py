#!/usr/bin/env python3
"""Parse a LinkedIn data archive and extract your saved items as a normalized
pivot CSV + JSON.

The archive contains **`Saved Items.csv`**: a URL and a save date, with **no
text, author or title** (confirmed by LinkedIn's export).

DECISION (PRD §4.2) — LinkedIn items are imported as a **list of links to
review**. Because the export carries no content and authenticated scraping is
out of scope, these items have no caption; the analyzer will (correctly) mark
them low-confidence and `compile.py` will send them to the configured
`review_dir` (inbox). This is deliberate: OpenCarnet never files a note from a
bare link. Fetching public post previews (og:title/description) without login is
a documented future option, not implemented here.

Usage:
    python3 parse_linkedin_export.py ~/Downloads/linkedin-archive.zip --out items.csv
    python3 parse_linkedin_export.py ~/Downloads/linkedin/ --out items.csv
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

URL_HINTS = ("url", "link", "lien")
DATE_HINTS = ("date", "saved", "time", "added")


def norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(h).lower()).strip()


def is_saved_items(name: str) -> bool:
    return name.lower().endswith(".csv") and "saved" in Path(name).stem.lower()


def parse_saved_csv(text: str) -> list[dict]:
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    if not lines:
        return []
    rows = list(csv.DictReader(io.StringIO("\n".join(lines))))
    if not rows:
        return []
    headers = list(rows[0].keys())
    norm = {h: norm_header(h) for h in headers}
    url_col = next((h for h in headers if any(k in norm[h] for k in URL_HINTS)), headers[0])
    date_col = next((h for h in headers if any(k in norm[h] for k in DATE_HINTS)), None)

    items = []
    for row in rows:
        url = (row.get(url_col) or "").strip()
        if not url.lower().startswith("http"):
            continue
        items.append(_pivot.make_item(
            url, canal="linkedin", collection="saved",
            date_source=_pivot.iso_date(row.get(date_col, "")) if date_col else ""))
    return items


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("export", help="dossier LinkedIn ou .zip de l'archive")
    ap.add_argument("--out", default="items.csv", help="CSV de sortie")
    args = ap.parse_args()

    root = Path(args.export).expanduser()
    if not root.exists():
        return _pivot.fail(f"introuvable : {root}")

    all_items, files_seen = [], 0
    for name, data in _pivot.iter_members(root, lambda n: is_saved_items(n)):
        files_seen += 1
        all_items += parse_saved_csv(data.decode("utf-8-sig", errors="replace"))

    rows = _pivot.dedup_items(all_items)
    if files_seen == 0:
        print("[i] « Saved Items.csv » introuvable (LinkedIn : cochez « Saved "
              "Items » dans Télécharger vos données).", file=sys.stderr)
    print("[i] LinkedIn : export = liens seuls → fiches à relire (voir docstring).")
    _pivot.write_items(rows, Path(args.out), files_seen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
