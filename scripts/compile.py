#!/usr/bin/env python3
"""Moteur de compilation (neutre) : transforme l'analyse d'un item sauvegardé
en fiches, selon un fichier de configuration JSON.

AUCUN chemin ni AUCUNE propriété n'est codé en dur : racine, dossiers, thèmes,
routage, frontmatter, champs personnalisés et index (MOC) proviennent de la
config. C'est ce qui permet le même moteur pour tous les usages.

Usage :
    python3 compile.py --init [--tool obsidian] [--language fr] [--root ~/notes] [--force]
    python3 compile.py --analysis analyses/x.json [--config config.json] [--dry-run]
    python3 compile.py --print-prompt [--config config.json]

Résolution de la config (par ordre) :
    1. --config
    2. $OPENCARNET_CONFIG (ou l'ancien $INSTAGRAM_SAVED_CONFIG)
    3. ~/.config/opencarnet/config.json
    4. <skill>/config.example.json

Codes de sortie : 0 = ok, 1 = erreur, 2 = rien à faire.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import shutil
import sys
import unicodedata
import urllib.parse
from datetime import date
from pathlib import Path

import enrich
import templating

SKILL_DIR = Path(__file__).resolve().parent.parent
PRESETS_DIR = SKILL_DIR / "presets"
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "opencarnet" / "config.json"
DEFAULT_CONFIG_CANDIDATES = [
    os.environ.get("OPENCARNET_CONFIG", ""),
    os.environ.get("INSTAGRAM_SAVED_CONFIG", ""),  # ancien nom, conservé
    str(DEFAULT_CONFIG_PATH),
    str(SKILL_DIR / "config.example.json"),
]

SUPPORTED_LANGS = ("en", "fr")
SUPPORTED_TOOLS = ("plain-markdown", "obsidian", "logseq")

# Tous les messages destinés à l'utilisateur, dans la langue de la config.
# `T(lang, "clé", **champs)` ; repli sur l'anglais si la clé/langue manque.
MESSAGES = {
    "en": {
        "config_not_found": "no config found — run `--init`, pass --config, set "
                             "$OPENCARNET_CONFIG, or create ~/.config/opencarnet/config.json",
        "formats_not_found": "formats not found: {path}",
        "format_clash": "format \"{fmt}\": reserved field(s) {fields} — rename them.",
        "template_not_found": "template not found: {name} (looked in {dirs})",
        "old_config": "{path}: old config format ({keys}). Describe your properties under "
                      "frontmatter.fields (and frontmatter.by_family for extras). "
                      "See reference/configuration.md and config.example.json.",
        "analysis_missing": "analysis not found: {path}",
        "analysis_required": "--analysis is required (or --print-prompt / --init)",
        "bad_output": "output.format \"{fmt}\" unknown — use \"markdown\", \"csv\" or \"jsonl\".",
        "nothing": "nothing to file.",
        "ignored": "ignored (type_contenu={tc}): {name}",
        "duplicate": "duplicate -> merge ({status}): {path}",
        "src_present": "source already present",
        "src_added": "source added",
        "dup_source_line": "- Duplicate source: {src}",
        "created": "created",
        "dry": "dry",
        "indexed": "indexed",
        "already_indexed": "already indexed",
        "created_line": "[+] {dest}  ({status})",
        "summary": "{verb}summary: {created} created, {dup} duplicate(s), {skipped} ignored."
                   "  [config: {cfg}]",
        "verb_dry": "[dry] ",
        "init_intro": "OpenCarnet setup — a few questions, then your notes file themselves.",
        "init_tool": "Notes app?  1) Plain Markdown  2) Obsidian  3) Logseq  [1] ",
        "init_root": "Where should notes go? [{default}] ",
        "init_lang": "Language of the notes? (en/fr) [{default}] ",
        "init_review": "Folder for notes to review? [{default}] ",
        "init_invalid_choice": "Please answer 1, 2 or 3 (or a name).",
        "init_bad_lang": "Please answer en or fr.",
        "init_config_exists": "A config already exists: {path}\nUse --force to overwrite it.",
        "init_unknown_tool": "Unknown tool \"{tool}\". Choose one of: {tools}.",
        "init_wrote": "Config written: {path}",
        "init_templates_copied": "Templates ({language}) copied to {dest} ({n} files).",
        "init_templates_kept": "Existing templates kept in {dest} (use --force to replace them).",
        "init_next": "Next: `python3 scripts/compile.py --print-prompt` to get your extraction prompt.",
    },
    "fr": {
        "config_not_found": "aucune config trouvée — lancez `--init`, passez --config, définissez "
                            "$OPENCARNET_CONFIG, ou créez ~/.config/opencarnet/config.json",
        "formats_not_found": "formats introuvables : {path}",
        "format_clash": "format « {fmt} » : champ(s) réservé(s) {fields} — renommez-les.",
        "template_not_found": "modèle introuvable : {name} (cherché dans {dirs})",
        "old_config": "{path} : ancien format de config ({keys}). Décrivez désormais vos propriétés "
                      "dans frontmatter.fields (et frontmatter.by_family pour les extras). "
                      "Voir reference/configuration.md et config.example.json.",
        "analysis_missing": "analyse introuvable : {path}",
        "analysis_required": "--analysis est requis (ou --print-prompt / --init)",
        "bad_output": "output.format « {fmt} » inconnu — utilisez « markdown », « csv » ou « jsonl ».",
        "nothing": "aucune extraction exploitable.",
        "ignored": "ignoré (type_contenu={tc}) : {name}",
        "duplicate": "doublon -> fusion ({status}) : {path}",
        "src_present": "source déjà présente",
        "src_added": "source ajoutée",
        "dup_source_line": "- Source (doublon) : {src}",
        "created": "créé",
        "dry": "à blanc",
        "indexed": "indexé",
        "already_indexed": "déjà indexé",
        "created_line": "[+] {dest}  ({status})",
        "summary": "{verb}bilan : {created} créé(s), {dup} doublon(s), {skipped} ignoré(s)."
                   "  [config : {cfg}]",
        "verb_dry": "[à blanc] ",
        "init_intro": "Installation d'OpenCarnet — quelques questions, puis vos notes se rangent seules.",
        "init_tool": "Outil de notes ?  1) Dossier Markdown  2) Obsidian  3) Logseq  [1] ",
        "init_root": "Où ranger les fiches ? [{default}] ",
        "init_lang": "Langue des fiches ? (en/fr) [{default}] ",
        "init_review": "Dossier des fiches à relire ? [{default}] ",
        "init_invalid_choice": "Répondez 1, 2 ou 3 (ou un nom).",
        "init_bad_lang": "Répondez en ou fr.",
        "init_config_exists": "Une config existe déjà : {path}\nUtilisez --force pour la remplacer.",
        "init_unknown_tool": "Outil inconnu « {tool} ». Choisissez parmi : {tools}.",
        "init_wrote": "Config écrite : {path}",
        "init_templates_copied": "Modèles ({language}) copiés dans {dest} ({n} fichiers).",
        "init_templates_kept": "Modèles existants conservés dans {dest} (--force pour les remplacer).",
        "init_next": "Ensuite : `python3 scripts/compile.py --print-prompt` pour obtenir votre prompt d'extraction.",
    },
}


def T(lang: str, key: str, **kw) -> str:
    text = (MESSAGES.get(lang) or {}).get(key) or MESSAGES["en"].get(key, key)
    return text.format(**kw) if kw else text


def detect_lang() -> str:
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if (os.environ.get(var) or "").lower().startswith("fr"):
            return "fr"
    return "en"


def load_config(path: str | None) -> dict:
    for c in ([path] if path else DEFAULT_CONFIG_CANDIDATES):
        if c and Path(c).expanduser().exists():
            cfg = json.loads(Path(c).expanduser().read_text(encoding="utf-8"))
            cfg["_path"] = str(Path(c).expanduser())
            cfg["formats"] = load_formats(cfg)
            return cfg
    raise SystemExit("[!] " + T(detect_lang(), "config_not_found"))


def find_file(rel: str, cfg: dict) -> Path | None:
    """Chemin relatif au dossier de la config, sinon au skill."""
    p = Path(os.path.expanduser(rel))
    if p.is_absolute():
        return p if p.exists() else None
    for base in (Path(cfg.get("_path", ".")).parent, SKILL_DIR):
        if (base / p).exists():
            return base / p
    return None


def load_formats(cfg: dict) -> dict:
    """`formats` : objet, ou chemin d'un JSON, ou objet avec `_extends` (fusion :
    les clés données remplacent celles du fichier de base, format par format)."""
    spec = cfg.get("formats") or {}
    if isinstance(spec, str):
        spec = {"_extends": spec}
    base = {}
    if spec.get("_extends"):
        f = find_file(spec["_extends"], cfg)
        if not f:
            raise SystemExit("[!] " + T(cfg.get("language") or detect_lang(),
                                        "formats_not_found", path=spec["_extends"]))
        base = json.loads(f.read_text(encoding="utf-8"))
    out = {k: v for k, v in base.items() if not k.startswith("_")}
    for k, v in spec.items():
        if k.startswith("_"):
            continue
        out[k] = {**out.get(k, {}), **v} if isinstance(v, dict) else v
    return {k: v for k, v in out.items() if v}  # `"livre": null` désactive un format


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def safe_name(s: str) -> str:
    # caractères interdits dans un nom de fichier ou cassant un [[wikilink]] / tableau
    s = re.sub(r'[/\\:|#^\[\]*"<>?]', "-", s).strip()
    return re.sub(r"\s+", " ", s) or "Sans titre"


YAML_RETYPED = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}.*|[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?|"
    r"true|false|yes|no|on|off|null|~)$", re.I)


def yaml_str(v: str) -> str:
    if v == "" or re.search(r"[:#\[\]{},&*!|>'\"%@`]", v) or v != v.strip() or YAML_RETYPED.match(v):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return v


def yaml_scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return yaml_str(str(v))


def yaml_list(items) -> str:
    items = [i for i in (items or []) if i not in (None, "")]
    return "[]" if not items else "[" + ", ".join(yaml_scalar(i) for i in items) + "]"


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

    # categorie : valeur fixe, ou repère `{champ}` lu dans l'analyse
    default_cat = cfg.get("frontmatter", {}).get("default_categorie", "")
    cat = rule.get("categorie") or ""
    if "{" in cat:
        cat = interpolate(cat, ext) or default_cat
    cat = cat or default_cat

    tags = list(cfg.get("frontmatter", {}).get("base_tags", []))
    tags += rule.get("tags", [])
    if rule.get("tags_if_ai") and is_ai:
        tags += rule["tags_if_ai"]
    return {"family": family, "categorie": cat, "folder": folder, "is_ai": is_ai, "tags": tags}


# ---------- contexte & corps de fiche (modèles) ----------

RESERVED = {"type_contenu", "nom", "resume", "exploitation", "substance_technique", "citation_cle",
            "liens", "illustrations", "themes", "tags_extra", "confiance", "dossier_cible", "format",
            "donnees", "source_url", "today", "family", "folder", "categorie", "tags", "code"}


def check_formats(cfg: dict) -> None:
    """Refuse les champs de format qui écraseraient un champ du contrat ou du moteur."""
    custom = set(cfg.get("custom_fields") or {})
    for fname, f in cfg["formats"].items():
        names = set(f.get("fields") or {}) | enrich.targets(f.get("enrich"))
        clash = sorted(names & (RESERVED | custom))
        if clash:
            raise SystemExit("[!] " + T(cfg.get("language") or detect_lang(),
                                        "format_clash", fmt=fname, fields=", ".join(clash)))


def build_context(ext: dict, route: dict, src: str, cfg: dict, today: str, offline: bool) -> dict:
    ctx = dict(ext)
    fmt = cfg["formats"].get(ext.get("format") or "")
    if fmt:
        data = enrich.normalize(ext.get("donnees") or {}, fmt.get("fields"))
        data["_today"] = today
        data = enrich.apply(data, fmt.get("enrich"), cfg.get("geocoding") or {}, offline)
        data.pop("_today", None)
        ctx.update({k: v for k, v in data.items() if k not in RESERVED})
    st = ext.get("substance_technique") or {}
    ctx.update(source_url=src, today=today, family=route["family"], folder=route["folder"],
               categorie=route["categorie"], code=st.get("code") or ext.get("code") or "",
               tags=dedup(route["tags"] + (ext.get("tags_extra") or [])))
    return ctx


def load_template(name: str, cfg: dict) -> str:
    dirs = []
    if cfg.get("templates_dir"):
        d = find_file(cfg["templates_dir"], cfg)
        if d:
            dirs.append(d)
    dirs.append(SKILL_DIR / "templates" / cfg.get("language", "en"))
    for d in dirs:
        if (d / name).exists():
            return (d / name).read_text(encoding="utf-8")
    raise SystemExit("[!] " + T(cfg.get("language") or detect_lang(),
                                "template_not_found", name=name, dirs=", ".join(map(str, dirs))))


def build_body(ext: dict, route: dict, ctx: dict, cfg: dict) -> str:
    fmt = cfg["formats"].get(ext.get("format") or "")
    name = (fmt or {}).get("template") or (f"{ext['format']}.md" if fmt else f"{route['family']}.md")
    return templating.render(load_template(name, cfg), ctx, link_style=cfg.get("link_style", "wikilink"))


# ---------- frontmatter (100% config) ----------
#
# config.frontmatter.fields = { "clé": valeur }, rendu dans cet ordre :
#   - "texte {repère}"           -> chaîne, repères remplacés ;
#   - "{repère}" seul            -> valeur brute (une liste reste une liste) ;
#   - {"value": "{tags}", "style": "block"} -> liste en puces YAML ;
#   - [] / false / 3             -> littéral YAML.
# config.frontmatter.by_family = { "<famille>": { …mêmes règles… } } ajoute des
# clés selon la famille de la fiche. `fields: {}` => aucune ligne de frontmatter.

PLACEHOLDER = re.compile(r"\{([A-Za-z_]\w*)\}")
BASE_LIST_FIELDS = {"themes", "tags", "tags_extra", "liens", "illustrations", "exploitation"}


def interpolate(template: str, ctx: dict) -> str:
    def sub(m):
        v = ctx.get(m.group(1))
        if isinstance(v, list):
            return ", ".join(str(x) for x in v if x)
        return "" if v is None else str(v)
    return PLACEHOLDER.sub(sub, template)


def check_config(cfg: dict) -> None:
    """Refuse l'ancien format de frontmatter avec un message de migration clair."""
    fm = cfg.get("frontmatter", {})
    old = [k for k in ("type", "default_statut", "date_fields") if k in fm] + \
          (["prompt_extra_fields"] if "prompt_extra_fields" in cfg else [])
    if "fields" not in fm and (old or not fm):
        raise SystemExit("[!] " + T(cfg.get("language") or detect_lang(), "old_config",
                                    path=cfg.get("_path"),
                                    keys=", ".join(old) or ("frontmatter missing" if not fm else "")))


