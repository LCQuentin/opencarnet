#!/usr/bin/env python3
"""Moteur de compilation (neutre) : transforme une analyse d'item Instagram
en fiches, selon un fichier de configuration JSON.

AUCUN chemin n'est codé en dur : racine, dossiers, thèmes, routage, frontmatter
et index (MOC) proviennent de la config. C'est ce qui permet le même moteur pour
un vault perso, un Notion/CSV, ou un usage générique.

Usage :
    python3 compile.py --analysis analyses/x.json [--config config.json] [--dry-run]

Résolution de la config (par ordre) :
    1. --config
    2. $OPENCARNET_CONFIG (ou l'ancien $INSTAGRAM_SAVED_CONFIG)
    3. ~/.config/opencarnet/config.json
    4. <skill>/config.example.json

Codes de sortie : 0 = ok, 1 = erreur, 2 = rien à faire.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_CANDIDATES = [
    os.environ.get("OPENCARNET_CONFIG", ""),
    os.environ.get("INSTAGRAM_SAVED_CONFIG", ""),  # ancien nom, conservé
    str(Path.home() / ".config" / "opencarnet" / "config.json"),
    str(SKILL_DIR / "config.example.json"),
]


def load_config(path: str | None) -> dict:
    for c in ([path] if path else DEFAULT_CONFIG_CANDIDATES):
        if c and Path(c).expanduser().exists():
            cfg = json.loads(Path(c).expanduser().read_text(encoding="utf-8"))
            cfg["_path"] = str(Path(c).expanduser())
            return cfg
    raise SystemExit(
        "[!] aucune config trouvée — passer --config, ou définir "
        "$OPENCARNET_CONFIG, ou créer ~/.config/opencarnet/config.json"
    )


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def safe_name(s: str) -> str:
    # caractères interdits dans un nom de fichier ou cassant un [[wikilink]] / tableau
    s = re.sub(r'[/\\:|#^\[\]*"<>?]', "-", s).strip()
    return re.sub(r"\s+", " ", s) or "Sans titre"


def yaml_str(v: str) -> str:
    if v == "" or re.search(r"[:#\[\]{},&*!|>'\"%@`]", v) or v != v.strip():
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return v


def yaml_list(items) -> str:
    items = [str(i) for i in (items or []) if i]
    return "[]" if not items else "[" + ", ".join(yaml_str(i) for i in items) + "]"


def md_bullets(v) -> str:
    """Liste (ou chaîne) -> puces Markdown."""
    items = [str(x) for x in v if x] if isinstance(v, list) else ([str(v)] if v else [])
    return "\n".join(f"- {x}" for x in items) or "- "


def fence(code: str) -> str:
    """Clôture de bloc de code plus longue que toute suite de ` dans le contenu."""
    longest = max((len(m) for m in re.findall(r"`+", code)), default=0)
    return "`" * max(3, longest + 1)


def dedup(seq):
    seen, out = set(), []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ---------- routage (100% config) ----------

def resolve(ext: dict, cfg: dict):
    rule = (cfg.get("routes") or {}).get(ext.get("type_contenu", "aucun"))
    if not rule:
        return None
    family = rule.get("family", "resource")
    themes = ext.get("themes") or []
    is_ai = bool(set(cfg.get("ai_themes", [])) & set(themes))
    themes_map = cfg.get("themes", {})
    default_theme = cfg.get("default_theme", "")

    folder = rule.get("folder")
    if family == "resource":
        if rule.get("folder_if_ai"):
            folder = rule["folder_if_ai"] if is_ai else None
        if folder is None:  # route par thème
            theme = themes[0] if themes else default_theme
            folder = themes_map.get(theme) or themes_map.get(default_theme) or "."

    if ext.get("dossier_cible"):  # override explicite de l'analyse
        folder = str(ext["dossier_cible"])

    cat = rule.get("categorie")
    if not cat or cat == "(from analysis)":
        cat = ext.get("categorie_vault") or cfg.get("frontmatter", {}).get("default_categorie", "Veille")

    tags = list(cfg.get("frontmatter", {}).get("base_tags", []))
    tags += rule.get("tags", [])
    if rule.get("tags_if_ai") and is_ai:
        tags += rule["tags_if_ai"]
    return {"family": family, "categorie": cat, "folder": folder, "is_ai": is_ai, "tags": tags}


