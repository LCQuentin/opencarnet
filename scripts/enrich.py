"""Enrichissements déterministes des données d'un format (jamais inventés par l'IA).

Déclarés dans la config, par format :
    "enrich": [
      {"sum": "temps_total", "of": ["temps_preparation", "temps_cuisson"]},
      {"maps_link": "google_maps", "query": ["nom_lieu", "adresse", "ville", "pays"],
       "require_any": ["nom_lieu", "adresse"]},
      {"geocode": "coordonnees", "query": ["nom_lieu", "adresse", "ville", "pays"],
       "fallback": ["adresse", "ville", "pays"], "fallback_require": ["adresse"],
       "require": ["ville"], "match": "ville", "min_precision": "adresse",
       "precision": "precision_gps"},
      {"domain": "domaine", "from": "url"},
      {"stamp": "prix_constate_le", "if": "prix"}
    ]

Le géocodage utilise Nominatim (OpenStreetMap) : désactivé par défaut, activé par
`geocoding.enabled` ; 1 requête/s max, User-Agent obligatoire, cache disque.
"""
from __future__ import annotations

import json
import re
import unicodedata
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = Path.home() / ".cache" / "opencarnet" / "geocode.json"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
_last_call = [0.0]

def to_minutes(v):
    """45 / "45" / "45 min" / "1 h 15" / "1h15" -> int ; sinon None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(round(v))
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.strip().lower()
    if re.fullmatch(r"\d+(?:[.,]\d+)?", s):
        return int(round(float(s.replace(",", "."))))
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*h(?:eures?|ours?|rs?)?\s*(\d+)?\s*(?:min\w*|mn)?", s)
    if m:
        return int(round(float(m.group(1).replace(",", ".")) * 60 + int(m.group(2) or 0)))
    m = re.fullmatch(r"(\d+)\s*(?:min\w*|mn|m)", s)
    if m:
        return int(m.group(1))
    return None


def to_number(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        m = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*", v)
        if m:
            f = float(m.group(1).replace(",", "."))
            return int(f) if f.is_integer() else f
    return None


def normalize(data: dict, fields: dict) -> dict:
    """Convertit les champs typés `minutes` / `number` ; garde le texte d'origine
    sous `<champ>_texte` si la conversion échoue (affichable dans le corps)."""
    out = dict(data)
    for k, spec in (fields or {}).items():
        t = (spec or {}).get("type") if isinstance(spec, dict) else None
        if k not in out or t not in ("minutes", "number"):
            continue
        conv = to_minutes(out[k]) if t == "minutes" else to_number(out[k])
        if conv is None and out[k] not in (None, ""):
            out[f"{k}_texte"] = out[k]
        out[k] = conv
    return out


def join_query(data: dict, keys: list) -> str:
    parts = []
    for k in keys or []:
        v = data.get(k)
        if v not in (None, "", []) and str(v) not in parts:
            parts.append(str(v))
    return ", ".join(parts)


def _load_cache() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_cache(cache: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


def _get(url: str, ua: str) -> str:
    """GET HTTPS ; certificats via certifi si présent, sinon système, sinon curl
    (certains Python macOS n'ont pas accès aux certificats racine)."""
    try:
        import certifi  # type: ignore
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            return r.read().decode("utf-8")
    except urllib.error.URLError as exc:
        if not isinstance(getattr(exc, "reason", None), ssl.SSLError):
            raise
    out = subprocess.run(["curl", "-fsS", "--max-time", "15", "-A", ua, url],
                         capture_output=True, text=True, check=True)
    return out.stdout


PRECISION_RANK = {"approximative": 0, "ville": 1, "adresse": 2}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def geocode(query: str, geo_cfg: dict, offline: bool):
    """-> (lat, lon, précision, libellé) ou None. Précision : adresse | ville | approximative."""
    cache = _load_cache()
    if query in cache and (cache[query] is None or len(cache[query]) == 4):
        return tuple(cache[query]) if cache[query] else None
    if offline or not geo_cfg.get("enabled"):
        return None
    ua = geo_cfg.get("user_agent")
    if not ua:
        print("[!] géocodage ignoré : geocoding.user_agent manquant (exigé par Nominatim)", file=sys.stderr)
        return None
    wait = 1.1 - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    url = NOMINATIM + "?" + urllib.parse.urlencode({"q": query, "format": "jsonv2", "limit": 1})
    try:
        res = json.loads(_get(url, ua))
    except Exception as exc:  # noqa: BLE001  (réseau : on n'invente rien, on passe)
        print(f"[!] géocodage en échec pour « {query} » : {exc}", file=sys.stderr)
        return None
    finally:
        _last_call[0] = time.monotonic()
    out = None
    if res:
        rank = int(res[0].get("place_rank") or 0)
        prec = "adresse" if rank >= 26 else "ville" if rank >= 16 else "approximative"
        out = (round(float(res[0]["lat"]), 6), round(float(res[0]["lon"]), 6), prec,
               res[0].get("display_name", ""))
    cache[query] = list(out) if out else None
    _save_cache(cache)
    return out


def apply(data: dict, rules: list, geo_cfg: dict, offline: bool) -> dict:
    out = dict(data)
    for r in rules or []:
        if r.get("require_any") and all(out.get(k) in (None, "", []) for k in r["require_any"]):
            continue  # ex. pas de lien Maps sans nom ni adresse (sinon il pointe sur la ville)
        if "sum" in r:
            vals = [out.get(k) for k in r.get("of", [])]
            nums = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if out.get(r["sum"]) in (None, "") and nums:
                out[r["sum"]] = sum(nums)
        elif "maps_link" in r:
            q = join_query(out, r.get("query"))
            if q and not out.get(r["maps_link"]):
                out[r["maps_link"]] = ("https://www.google.com/maps/search/?api=1&query="
                                       + urllib.parse.quote_plus(q))
        elif "geocode" in r:
            # Une coordonnée fausse est pire qu'une absente : on n'accepte qu'un résultat
            # assez précis (min_precision) et situé dans la bonne ville (match).
            if any(out.get(k) in (None, "") for k in r.get("require", [])):
                continue
            hit = None
            attempts = [r.get("query")]
            if all(out.get(k) not in (None, "") for k in r.get("fallback_require", [])):
                attempts.append(r.get("fallback"))
            min_rank = PRECISION_RANK.get(r.get("min_precision", "approximative"), 0)
            for keys in attempts:
                q = join_query(out, keys)
                cand = geocode(q, geo_cfg, offline) if q else None
                if not cand or PRECISION_RANK.get(cand[2], 0) < min_rank:
                    continue
                if r.get("match") and _fold(out.get(r["match"], "")) not in _fold(cand[3]):
                    continue
                hit = cand
                break
            if hit:
                out[r["geocode"]] = [hit[0], hit[1]]
                if r.get("precision"):
                    out[r["precision"]] = hit[2]
        elif "domain" in r:
            u = str(out.get(r.get("from", "url")) or "")
            host = urllib.parse.urlparse(u if "://" in u else "https://" + u).hostname if u else None
            if host:
                out[r["domain"]] = host.removeprefix("www.")
        elif "stamp" in r:
            if out.get(r.get("if")) not in (None, "", []) and not out.get(r["stamp"]):
                out[r["stamp"]] = out.get("_today", "")
    return out


def target_types(rules: list) -> dict:
    """Type des champs calculés (pour le rendu du frontmatter)."""
    out = {}
    for r in rules or []:
        if "sum" in r:
            out[r["sum"]] = "number"
        if "geocode" in r:
            out[r["geocode"]] = "coords"
        for k in ("maps_link", "domain", "stamp", "precision"):
            if r.get(k):
                out[r[k]] = "text"
    return out


def targets(rules: list) -> set:
    """Champs calculés par le moteur (à exclure du prompt)."""
    keys = ("sum", "maps_link", "geocode", "domain", "stamp")
    out = set()
    for r in rules or []:
        for k in keys:
            if k in r:
                out.add(r[k])
        if r.get("precision"):
            out.add(r["precision"])
    return out