def field_types(cfg: dict, fmt: dict | None) -> dict:
    types = {k: "list" for k in BASE_LIST_FIELDS}
    for src in (cfg.get("custom_fields") or {}, (fmt or {}).get("fields") or {}):
        for k, d in src.items():
            if isinstance(d, dict) and d.get("type"):
                types[k] = d["type"]
    types.update(enrich.target_types((fmt or {}).get("enrich")))
    return types


def render_value(key: str, spec, ctx: dict, types: dict) -> str:
    style = "flow"
    if isinstance(spec, dict):
        style, spec = spec.get("style", "flow"), spec.get("value", "")
    if isinstance(spec, str):
        m = PLACEHOLDER.fullmatch(spec)
        if m:
            name = m.group(1)
            v = ctx.get(name)
            t = types.get(name)
            if isinstance(v, list) and t != "coords" or (v in (None, "") and t == "list"):
                items = [x for x in (v or []) if x not in (None, "")]
                if style == "block" and items:
                    return f"{key}:\n" + "\n".join(f"  - {yaml_scalar(i)}" for i in items)
                return f"{key}: {yaml_list(items)}"
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return f"{key}: {v}"
            if t == "coords" and isinstance(v, list) and v:
                return f"{key}: {yaml_list(v)}"
            if t in ("number", "minutes", "coords") or (v in (None, "") and t):
                return f"{key}:"  # null : propriété présente mais vide
        return f"{key}: {yaml_str(interpolate(spec, ctx))}"
    if isinstance(spec, list):
        return f"{key}: {yaml_list(spec)}"
    if isinstance(spec, bool):
        return f"{key}: {'true' if spec else 'false'}"
    return f"{key}: {'' if spec is None else spec}"