# ---------- corps de fiche (défauts FR ; surchargés par config si fourni) ----------

def substance_md(st: dict) -> str:
    out = []
    for label, key in [("Modèle ciblé", "modele_cible"), ("Stack", "stack"),
                        ("Méthode", "methode"), ("Étapes", "etapes"),
                        ("Placeholders", "placeholders"), ("Détails", "details")]:
        v = (st or {}).get(key)
        if not v:
            continue
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v)
        out.append(f"- **{label}** : {v}")
    return "\n".join(out)


def body_prompt(ext: dict, src: str, cfg: dict) -> str:
    st = ext.get("substance_technique") or {}
    code = st.get("code") or ext.get("code") or "_(prompt non fourni en clair — voir la source)_"
    vars_ = st.get("placeholders") or []
    vars_md = "\n".join(f"- `{v}` : " for v in vars_) or "- _aucune_"
    liens_md = "\n".join(f"- {u}" for u in (ext.get("liens") or [])) or "- "
    f = fence(code)
    return f"""# 🤖 {ext.get('nom','')}

## 🎯 Objectif
- {ext.get('resume','')}

## 💻 Code (prêt à copier-coller)

{f}markdown
{code}
{f}

## 🧩 Variables à renseigner
{vars_md}

## 🖼️ Exemple de résultat
- 

## 📓 Journal d'itérations

| Date | Changement | Résultat |
|---|---|---|
| {date.today().isoformat()} | Import OpenCarnet | À tester |

## 🔗 Ressources & liens liés
- Source : {src}
{liens_md}
"""


def body_resource(ext: dict, src: str, cfg: dict) -> str:
    subst = substance_md(ext.get("substance_technique"))
    citation = ext.get("citation_cle") or ""
    img_md = "\n".join(f"![[{Path(i).name}]]" for i in (ext.get("illustrations") or []))
    liens_md = "\n".join(f"- {u}" for u in (ext.get("liens") or []))
    return f"""# 📚 {ext.get('nom','')}

## 🔎 Résumé
{md_bullets(ext.get('resume'))}

## 💡 Idées clés / Citations
{('- « ' + citation + ' »') if citation else '- '}
{subst}

{img_md}

## 🤖 Exploitation possible
{md_bullets(ext.get('exploitation'))}

## 🔗 Lien vers la source
- {src}
{liens_md}
"""


def build_frontmatter(ext: dict, route: dict, src: str, cfg: dict, today: str) -> str:
    f = cfg.get("frontmatter", {})
    tags = dedup(route["tags"] + (ext.get("tags_extra") or []))
    lines = ["aliases: []", f"type: {yaml_str(str(f.get('type','ressource')))}",
             f"categorie: {yaml_str(str(route['categorie']))}", "tags:"]
    lines += [f"  - {yaml_str(str(t))}" for t in tags]
    lines += [
        f"themes: {yaml_list(ext.get('themes'))}",
        f"statut: {yaml_str(str(f.get('default_statut','À consulter')))}",
        f"casquettes: {yaml_list(ext.get('casquettes'))}",
        f"projets_lies: {yaml_list(ext.get('projets_lies'))}",
        f"source: {yaml_str(src)}",
    ]
    for df in f.get("date_fields", ["date_creation", "date_dernière_mise_a_jour"]):
        lines.append(f'{df}: "{today}"')
    if route["family"] == "prompt":
        for k, v in (cfg.get("prompt_extra_fields") or {"outils": "[]", "partageable": "false"}).items():
            lines.append(f"{k}: {v}")
    return "---\n" + "\n".join(lines) + "\n---\n"


# ---------- dédoublonnage ----------

def scan_index(root: Path, dirs: list[str]) -> dict:
    """Nom normalisé -> fiche existante. Pas de dédoublonnage par URL seule :
    plusieurs substances d'une même source donnent légitimement plusieurs fiches."""
    by_name = {}
    for d in dirs:
        base = root / d
        if base.is_dir():
            for p in base.rglob("*.md"):
                by_name.setdefault(norm(p.stem), p)
    return by_name


