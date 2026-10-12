# Engine configuration (neutral)

> The engine (`scripts/compile.py`) knows **no hardcoded path**. All routing,
> themes, frontmatter and index come from a JSON file. This is what lets the same
> engine serve a personal vault, a wiki, a notes folder, or a neutral export.

## Where the config lives
Resolution order:
1. `--config <path>`
2. `$OPENCARNET_CONFIG` (legacy name `$INSTAGRAM_SAVED_CONFIG` still read)
3. `~/.config/opencarnet/config.json` (personal use)
4. `<skill>/config.example.json` (neutral default)

Keep your **personal** config out of the repo (it should not be published).

## Config schema

```jsonc
{
  "root": "~/my-notes",                  // destination root
  "inbox_dir": "inbox",                   // where low-confidence items land
  "index": { "scan_dir": "notes" },       // folder scanned for deduplication (inbox_dir is always scanned too)
  "default_theme": "general",
  "ai_themes": ["tech"],
  "themes": { "<slug>": "<path relative to root>" },
  "frontmatter": {
    "fields": {                           // properties, in this order ({} => no frontmatter)
      "tags": { "value": "{tags}", "style": "block" },
      "category": "{categorie}",
      "status": "to-review",
      "source": "{source_url}",
      "created": "{today}"
    },
    "by_family": { "prompt": { "tested": false } },   // extra properties per family
    "base_tags": ["imported"],
    "default_categorie": "note"
  },
  "custom_fields": {                      // your own fields, filled by the AI
    "projects": { "type": "list", "prompt": "Related projects, as [[wikilinks]]. Empty if unsure." }
  },
  "routes": {
    "<type_contenu>": {
      "family": "prompt" | "resource",     // prompt => "prompt" body, else "resource"
      "categorie": "prompt" | "note" | "{a_custom_field}",
      "folder": "…",                        // fixed destination (optional)
      "folder_if_ai": "…",                 // alternative destination when theme is AI
      "tags": ["…"],                        // tags added
      "tags_if_ai": ["…"]                   // tags added when theme is AI
    }
  },
  "moc": {                                 // optional index (e.g. Obsidian); omit to disable
    "prompt": "…/index-prompts.md",
    "resource": "…/index-resources.md",
    "section": "## 📥 Imported"
  }
}
```

## Frontmatter

The engine writes **no property of its own**: every key comes from
`frontmatter.fields`, in order. Values:

| Value | Result |
|---|---|
| `"text {placeholder}"` | string, placeholders replaced (lists joined with `, `) |
| `"{placeholder}"` alone | raw value — a list stays a YAML list (`[a, b]`) |
| `{ "value": "{tags}", "style": "block" }` | list written as YAML bullets |
| `[]`, `false`, `3` | YAML literal |

Placeholders: any field of the analysis (including custom fields), plus
`{source_url}`, `{today}`, `{tags}` (base + route + `tags_extra`), `{categorie}`
(resolved by the route), `{family}`, `{folder}`.

Configs in the first format (`type`, `default_statut`, `date_fields`,
`prompt_extra_fields`) are refused with a migration message: move those values
into `frontmatter.fields` / `frontmatter.by_family`.

## Custom fields

`custom_fields` declares **your own** fields (roles, projects, category…). Each
has a `type` (`list` or `text`) and a `prompt`: the instruction given to the AI.
They are added to the extraction prompt (`compile.py --print-prompt`) and can be
used as placeholders in `frontmatter.fields` or in a route's `categorie`.

## Routing resolution
1. Take the rule for the `type_contenu`.
2. `family=prompt` → fixed `folder` (e.g. a prompts folder).
3. `family=resource`:
   - if `folder_if_ai` and a theme ∈ `ai_themes` → `folder_if_ai` ;
   - otherwise → the folder of the **first** theme (`themes[0]`), else `default_theme`.
4. A `dossier_cible` provided by the analysis **takes precedence** over all.
5. `confiance == "basse"` **or** empty `source_url` → `inbox_dir` (never indexed).

## Methodology rules (storage-independent)
- **"List" granularity**: recipe → one note; tool list → one note per tool;
  other lists (furniture, brands, cultural recs…) → one recap note per list.
- **Dedup** by normalized name before creating: an existing note is never
  overwritten, the new source URL is appended to it (non-destructive merge).
  No dedup on URL alone — one source can legitimately yield several notes.
- **Index** (if `moc` configured): appended in a dedicated section, deduped,
  without touching curated sections.
- **Filename**: `<Readable name>.md`; `/ \ : | # ^ [ ] * " < > ?` are replaced
  by `-` (they break filenames, `[[wikilinks]]` or index tables).

## Provided examples
- `config.example.json` — neutral (no personal paths).
- A real config usually lives at
  `~/.config/opencarnet/config.json`.