def build_frontmatter(ext: dict, route: dict, ctx: dict, cfg: dict) -> str:
    spec = cfg.get("frontmatter", {})
    fmt = cfg["formats"].get(ext.get("format") or "")
    fields = dict(spec.get("fields") or {})
    if not fields:
        return ""
    fields.update((spec.get("by_family") or {}).get(route["family"]) or {})
    fields.update((fmt or {}).get("frontmatter") or {})
    types = field_types(cfg, fmt)
    lines = [render_value(k, v, ctx, types) for k, v in fields.items()]
    return "---\n" + "\n".join(lines) + "\n---\n"


# ---------- prompt d'extraction (généré depuis la config) ----------

PROMPT_SKELETONS = {
    "en": """You receive a SAVED ITEM (Instagram, X, TikTok, YouTube…): its caption or text,
its audio transcript and the visual reading of its key images. Your task: extract
the USABLE SUBSTANCE, not an entertainment summary.

1. Split into independent substances (0..n): one entry per substance.
2. `type_contenu`: one of [@@VOCAB@@].
3. `themes`: only from [@@THEMES@@].
4. Fill the fields. Invent NOTHING: if a detail isn't legible, leave it empty and
   lower `confiance` (`basse` => the note goes to review, never filed).
5. `nom` = explicit title you could find again in 6 months.
6. `exploitation`: 1–3 concrete uses — never empty.
7. Custom fields for this setup:
@@CUSTOM@@
8. `format` + `donnees`: if the substance matches one of the formats below, set
   `format` to its name and fill `donnees` with its fields (types: number = digits
   only, minutes = integer minutes, list = array). Otherwise leave `format` empty.
   Never fill coordinates, map links or computed values: the engine adds them.
@@FORMATS@@
9. If no usable substance: {"extraction": []}.

Constraints: never copy a paid asset wholesale (extract + link); distinguish the
model CITED from the model USED; don't infer a tool name from a mis-transcribed word.

Output (one JSON per item):
@@SHAPE@@

[CAPTION]     : …
[TRANSCRIPT]  : …
[SCREEN READ] : …
[METADATA]    : author=…, date=…, url=…
""",
    "fr": """Vous recevez un ÉLÉMENT ENREGISTRÉ (Instagram, X, TikTok, YouTube…) : sa légende ou
son texte, la transcription de son audio et la lecture visuelle de ses images clés. Votre
tâche : extraire la SUBSTANCE UTILE, pas un résumé divertissant.

1. Découpez en substances indépendantes (0..n) : une entrée par substance.
2. `type_contenu` : une valeur parmi [@@VOCAB@@].
3. `themes` : uniquement parmi [@@THEMES@@].
4. Remplissez les champs. N'inventez RIEN : si un détail n'est pas lisible, laissez-le vide
   et baissez `confiance` (`basse` => la fiche part en relecture, jamais classée).
5. `nom` = titre explicite que vous pourriez retrouver dans 6 mois.
6. `exploitation` : 1 à 3 usages concrets — jamais vide.
7. Champs personnalisés de cette configuration :
@@CUSTOM@@
8. `format` + `donnees` : si la substance correspond à un des formats ci-dessous, mettez
   `format` à son nom et remplissez `donnees` avec ses champs (types : number = chiffres
   seuls, minutes = minutes entières, list = tableau). Sinon laissez `format` vide.
   Ne remplissez jamais les coordonnées, liens de carte ou valeurs calculées : le moteur les ajoute.
@@FORMATS@@
9. Si aucune substance utilisable : {"extraction": []}.

Contraintes : ne recopiez jamais un contenu payant en entier (extrait + lien) ; distinguez le
modèle CITÉ du modèle UTILISÉ ; ne déduisez pas un nom d'outil d'un mot mal transcrit.

Sortie (un JSON par élément) :
@@SHAPE@@

[LÉGENDE]       : …
[TRANSCRIPTION] : …
[LECTURE ÉCRAN] : …
[MÉTADONNÉES]   : author=…, date=…, url=…
""",
}


