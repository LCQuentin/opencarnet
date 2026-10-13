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
import os
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

PIVOT_COLS = ["id", "url", "auteur", "handle", "date_source", "canal",
              "legende", "hashtags", "collection"]

_LANG = "en"
_MSG = {
    "en": {
        "not_found": "not found: {path}",
        "ignore_file": "[!] ignoring {path}: {err}",
        "no_playlist": "[i] no playlist CSV found (Takeout: tick \"YouTube and YouTube "
                       "Music\" -> playlists).",
        "no_saved_items": "[i] \"Saved Items.csv\" not found (LinkedIn: tick \"Saved "
                          "Items\" in Download your data).",
        "linkedin_note": "[i] LinkedIn: export = links only -> notes to review (see docstring).",
        "recap_head": "[ok] {n} items from {files} file(s) -> {out}",
        "recap_row": "     {collection}: {count}",
        "recap_urls": "     {with_url} with URL, {without_url} without URL (to complete).",
        "recap_sidecar": "     sidecar: {path}",
    },
    "fr": {
        "not_found": "introuvable : {path}",
        "ignore_file": "[!] fichier ignoré {path} : {err}",
        "no_playlist": "[i] aucun CSV de playlist trouvé (Takeout : cochez « YouTube and "
                       "YouTube Music » -> playlists).",
        "no_saved_items": "[i] « Saved Items.csv » introuvable (LinkedIn : cochez « Saved "
                          "Items » dans Télécharger vos données).",
        "linkedin_note": "[i] LinkedIn : export = liens seuls -> fiches à relire (voir docstring).",
        "recap_head": "[ok] {n} items depuis {files} fichier(s) -> {out}",
        "recap_row": "     {collection}: {count}",
        "recap_urls": "     {with_url} avec URL, {without_url} sans URL (à compléter).",
        "recap_sidecar": "     sidecar : {path}",
    },
}


def set_lang(lang: str | None) -> None:
    global _LANG
    if lang in _MSG:
        _LANG = lang


def _config_lang() -> str | None:
    """Langue lue dans la config, **même ordre que compile.load_config**."""
    candidates = [
        os.environ.get("OPENCARNET_CONFIG", ""),
        os.environ.get("INSTAGRAM_SAVED_CONFIG", ""),  # ancien nom, conservé
        str(Path.home() / ".config" / "opencarnet" / "config.json"),
        str(Path(__file__).resolve().parent.parent / "config.example.json"),
    ]
    for c in candidates:
        if not c:
            continue
        p = Path(c).expanduser()
        if not p.exists():
            continue
        try:
            lang = json.loads(p.read_text(encoding="utf-8")).get("language")
        except (OSError, json.JSONDecodeError):
            continue
        if lang in _MSG:
            return lang
    return None


def default_lang() -> str:
    """Langue par défaut des outils sans config : $OPENCARNET_LANG, sinon la
    langue de la config (comme compile.load_config, y compris
    ~/.config/opencarnet/config.json), sinon la locale système."""
    env = os.environ.get("OPENCARNET_LANG")
    if env in _MSG:
        return env
    lang = _config_lang()
    if lang:
        return lang
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if (os.environ.get(var) or "").lower().startswith("fr"):
            return "fr"
    return "en"


def t(key: str, **kw) -> str:
    text = (_MSG.get(_LANG) or _MSG["en"]).get(key) or _MSG["en"].get(key, key)
    return text.format(**kw) if kw else text

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


def _with_scheme(url: str) -> str:
    """Adds `https://` when a pasted link omits it (manual link lists)."""
    u = (url or "").strip()
    return u if not u or "://" in u else "https://" + u


def canonical_url(url: str) -> str:
    """Apply every known canonicalizer; fall back to the trimmed URL."""
    u = _with_scheme(url)
    for fn in (canonical_instagram, canonical_x, canonical_tiktok, canonical_youtube,
               canonical_linkedin):
        c = fn(u)
        if c:
            return c
    return u


def _host_is(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def canal_from_url(url: str) -> str:
    """Platform tag for the `canal` column, from the URL **host** (not a
    substring: `dropbox.com`/`netflix.com` must not match `x.com`). Tolerates a
    missing scheme (`instagram.com/reel/…`)."""
    u = _with_scheme(url)
    try:
        host = (urlparse(u).hostname or "").lower()
    except ValueError:
        host = ""
    if _host_is(host, "instagram.com"):
        return "reel" if "/reel" in u.lower() else "post"
    if _host_is(host, "tiktok.com"):
        return "tiktok"
    if _host_is(host, "youtube.com") or host == "youtu.be":
        return "youtube"
    if _host_is(host, "x.com") or _host_is(host, "twitter.com"):
        return "tweet"
    if _host_is(host, "linkedin.com"):
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
    """Best-effort ISO `YYYY-MM-DD` from a string or timestamp. Handles Unix
    seconds and **milliseconds** (a 13-digit stamp used to overflow the year
    and crash the whole export)."""
    import datetime as _dt
    ts = None
    if isinstance(value, (int, float)) and value:
        ts = float(value)
    elif isinstance(value, str):
        v = value.strip()
        if v.isdigit() and len(v) >= 9:
            ts = float(v)
        else:
            m = re.match(r"\d{4}-\d{2}-\d{2}", v)
            return m.group(0) if m else ""
    if ts is None:
        return ""
    if ts > 1e12:  # millisecondes
        ts /= 1000.0
    try:
        return _dt.datetime.fromtimestamp(ts, tz=_dt.timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
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
    print(t("recap_head", n=len(rows), files=files_seen, out=out))
    for k, v in sorted(by_collection.items()):
        print(t("recap_row", collection=k, count=v))
    print(t("recap_urls", with_url=with_url, without_url=len(rows) - with_url))
    print(t("recap_sidecar", path=out.with_suffix(".json")))


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
