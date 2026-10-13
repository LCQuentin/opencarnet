#!/usr/bin/env python3
"""Shared helpers for the OpenCarnet source parsers.

Every platform export (Meta / Instagram, X, TikTok, LinkedIn, YouTube…) is
normalized to the same **pivot** item and written to a normalized CSV + JSON:

    id, url, auteur, handle, date_source, canal, legende, hashtags, collection

`id` = hash of the canonical URL (so the same item shared on two sources
de-duplicates). `canal` = platform (`reel`/`post`, `tweet`, `tiktok`,
`linkedin`, `youtube`). `collection` = save signal (`saved`, `like`,
`bookmark`, `favorite`, `playlist:<name>`).

Nothing platform-specific is hardcoded here beyond URL shapes; parsers call
`make_item` and `write_items`.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

PIVOT_COLS = ["id", "url", "auteur", "handle", "date_source", "canal",
              "legende", "hashtags", "collection"]

# --- URL shapes -------------------------------------------------------------

IG_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)",
    re.I)
X_RE = re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/[^/]+/status/(\d+)", re.I)
X_WEB_RE = re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/i/web/status/(\d+)", re.I)
TT_RE = re.compile(
    r"https?://(?:www\.)?tiktok\.com/@([^/\s?]+)/video/(\d+)|"
    r"https?://(?:www\.|m\.)?tiktokv\.com/(?:share/)?video/(\d+)", re.I)
YT_RE = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/watch\?[^#\s]*?\bv=([A-Za-z0-9_-]{6,})"
    r"|youtu\.be/([A-Za-z0-9_-]{6,})|youtube\.com/shorts/([A-Za-z0-9_-]{6,}))", re.I)
LI_RE = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/([^\s?#]+)", re.I)

_IG_COLLECTIONS = {"saved", "like", "bookmark"}


def first_url(pattern: re.Pattern, text: str) -> str | None:
    m = pattern.search(text or "")
    return m.group(0) if m else None


def canonical_instagram(url: str) -> str:
    m = IG_RE.search(url or "")
    return m.group(0) if m else ""


def canonical_x(url: str) -> str:
    m = X_RE.search(url or "") or X_WEB_RE.search(url or "")
    return f"https://x.com/i/web/status/{m.group(1)}" if m else ""


def canonical_tiktok(url: str) -> str:
    m = TT_RE.search(url or "")
    if not m:
        return ""
    handle = (m.group(1) or "").lstrip("@")
    vid = m.group(2) or m.group(3)
    if handle:
        return f"https://www.tiktok.com/@{handle}/video/{vid}"
    return f"https://www.tiktok.com/video/{vid}"


def canonical_youtube(url: str) -> str:
    m = YT_RE.search(url or "")
    if not m:
        return ""
    vid = next(g for g in m.groups() if g)
    return f"https://www.youtube.com/watch?v={vid}"


def canonical_linkedin(url: str) -> str:
    m = LI_RE.search(url or "")
    return f"https://www.linkedin.com/{m.group(1).rstrip('/')}" if m else ""


def canonical_url(url: str) -> str:
    """Apply every known canonicalizer; fall back to the trimmed URL."""
    for fn in (canonical_instagram, canonical_x, canonical_tiktok, canonical_youtube,
               canonical_linkedin):
        c = fn(url)
        if c:
            return c
    return (url or "").strip()


def canal_from_url(url: str) -> str:
    """Platform tag for the `canal` column, derived from the URL domain."""
    u = (url or "").lower()
    if "instagram.com" in u:
        return "reel" if "/reel" in u else "post"
    if "tiktok.com" in u:
        return "tiktok"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "twitter.com" in u or "x.com" in u:
        return "tweet"
    if "linkedin.com" in u:
        return "linkedin"
    return ""


def pivot_id(url: str) -> str:
    """Stable id = hash of the canonical URL (empty URL → id from fallback)."""
    return hashlib.sha1((canonical_url(url) or url or "").encode()).hexdigest()[:12]


def make_item(url: str = "", *, auteur: str = "", handle: str = "", date_source: str = "",
              canal: str = "", legende: str = "", hashtags: str = "",
              collection: str = "saved", id_key: str | None = None) -> dict:
    """Build one pivot row. `canal` and `id` are derived from the URL when omitted;
    pass `id_key` when there is no usable URL (id from that key instead)."""
    url = (url or "").strip()
    return {
        "id": hashlib.sha1((id_key or canonical_url(url) or url).encode()).hexdigest()[:12],
        "url": url,
        "auteur": auteur or "",
        "handle": handle or "",
        "date_source": date_source or "",
        "canal": canal or canal_from_url(url),
        "legende": legende or "",
        "hashtags": hashtags or "",
        "collection": collection or "saved",
    }


def iso_date(value) -> str:
    """Best-effort ISO `YYYY-MM-DD` from a string/timestamp."""
    import datetime as _dt
    if isinstance(value, (int, float)) and value:
        return _dt.datetime.fromtimestamp(int(value), tz=_dt.timezone.utc).strftime("%Y-%m-%d")
    if isinstance(value, str):
        v = value.strip()
        if v.isdigit() and len(v) >= 9:
            return _dt.datetime.fromtimestamp(int(v), tz=_dt.timezone.utc).strftime("%Y-%m-%d")
        m = re.match(r"\d{4}-\d{2}-\d{2}", v)
        if m:
            return m.group(0)
    return ""


def dedup_items(items: list[dict]) -> list[dict]:
    """Drop duplicates by canonical URL (falling back to id), keeping order."""
    seen, rows = set(), []
    for it in items:
        key = canonical_url(it.get("url", "")) or it.get("id", "")
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(it)
    return rows


def iter_members(root: Path, want):
    """Yield `(name, bytes)` for members matching `want(name)`, reading a .zip
    without extracting it (exports can be several GB of media). A single file is
    yielded as-is."""
    if root.is_file() and root.suffix.lower() == ".zip":
        with zipfile.ZipFile(root) as z:
            for info in z.infolist():
                if not info.is_dir() and want(info.filename):
                    yield info.filename, z.read(info)
    elif root.is_file():
        if want(root.name):
            yield root.name, root.read_bytes()
    elif root.is_dir():
        for f in sorted(root.rglob("*")):
            if f.is_file() and want(str(f)):
                yield str(f), f.read_bytes()


def recap(rows: list[dict], files_seen: int, out: Path) -> None:
    by_collection: dict[str, int] = {}
    for r in rows:
        by_collection[r.get("collection", "")] = by_collection.get(r.get("collection", ""), 0) + 1
    with_url = sum(1 for r in rows if r.get("url"))
    print(f"[ok] {len(rows)} items depuis {files_seen} fichier(s) -> {out}")
    for k, v in sorted(by_collection.items()):
        print(f"     {k}: {v}")
    print(f"     {with_url} avec URL, {len(rows) - with_url} sans URL (à compléter).")
    print(f"     sidecar : {out.with_suffix('.json')}")


def write_items(rows: list[dict], out: Path, files_seen: int = 0) -> int:
    """Write the pivot CSV + JSON sidecar and print the recap. Returns row count."""
    out = Path(out).expanduser()
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=PIVOT_COLS)
        w.writeheader()
        w.writerows(rows)
    out.with_suffix(".json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    recap(rows, files_seen, out)
    return len(rows)


def fail(msg: str) -> int:
    print(f"[!] {msg}", file=sys.stderr)
    return 1