def build_prompt(cfg: dict) -> str:
    lang = cfg.get("language") if cfg.get("language") in PROMPT_SKELETONS else "en"
    vocab = ", ".join(list((cfg.get("routes") or {}).keys()) + ["aucun"])
    themes = ", ".join((cfg.get("themes") or {}).keys()) or ("(free)" if lang == "en" else "(libre)")
    none_custom = "- (none)" if lang == "en" else "- (aucun)"
    none_formats = "- (none)" if lang == "en" else "- (aucun)"
    custom = cfg.get("custom_fields") or {}
    custom_md = "\n".join(
        f"- `{k}` ({d.get('type', 'text')}) : {d.get('prompt', '')}" for k, d in custom.items()
        if isinstance(d, dict)) or none_custom
    example = {"type_contenu": "…", "nom": "…", "resume": "…", "exploitation": ["…"],
               "substance_technique": {"modele_cible": "", "stack": [], "methode": "", "etapes": [],
                                       "placeholders": [], "details": ""},
               "citation_cle": "", "liens": [], "illustrations": [], "themes": [], "tags_extra": [],
               "confiance": "haute | moyenne | basse"}
    for k, d in custom.items():
        example[k] = [] if isinstance(d, dict) and d.get("type") == "list" else ""
    formats = cfg.get("formats") or {}
    fmt_md = []
    for fname, f in formats.items():
        computed = enrich.targets(f.get("enrich"))
        fields = "\n".join(f"    - `{k}` ({d.get('type', 'text')}) : {d.get('prompt', '')}"
                           for k, d in (f.get("fields") or {}).items()
                           if isinstance(d, dict) and k not in computed)
        fmt_md.append(f"- `{fname}` — {f.get('when', '')}\n{fields}")
    if formats:
        example["format"] = "…"
        example["donnees"] = {}
    shape = json.dumps({"id": "…", "source_url": "…", "auteur": "…", "date_source": "…",
                        "canal": "…", "extraction": [example]}, ensure_ascii=False, indent=2)
    skeleton = PROMPT_SKELETONS[lang]
    return (skeleton.replace("@@VOCAB@@", vocab).replace("@@THEMES@@", themes)
            .replace("@@CUSTOM@@", custom_md)
            .replace("@@FORMATS@@", "\n".join(fmt_md) or none_formats)
            .replace("@@SHAPE@@", shape))


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


