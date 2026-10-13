"""Mini moteur de modèles (sans dépendance) pour les fiches OpenCarnet.

Syntaxe :
    {champ}                     valeur (liste -> « a, b ») ; {a.b} = clé b de l'objet a
    {champ|filtre|filtre:arg}   filtres enchaînés (l'argument va jusqu'au | ou } suivant)
    {#if champ} … {#else} … {/if}   bloc conditionnel (imbricable) ; {#if a|b} = l'un ou l'autre
    {{  }}                      accolades littérales

Le modèle est analysé une seule fois ; les valeurs insérées ne sont jamais
réinterprétées (un prompt contenant « {nom} » ressort tel quel).

Filtres :
    liste              une puce « - x » par élément
    numerote           « 1. x », « 2. y »…
    puces:MOTIF        une ligne par élément, « @ » = l'élément (ex. « - [ ] @ »)
    embed              image intégrée (wikilink ou Markdown selon link_style)
    champs:k=Libellé,k2=Libellé2[;sep= : ]   objet -> « - **Libellé**<sep>valeur »
    minutes            45 -> « 45 min », 75 -> « 1 h 15 min »
    bloc:LANGAGE       bloc de code, clôture plus longue que tout ` du contenu
    ou:AUTRE_CHAMP     si vide, prend la valeur d'un autre champ
    defaut:TEXTE       si vide, TEXTE
"""
from __future__ import annotations

import re
from pathlib import Path

TOKEN = re.compile(r"\{\{|\}\}|\{(#if\s+[^{}]+|#else|/if|[A-Za-z_][\w.]*(?:\|[^{}]*)?)\}")


class TemplateError(ValueError):
    pass


def parse(template: str):
    """Arbre : liste de str | ("var", nom, filtres) | ("if", nom, oui, non)."""
    root: list = []
    stack = [(root, None)]  # (liste courante, noeud if en cours)
    pos = 0
    for m in TOKEN.finditer(template):
        cur = stack[-1][0]
        if m.start() > pos:
            cur.append(template[pos:m.start()])
        pos = m.end()
        tok = m.group(0)
        if tok == "{{":
            cur.append("{")
        elif tok == "}}":
            cur.append("}")
        else:
            body = m.group(1)
            if body.startswith("#if"):
                node = ["if", body[3:].strip(), [], []]
                cur.append(node)
                stack.append((node[2], node))
            elif body == "#else":
                if stack[-1][1] is None:
                    raise TemplateError("{#else} sans {#if}")
                node = stack.pop()[1]
                stack.append((node[3], node))
            elif body == "/if":
                if stack[-1][1] is None:
                    raise TemplateError("{/if} sans {#if}")
                stack.pop()
            else:
                name, *filters = body.split("|")
                cur.append(("var", name, filters))
    if len(stack) > 1:
        raise TemplateError("{#if} non fermé")
    if pos < len(template):
        stack[-1][0].append(template[pos:])
    return root


def lookup(ctx: dict, name: str):
    v = ctx
    for part in name.split("."):
        if not isinstance(v, dict):
            return None
        v = v.get(part)
    return v


def empty(v) -> bool:
    return v is None or v == "" or v == [] or v == {}


def as_items(v) -> list:
    if empty(v):
        return []
    if isinstance(v, list):
        return [x for x in v if not empty(x)]
    return [v]


def to_text(v) -> str:
    if empty(v):
        return ""
    if isinstance(v, list):
        return ", ".join(to_text(x) for x in v if not empty(x))
    if isinstance(v, bool):
        return "oui" if v else "non"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def fmt_minutes(v) -> str:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return to_text(v)
    m = int(round(v))
    if m < 60:
        return f"{m} min"
    h, r = divmod(m, 60)
    return f"{h} h {r:02d} min" if r else f"{h} h"


def apply_filter(v, flt: str, ctx: dict, opts: dict):
    name, _, arg = flt.partition(":")
    name = name.strip()
    if name == "defaut":
        return arg if empty(v) else v
    if name == "ou":
        return lookup(ctx, arg.strip()) if empty(v) else v
    if name == "liste":
        return "\n".join(f"- {to_text(x)}" for x in as_items(v))
    if name == "numerote":
        return "\n".join(f"{i}. {to_text(x)}" for i, x in enumerate(as_items(v), 1))
    if name == "puces":
        return "\n".join(arg.replace("@", to_text(x)) for x in as_items(v))
    if name == "embed":
        if opts.get("link_style") == "markdown":
            return "\n".join(f"![]({x})" for x in as_items(v))
        return "\n".join(f"![[{Path(str(x)).name}]]" for x in as_items(v))
    if name == "champs":
        spec, _, sep = arg.partition(";sep=")
        sep = sep if sep else ": "
        out = []
        for pair in spec.split(","):
            key, _, label = pair.partition("=")
            val = (v or {}).get(key.strip()) if isinstance(v, dict) else None
            if not empty(val):
                out.append(f"- **{label.strip() or key.strip()}**{sep}{to_text(val)}")
        return "\n".join(out)
    if name == "minutes":
        return fmt_minutes(v)
    if name == "bloc":
        code = to_text(v)
        longest = max((len(m) for m in re.findall(r"`+", code)), default=0)
        fence = "`" * max(3, longest + 1)
        return f"{fence}{arg.strip()}\n{code}\n{fence}"
    raise TemplateError(f"filtre inconnu : {name}")


def evaluate(tree, ctx: dict, opts: dict) -> str:
    out = []
    for node in tree:
        if isinstance(node, str):
            out.append(node)
        elif node[0] == "var":
            v = lookup(ctx, node[1])
            for flt in node[2]:
                v = apply_filter(v, flt, ctx, opts)
            out.append(to_text(v))
        else:  # if
            cond = node[1]
            neg = cond.startswith("!")
            names = cond.lstrip("!").split("|")  # {#if a|b} : vrai si l'un des champs est rempli
            truthy = any(not empty(lookup(ctx, n.strip())) for n in names)
            out.append(evaluate(node[2] if truthy != neg else node[3], ctx, opts))
    return "".join(out)


def render(template: str, ctx: dict, **opts) -> str:
    return evaluate(parse(template), ctx, opts)
