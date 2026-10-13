# Engine configuration (neutral)

> The engine (`scripts/compile.py`) knows **no hardcoded path, property or note
> text**. Routing, themes, frontmatter, note formats, templates and index come
> from a JSON file and template files (see also **`formats.md`**). This is what lets the same
> engine serve a personal vault, a wiki, a notes folder, or a neutral export.

## Where the config lives
Resolution order:
1. `--config <path>`
2. `$OPENCARNET_CONFIG` (legacy name `$INSTAGRAM_SAVED_CONFIG` still read)
3. `~/.config/opencarnet/config.json` (personal use)
4. `<skill>/config.example.json` (neutral default)

Keep your **personal** config out of the repo (it should not be published).

## Initialize (`--init`)

The easiest way to get a working config — no JSON to write by hand:

```bash
python3 scripts/compile.py --init                          # guided questions
python3 scripts/compile.py --init --tool obsidian --language fr \
  --root ~/Documents/Obsidian --review-dir "OpenCarnet/to-review"   # non-interactive
```

| Flag | Meaning |
|---|---|
| `--tool` | preset: `plain-markdown`, `obsidian`, `logseq` (see `presets/`) |
| `--language` | `en` or `fr` — templates, messages and generated prompt |
| `--root` | destination root (default from the preset) |
| `--review-dir` | "to review" folder (default from the preset) |
| `--templates-dir` | where templates are copied (default: `<config dir>/templates`) |
| `--config` | where to write the config (default `~/.config/opencarnet/config.json`) |
| `--force` | overwrite an existing config / templates |

`--init` writes the config, sets `templates_dir` (so you can edit the note
templates) and copies the chosen language's templates there. Each preset controls
`link_style`, folder layout, the taxonomy and — for Obsidian — an optional index;
**no preset contains a personal element**. Messages and prompts are emitted in the
config's `language` (`en` | `fr`).

## Config schema

```jsonc
{
  "root": "~/my-notes",                  // destination root
  "language": "en",                       // templates/<language>/ (en | fr)
  "templates_dir": "~/my-templates",      // optional: your own templates, searched first
  "link_style": "wikilink",               // or "markdown"
  "review_dir": "to-review",              // where low-confidence items land (old name: inbox_dir)
  "index": { "scan_dir": "" },             // EXTRA folder scanned for dedup; destination folders are always scanned (never all of root)
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
  "formats": "formats/en.json",            // note formats (recipe, place…) — see formats.md
  "geocoding": { "enabled": false, "user_agent": "" },
  "output": "markdown",                     // "markdown" (files) | "csv" | "jsonl" — see Output formats
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
4. A `dossier_cible` provided by the analysis **takes precedence** over all —
   but it is **forced under `root`**: an absolute path or a `../` escape is
   refused and the item goes to `review_dir` instead.
5. A `folder` set on the note's **format** overrides steps 2–3 (not step 4).
6. `confiance == "basse"`, **or** empty `source_url`, **or** an extraction with no
   content (empty `resume`, `substance_technique`, `citation_cle` **and** format
   `donnees` — a bare `liens` alone is not content) → `review_dir` (never indexed).

## Output formats

Notes are written as **Markdown files** by default (one per note, plus the
optional index). To gather everything into a single table instead — for Notion,
Airtable or Sheets — set `output`:

```jsonc
"output": "csv"                       // shorthand: { "format": "csv" }
"output": {
  "format": "csv",                    // or "jsonl" (one JSON object per line)
  "file": "opencarnet.csv",           // default: opencarnet.<format>
  "review_file": "to-review.csv",     // low-confidence items; default: to-review.<format>
  "columns": { "title": "{nom}", "theme": "{themes}", "link": "{source_url}" },
  "body": false,                      // true: add a `body` column with the full Markdown
  "list_sep": "; "                    // lists joined with this in CSV
}
```

- **One row per note.** Deduplication is unchanged (by normalized name): an
  existing row is never duplicated — the new source is appended to its `source`.
- Low-confidence / URL-less items go to `review_file` (never mixed with the rest).
- **Default columns** = `nom` + your `frontmatter` properties (including
  `by_family` and per-format properties), so no field is lost. Set `columns` for
  a clean subset; `nom` stays present (title + dedup key). Column values use the
  same placeholders as the frontmatter.
- `jsonl` keeps types (lists stay arrays, numbers stay numbers); `csv` joins
  lists with `list_sep` and quotes multi-line values (e.g. `body`).

## Methodology rules (storage-independent)
- **"List" granularity**: recipe → one note; tool list → one note per tool;
  other lists (furniture, brands, cultural recs…) → one recap note per list.
- **Dedup** by normalized name (Unicode-aware) before creating: an existing note
  is never overwritten, the new source URL is appended to it (non-destructive
  merge). Only your **destination folders** (routes, themes, formats, review) plus
  an explicit `index.scan_dir` are scanned — never all of `root`, so ordinary
  notes that happen to share a name are left alone. No dedup on URL alone — one
  source can legitimately yield several notes.
- **Index** (if `moc` configured): appended in a dedicated section, deduped,
  without touching curated sections.
- **Filename**: `<Readable name>.md`; `/ \ : | # ^ [ ] * " < > ?` are replaced
  by `-` (they break filenames, `[[wikilinks]]` or index tables).

## Provided examples
- `presets/` — starting configs used by `--init` (`plain-markdown`, `obsidian`, `logseq`).
- `config.example.json` — neutral (no personal paths).
- A real config usually lives at
  `~/.config/opencarnet/config.json`.