def merge_source(p: Path, src: str, lang: str) -> str:
    """Fusion non destructive : ajoute la source en fin de fiche si elle est absente."""
    text = p.read_text(encoding="utf-8")
    if not src or src in text:
        return "present"
    p.write_text(text.rstrip() + "\n" + T(lang, "dup_source_line", src=src) + "\n", encoding="utf-8")
    return "added"


# ---------- index / MOC ----------

def update_moc(root: Path, moc_rel: str, section: str, name: str, tc: str, today: str,
               link_style: str = "wikilink") -> str:
    p = root / moc_rel
    link = f"[{name}]({urllib.parse.quote(name)}.md)" if link_style == "markdown" else f"[[{name}]]"
    row = f"| {link} | {tc} | {today} |"
    header = f"{section}\n\n| Note | Type | Date |\n|---|---|---|\n"
    if p.exists():
        text = p.read_text(encoding="utf-8")
        if link in text:
            return "present"
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
    return "indexed"


# ---------- sortie tabulaire (csv / jsonl) ----------
#
# `output` : "markdown" (dossiers + index, défaut) ou un objet :
#   { "format": "csv" | "jsonl", "file": "opencarnet.csv",
#     "review_file": "to-review.csv", "columns": { "titre": "{nom}", … },
#     "body": false, "list_sep": "; " }
# Une ligne par fiche ; dédoublonnage par `nom` (comme le markdown) ; les fiches
# peu fiables vont dans `review_file`. Aucun nom de colonne n'est codé en dur :
# par défaut, colonnes = `nom` + les propriétés du frontmatter.

