# Note formats & templates

> A recipe should look like a recipe, a place like a place. Formats give each kind
> of content its own **fields**, **properties** and **template**, while routing
> (which folder) stays unchanged.

## How it works

1. The AI picks a `format` for each extraction (or leaves it empty) and fills
   `donnees` with that format's fields. The list of formats and fields is part of
   the generated prompt (`compile.py --print-prompt`).
2. The engine **normalizes** typed fields (`number`, `minutes`), then **computes**
   the values the AI must never invent (map link, GPS, total time, domain…).
3. The note is written with the format's **frontmatter** (added after
   `frontmatter.fields`) and its **template**.

No format (or an unknown one) → the family template (`resource.md` /
`prompt.md`), exactly as before.

## Provided formats

| FR (`formats/fr.json`) | EN (`formats/en.json`) | Highlights |
|---|---|---|
| `recette` | `recipe` | servings, prep / cook / rest / **total** time (minutes, filterable), ingredients with quantities, tools, numbered steps, diet |
| `lieu` | `place` | address, city, **Google Maps link** (built), **GPS** (optional geocoding), budget, what to try |
| `ressource-web` | `web-resource` | the tool's own URL (not the source post), **domain** (computed), pricing, platforms, features |
| `livre` | `book` | author, year, genre, ISBN (only if visible), key ideas |
| `film-serie` | `film-series` | type, director, year, where to watch, pitch |
| `produit` | `product` | brand, price + **date the price was seen** (computed), link, pros / cons |

## Configuration

```jsonc
"language": "en",                        // templates/<language>/ and messages
"templates_dir": "~/my-templates",       // optional: your templates, searched first
"link_style": "wikilink",                // or "markdown" (images and index links)
"formats": "formats/en.json",            // a file…
// …or extend it: "formats": { "_extends": "formats/en.json", "book": null, "recipe": { "folder": "Recipes" } }
"geocoding": { "enabled": false, "user_agent": "" }
```

A format entry:

```jsonc
"recipe": {
  "when": "A reproducible food or drink recipe…",        // tells the AI when to pick it
  "fields": {                                              // filled by the AI
    "servings":  { "type": "number",  "prompt": "Number of servings, only if stated." },
    "prep_time": { "type": "minutes", "prompt": "Prep time in minutes, if stated." },
    "ingredients": { "type": "list",  "prompt": "One line per ingredient…" }
  },
  "frontmatter": { "servings": "{servings}", "total_time": "{total_time}" },
  "template": "recipe.md",                                // default: <format>.md
  "folder": "Recipes",                                    // optional: overrides routing
  "enrich": [ { "sum": "total_time", "of": ["prep_time", "cook_time", "rest_time"] } ]
}
```

Field types: `text`, `list`, `number` (written as a YAML number), `minutes`
(`"1 h 15"` → `75`; unreadable text is kept as `<field>_texte` for the body and
the property stays empty). Format field names must not reuse a field of the
extraction contract or a custom field — the engine refuses the config otherwise.

## Computed values (`enrich`)

| Rule | Effect |
|---|---|
| `{"sum": "total_time", "of": [...]}` | sum of the given minute fields, if not provided |
| `{"maps_link": "google_maps", "query": [...]}` | Google Maps search link built from the fields (no API key) |
| `{"geocode": "location", "query": [...], "fallback": [...], "fallback_require": ["address"], "require": ["city"], "match": "city", "min_precision": "adresse", "precision": "gps_precision"}` | `[lat, lon]` from OpenStreetMap Nominatim. A result is kept only if precise enough (`min_precision`: `adresse` > `ville` > `approximative`) and located in the right city (`match`) — a wrong pin is worse than none. The fallback query runs only when `fallback_require` fields are filled. |
| `{"domain": "domain", "from": "url"}` | domain of a URL |
| `{"stamp": "price_seen_on", "if": "price"}` | today's date when the field is filled |

Any rule accepts `"require_any": [fields]`: it is skipped unless at least one of
them is filled (e.g. no map link without a place name or address — it would only
point at the city).

**Geocoding** is off by default. When enabled it calls Nominatim at most once per
second with your `user_agent`, caches results in `~/.cache/opencarnet/`, and is
skipped with `--dry-run` / `--offline` (cache only). Coordinates are never
produced by the AI. `location: [lat, lon]` works with Obsidian map views.

## Template syntax

Templates are Markdown files with placeholders, parsed once (inserted values are
never re-interpreted — a prompt containing `{name}` comes out as is).

| Syntax | Result |
|---|---|
| `{field}` | value (lists joined with `, `); `{a.b}` = key `b` of object `a` |
| `{field\|liste}` | one `- item` per element |
| `{field\|numerote}` | `1. item`, `2. item`… |
| `{field\|puces:- [ ] @}` | one line per element, `@` = the element |
| `{field\|embed}` | image embed (`![[x]]` or `![](x)` per `link_style`) |
| `{field\|champs:k=Label,k2=Label 2;sep= : }` | object → `- **Label**<sep>value` lines |
| `{field\|minutes}` | `75` → `1 h 15 min` |
| `{field\|bloc:markdown}` | fenced code block (fence longer than any backticks inside) |
| `{field\|ou:other}` | if empty, value of `other` |
| `{field\|defaut:text}` | if empty, `text` |
| `{#if a}…{#else}…{/if}` | conditional block; `{#if a\|b}` = either is filled; `{#if !a}` = negation |
| `{{` `}}` | literal braces |

Placeholders available: every extraction field, the format's `donnees` (normalized
and enriched), custom fields, `{source_url}`, `{today}`, `{tags}`, `{categorie}`,
`{family}`, `{folder}`, `{code}`.

To customize a template, copy it from `templates/<language>/` into your
`templates_dir` and edit it there: your copy wins, the repository stays untouched.
