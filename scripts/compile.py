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
    2. $INSTAGRAM_SAVED_CONFIG
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
    os.environ.get("INSTAGRAM_SAVED_CONFIG", ""),
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
        "$INSTAGRAM_SAVED_CONFIG, ou créer ~/.config/opencarnet/config.json"
    )


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def safe_name(s: str) -> str:
    s = re.sub(r"[/\\:]", "-", s).strip()
    return re.sub(r"\s+", " ", s) or "Sans titre"


def yaml_str(v: str) -> str:
    if v == "" or re.search(r"[:#\[\]{}&*!|>'\"%@`]", v) or v != v.strip():
        return '"' + v.replace('"', '\\"') + '"'
    return v


def yaml_list(items) -> str:
    items = [i for i in (items or []) if i]
    return "[]" if not items else "[" + ", ".join(str(i) for i in items) + "]"


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
    return f"""# 🤖 {ext.get('nom','')}

## 🎯 Objectif
- {ext.get('resume','')}

## 💻 Code (prêt à copier-coller)

```markdown
{code}
```

## 🧩 Variables à renseigner
{vars_md}

## 🖼️ Exemple de résultat
- 

## 📓 Journal d'itérations

| Date | Changement | Résultat |
|---|---|---|
| {date.today().isoformat()} | Import Instagram | À tester |

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
- {ext.get('resume','')}

## 💡 Idées clés / Citations
{('- « ' + citation + ' »') if citation else '- '}
{subst}

{img_md}

## 🤖 Exploitation possible
- {ext.get('exploitation','')}

## 🔗 Lien vers la source
- {src}
{liens_md}
"""


def build_frontmatter(ext: dict, route: dict, src: str, cfg: dict, today: str) -> str:
    f = cfg.get("frontmatter", {})
    tags = dedup(route["tags"] + (ext.get("tags_extra") or []))
    lines = ["aliases: []", f"type: {f.get('type','ressource')}",
             f"categorie: {route['categorie']}", "tags:"]
    lines += [f"  - {t}" for t in tags]
    lines += [
        f"themes: {yaml_list(ext.get('themes'))}",
        f"statut: {f.get('default_statut','À consulter')}",
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

def scan_index(root: Path, scan_dir: str) -> dict:
    by_name, by_url = {}, {}
    base = root / scan_dir
    if not base.is_dir():
        return by_name
    for p in base.rglob("*.md"):
        by_name.setdefault(norm(p.stem), p)
        try:
            head = p.read_text(encoding="utf-8", errors="replace")[:1500]
        except OSError:
            continue
        for m in re.finditer(r"^\s*(?:source|url)\s*:\s*(.+)$", head, re.M):
            u = m.group(1).strip().strip('"').strip("'")
            if u.startswith("http"):
                by_url.setdefault(u, p)
    return by_name


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
            i = text.index(header) + len(header)
            text = text[:i] + row + "\n" + text[i:]
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
    ap.add_argument("--bundle", default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    root = Path(os.path.expanduser(str(cfg.get("root", "."))))
    scan_dir = (cfg.get("index") or {}).get("scan_dir", "")
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
    by_name = scan_index(root, scan_dir)

    created = updated = skipped = 0
    for ext in exts:
        route = resolve(ext, cfg)
        if route is None:
            print(f"[i] ignoré (type_contenu={ext.get('type_contenu')}) : {ext.get('nom')}")
            skipped += 1
            continue

        name = safe_name(ext.get("nom") or "Sans titre")
        low_conf = (ext.get("confiance") == "basse") or (not src)
        existing = by_name.get(norm(name))
        if existing:
            print(f"[~] doublon -> fusion : {existing}")
            updated += 1
            continue

        folder = root / (inbox_dir if low_conf else route["folder"])
        dest = folder / f"{name}.md"
        content = build_frontmatter(ext, route, src, cfg, today) + "\n" + \
            (body_prompt if route["family"] == "prompt" else body_resource)(ext, src, cfg)

        if args.dry_run:
            print(f"[dry] {dest}\n{content[:500]}...\n")
            continue

        folder.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
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