TABULAR_FORMATS = ("csv", "jsonl")


def output_config(cfg: dict) -> tuple[str, dict]:
    spec = cfg.get("output", "markdown")
    if isinstance(spec, str):
        spec = {"format": spec}
    fmt = str(spec.get("format") or "markdown").lower()
    return fmt, spec


def output_columns(cfg: dict, out: dict) -> dict:
    if out.get("columns"):
        cols = dict(out["columns"])
        cols.pop("nom", None)
        return {"nom": "{nom}", **cols}
    cols = {"nom": "{nom}"}
    fm = cfg.get("frontmatter", {})
    cols.update(fm.get("fields") or {})
    for fam in (fm.get("by_family") or {}).values():
        cols.update(fam or {})
    for f in (cfg.get("formats") or {}).values():
        cols.update((f or {}).get("frontmatter") or {})
    return cols


def plain_value(spec, ctx: dict):
    """Valeur brute d'une colonne (sans mise en forme YAML) : une liste reste une liste."""
    if isinstance(spec, dict):
        spec = spec.get("value", "")
    if isinstance(spec, str):
        m = PLACEHOLDER.fullmatch(spec)
        if m:
            return ctx.get(m.group(1))
        return interpolate(spec, ctx)
    return spec


def build_row(ext: dict, route: dict, ctx: dict, cfg: dict, cols: dict, name: str, body: str = "") -> dict:
    row = {"nom": name}
    for col, spec in cols.items():
        if col != "nom":
            row[col] = plain_value(spec, ctx)
    if body:
        row["body"] = body
    return row


def cell(v, sep: str = "; ") -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return sep.join(cell(x, sep) for x in v)
    return str(v)


def load_table(path: Path, fmt: str) -> list[dict]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if fmt == "jsonl":
        rows = []
        for line in text.splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return rows
    return [dict(r) for r in csv.DictReader(io.StringIO(text))]


def merge_row_source(row: dict, src: str) -> str:
    if not src:
        return "present"
    cur = row.get("source", "")
    if isinstance(cur, list):
        if src in cur:
            return "present"
        cur.append(src)
        return "added"
    if src in str(cur):
        return "present"
    row["source"] = f"{str(cur).strip()}, {src}" if str(cur).strip() else src
    return "added"


def write_table(path: Path, fmt: str, rows: list[dict], cols: dict, list_sep: str = "; ") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "jsonl":
        with path.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return
    fieldnames = list(cols.keys())
    for r in rows:
        for k in r:
            if k not in fieldnames:
                fieldnames.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: cell(r.get(k), list_sep) for k in fieldnames})
    path.write_text(buf.getvalue(), encoding="utf-8")


# ---------- init (guided setup) ----------

def pretty_path(p: Path) -> str:
    try:
        return "~/" + str(p.relative_to(Path.home()))
    except ValueError:
        return str(p)


def load_preset(tool: str, lang: str, root: str, review_dir: str, templates_dir: str) -> dict:
    p = PRESETS_DIR / f"{tool}.json"
    if not p.exists():
        raise SystemExit("[!] " + T(lang, "init_unknown_tool", tool=tool,
                                    tools=", ".join(SUPPORTED_TOOLS)))
    cfg = json.loads(p.read_text(encoding="utf-8"))
    cfg = {k: v for k, v in cfg.items() if not k.startswith("_")}
    cfg["root"] = root
    cfg["language"] = lang
    cfg["review_dir"] = review_dir
    cfg["templates_dir"] = templates_dir
    if isinstance(cfg.get("formats"), str):
        cfg["formats"] = cfg["formats"].replace("{LANG}", lang)
    return cfg


def ask(prompt: str, default: str = "") -> str:
    try:
        return (input(prompt).strip() or default)
    except EOFError:
        return default