def merge_source(p: Path, src: str) -> str:
    """Fusion non destructive : ajoute la source en fin de fiche si elle est absente."""
    text = p.read_text(encoding="utf-8")
    if not src or src in text:
        return "source déjà présente"
    p.write_text(text.rstrip() + f"\n- Source (doublon) : {src}\n", encoding="utf-8")
    return "source ajoutée"


# ---------- index / MOC ----------

def update_moc(root: Path, moc_rel: str, section: str, name: str, tc: str, today: str) -> str:
    p = root / moc_rel
    row = f"| [[{name}]] | {tc} | {today} |"
    header = f"{section}\n\n| Note | Type | Date |\n|---|---|---|\n"
    if p.exists():
        text = p.read_text(encoding="utf-8")
        if f"[[{name}]]" in text:
            return "déjà indexé"
        if section in text:
            # insère sous la ligne `|---` du premier tableau de la section, sinon crée le tableau
            start = text.index(section) + len(section)
            nxt = re.search(r"^#{1,6} ", text[start:], re.M)
            end = start + nxt.start() if nxt else len(text)
            sep = re.search(r"^\|\s*-{3}.*$\n?", text[start:end], re.M)
            if sep:
                i = start + sep.end()
                text = text[:i] + ("" if text[i - 1:i] == "\n" else "\n") + row + "\n" + text[i:]
            else:
                text = text[:start] + "\n\n| Note | Type | Date |\n|---|---|---|\n" + row + "\n" + text[start:].lstrip("\n")
        else:
            text = text.rstrip() + "\n\n" + header + row + "\n"
    else:
        text = header + row + "\n"
    p.write_text(text, encoding="utf-8")
    return "indexé"


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--analysis", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    root = Path(os.path.expanduser(str(cfg.get("root", "."))))
    scan_dir = (cfg.get("index") or {}).get("scan_dir") or "."
    inbox_dir = cfg.get("inbox_dir", "inbox")
    moc_cfg = cfg.get("moc") or {}

    apath = Path(args.analysis).expanduser()
    if not apath.exists():
        print(f"[!] analyse introuvable : {apath}", file=sys.stderr)
        return 1
    data = json.loads(apath.read_text(encoding="utf-8"))
    exts = data.get("extraction") or []
    if not exts:
        print("[i] aucune extraction exploitable.")
        return 2

    src = data.get("source_url", "")
    today = date.today().isoformat()
    by_name = scan_index(root, dedup([scan_dir, inbox_dir]))

    created = updated = skipped = 0
    for ext in exts:
        route = resolve(ext, cfg)
        if route is None:
            print(f"[i] ignoré (type_contenu={ext.get('type_contenu')}) : {ext.get('nom')}")
            skipped += 1
            continue

        name = safe_name(ext.get("nom") or "Sans titre")
        low_conf = (ext.get("confiance") == "basse") or (not src)
        folder = root / (inbox_dir if low_conf else route["folder"])
        dest = folder / f"{name}.md"
        existing = by_name.get(norm(name)) or (dest if dest.exists() else None)
        if existing:
            status = "dry" if args.dry_run else merge_source(existing, src)
            print(f"[~] doublon -> fusion ({status}) : {existing}")
            updated += 1
            continue
        content = build_frontmatter(ext, route, src, cfg, today) + "\n" + \
            (body_prompt if route["family"] == "prompt" else body_resource)(ext, src, cfg)

        if args.dry_run:
            print(f"[dry] {dest}\n{content[:500]}...\n")
            continue

        folder.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        by_name[norm(name)] = dest  # protège des homonymes dans la même analyse
        status = "créé"
        if not low_conf and moc_cfg:
            moc_rel = moc_cfg.get("prompt" if route["family"] == "prompt" else "resource")
            if moc_rel:
                status += ", " + update_moc(root, moc_rel, moc_cfg.get("section", "## 📥 Importés"),
                                            name, ext.get("type_contenu", ""), today)
        print(f"[+] {dest}  ({status})")
        created += 1

    verb = "[dry] " if args.dry_run else ""
    print(f"{verb}bilan : {created} créé(s), {updated} doublon(s), {skipped} ignoré(s).  [config: {cfg.get('_path')}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
