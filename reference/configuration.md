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
    "type": "note",
    "default_categorie": "note",
    "default_statut": "to-review",
    "base_tags": ["imported"],
    "date_fields": ["created", "updated"]
  },
  "prompt_extra_fields": { "source": "[]" },
  "routes": {
    "<type_contenu>": {
      "family": "prompt" | "resource",     // prompt => "prompt" body, else "resource"
      "categorie": "prompt" | "note" | "(from analysis)",
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