def run_init(args) -> int:
    lang = args.language or detect_lang()
    tty = sys.stdin.isatty()
    cfg_path = Path(os.path.expanduser(args.config)) if args.config else DEFAULT_CONFIG_PATH

    if cfg_path.exists() and not args.force:
        print(T(lang, "init_config_exists", path=pretty_path(cfg_path)))
        return 1

    print(T(lang, "init_intro"))

    tool = args.tool
    if tool not in SUPPORTED_TOOLS:
        if not tty:
            raise SystemExit("[!] " + T(lang, "init_unknown_tool", tool=tool or "(none)",
                                        tools=", ".join(SUPPORTED_TOOLS)))
        while tool not in SUPPORTED_TOOLS:
            ans = ask(T(lang, "init_tool"), "1")
            tool = {"1": "plain-markdown", "2": "obsidian", "3": "logseq"}.get(ans, ans)
            if tool not in SUPPORTED_TOOLS:
                print(T(lang, "init_invalid_choice"))

    preset = json.loads((PRESETS_DIR / f"{tool}.json").read_text(encoding="utf-8"))

    root = args.root
    if not root:
        d = preset.get("_root_default", "~/Documents/OpenCarnet")
        root = ask(T(lang, "init_root", default=d), d) if tty else d
    root = pretty_path(Path(os.path.expanduser(root)))

    if args.language:
        lang = args.language
    elif tty:
        choice = ask(T(lang, "init_lang", default=lang), lang)
        while choice not in SUPPORTED_LANGS:
            choice = ask(T(lang, "init_bad_lang"), lang)
        lang = choice

    review = args.review_dir
    if not review:
        d = preset.get("_review_default", "to-review")
        review = ask(T(lang, "init_review", default=d), d) if tty else d

    config_dir = cfg_path.parent
    tdir = (Path(os.path.expanduser(args.templates_dir)) if args.templates_dir
            else config_dir / "templates")
    if not tdir.is_absolute():
        tdir = config_dir / tdir
    tdir_value = "templates" if tdir == config_dir / "templates" else pretty_path(tdir)

    cfg = load_preset(tool, lang, root, review, tdir_value)
    cfg = {"_comment": f"OpenCarnet config — generated by `compile.py --init` ({tool}, {lang}).", **cfg}
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(T(lang, "init_wrote", path=pretty_path(cfg_path)))

    src_dir = SKILL_DIR / "templates" / lang
    if tdir.exists() and any(tdir.iterdir()) and not args.force:
        print(T(lang, "init_templates_kept", dest=pretty_path(tdir)))
    else:
        tdir.mkdir(parents=True, exist_ok=True)
        files = sorted(src_dir.glob("*.md"))
        for f in files:
            shutil.copyfile(f, tdir / f.name)
        print(T(lang, "init_templates_copied", language=lang, dest=pretty_path(tdir), n=len(files)))

    print(T(lang, "init_next"))
    return 0


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--analysis")
    ap.add_argument("--init", action="store_true",
                    help="guided setup: write a config and copy the templates")
    ap.add_argument("--tool", choices=SUPPORTED_TOOLS,
                    help="preset for --init: " + ", ".join(SUPPORTED_TOOLS))
    ap.add_argument("--language", dest="language", choices=SUPPORTED_LANGS,
                    help="note language (en | fr)")
    ap.add_argument("--root", help="--init: destination root")
    ap.add_argument("--review-dir", dest="review_dir", help="--init: 'to review' folder")
    ap.add_argument("--templates-dir", dest="templates_dir", help="--init: where to copy templates")
    ap.add_argument("--force", action="store_true",
                    help="--init: overwrite an existing config / templates")
    ap.add_argument("--print-prompt", action="store_true",
                    help="affiche le prompt d'extraction adapté à la config, puis quitte")
    ap.add_argument("--config", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true",
                    help="aucun appel réseau (géocodage : cache uniquement)")
    args = ap.parse_args()

    if args.init:
        return run_init(args)

    cfg = load_config(args.config)
    check_config(cfg)
    check_formats(cfg)
    lang = cfg.get("language") if cfg.get("language") in SUPPORTED_LANGS else "en"
    if args.print_prompt:
        print(build_prompt(cfg))
        return 0
    if not args.analysis:
        ap.error(T(lang, "analysis_required"))
    root = Path(os.path.expanduser(str(cfg.get("root", "."))))
    scan_dir = (cfg.get("index") or {}).get("scan_dir") or "."
    inbox_dir = cfg.get("review_dir") or cfg.get("inbox_dir") or "to-review"
    moc_cfg = cfg.get("moc") or {}
    out_fmt, out_cfg = output_config(cfg)
    if out_fmt not in ("markdown", *TABULAR_FORMATS):
        raise SystemExit("[!] " + T(lang, "bad_output", fmt=out_fmt))
    tabular = out_fmt in TABULAR_FORMATS

    apath = Path(args.analysis).expanduser()
    if not apath.exists():
        print("[!] " + T(lang, "analysis_missing", path=apath), file=sys.stderr)
        return 1
    data = json.loads(apath.read_text(encoding="utf-8"))
    exts = data.get("extraction") or []
    if not exts:
        print("[i] " + T(lang, "nothing"))
        return 2

    src = data.get("source_url", "")
    today = date.today().isoformat()
    created = updated = skipped = 0

    if tabular:
        cols = output_columns(cfg, out_cfg)
        list_sep = out_cfg.get("list_sep", "; ")
        want_body = bool(out_cfg.get("body"))
        file_path = root / (out_cfg.get("file") or f"opencarnet.{out_fmt}")
        review_path = root / (out_cfg.get("review_file") or f"to-review.{out_fmt}")
        rows = {False: load_table(file_path, out_fmt), True: load_table(review_path, out_fmt)}
        by_key = {low: {norm(r.get("nom", "")): r for r in rows[low]} for low in (False, True)}
        for ext in exts:
            route = resolve(ext, cfg)
            if route is None:
                print("[i] " + T(lang, "ignored", tc=ext.get("type_contenu"), name=ext.get("nom")))
                skipped += 1
                continue
            name = safe_name(ext.get("nom") or "Sans titre")
            low = (ext.get("confiance") == "basse") or (not src)
            fmt = cfg["formats"].get(ext.get("format") or "") or {}
            if fmt.get("folder") and not ext.get("dossier_cible"):
                route["folder"] = fmt["folder"]
            ctx = build_context(ext, route, src, cfg, today, offline=args.offline or args.dry_run)
            row = build_row(ext, route, ctx, cfg, cols, name,
                            build_body(ext, route, ctx, cfg) if want_body else "")
            key = norm(name)
            dest = review_path if low else file_path
            existing = by_key[low].get(key)
            if existing:
                if args.dry_run:
                    status = T(lang, "dry")
                else:
                    status = T(lang, "src_present" if merge_row_source(existing, src) == "present"
                                 else "src_added")
                print("[~] " + T(lang, "duplicate", status=status, path=dest))
                updated += 1
                continue
            by_key[low][key] = row
            rows[low].append(row)
            if args.dry_run:
                print("[dry] " + json.dumps({k: cell(v, list_sep) for k, v in row.items()},
                                            ensure_ascii=False))
            else:
                print(T(lang, "created_line", dest=dest, status=T(lang, "created")))
            created += 1
        if not args.dry_run:
            write_table(file_path, out_fmt, rows[False], cols, list_sep)
            write_table(review_path, out_fmt, rows[True], cols, list_sep)
        verb = T(lang, "verb_dry") if args.dry_run else ""
        print(T(lang, "summary", verb=verb, created=created, dup=updated, skipped=skipped,
                cfg=cfg.get("_path")))
        return 0

    by_name = scan_index(root, dedup([scan_dir, inbox_dir]))
    for ext in exts:
        route = resolve(ext, cfg)
        if route is None:
            print("[i] " + T(lang, "ignored", tc=ext.get("type_contenu"), name=ext.get("nom")))
            skipped += 1
            continue

        name = safe_name(ext.get("nom") or "Sans titre")
        low_conf = (ext.get("confiance") == "basse") or (not src)
        fmt = cfg["formats"].get(ext.get("format") or "") or {}
        if fmt.get("folder") and not ext.get("dossier_cible"):
            route["folder"] = fmt["folder"]
        folder = root / (inbox_dir if low_conf else route["folder"])
        dest = folder / f"{name}.md"
        existing = by_name.get(norm(name)) or (dest if dest.exists() else None)
        if existing:
            if args.dry_run:
                status = T(lang, "dry")
            else:
                status = T(lang, "src_present" if merge_source(existing, src, lang) == "present"
                             else "src_added")
            print("[~] " + T(lang, "duplicate", status=status, path=existing))
            updated += 1
            continue
        ctx = build_context(ext, route, src, cfg, today, offline=args.offline or args.dry_run)
        fm = build_frontmatter(ext, route, ctx, cfg)
        content = (fm + "\n" if fm else "") + build_body(ext, route, ctx, cfg)

        if args.dry_run:
            print(f"[dry] {dest}\n{content[:500]}...\n")
            continue

        folder.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        by_name[norm(name)] = dest  # protège des homonymes dans la même analyse
        status = T(lang, "created")
        if not low_conf and moc_cfg:
            moc_rel = moc_cfg.get("prompt" if route["family"] == "prompt" else "resource")
            if moc_rel:
                indexed = update_moc(root, moc_rel, moc_cfg.get("section", "## OpenCarnet"),
                                     name, ext.get("type_contenu", ""), today,
                                     cfg.get("link_style", "wikilink"))
                status += ", " + T(lang, "already_indexed" if indexed == "present" else "indexed")
        print(T(lang, "created_line", dest=dest, status=status))
        created += 1

    verb = T(lang, "verb_dry") if args.dry_run else ""
    print(T(lang, "summary", verb=verb, created=created, dup=updated, skipped=skipped,
            cfg=cfg.get("_path")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
