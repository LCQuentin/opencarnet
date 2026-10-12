# Extraction schema

> Read **before step 3** of the SKILL. Defines the controlled vocabulary and the
> exact shape of the analysis produced for each bundle.
>
> Field names (e.g. `nom`, `resume`, `type_contenu`) are the **data contract**
> read by `scripts/compile.py` — they are kept as-is and should not be renamed.

## Principle

A bundle may hold **zero, one or several substances**. Example: a reel that
presents a SaaS tool *and* gives a workflow tip *and* cites a book. Then produce
`extraction[]` with **one entry per substance**, each routed independently to its
own note.

Never force an item with no real substance (pure entertainment): mark it
`type_contenu: aucun` and ignore it (or send it to the inbox for the record).

## Controlled vocabulary — `type_contenu`

| Value | Definition | Examples |
|---|---|---|
| `prompt` | A reusable prompt to copy | image-generation prompt, analysis prompt |
| `skill` | A skill / agent / capability file | Claude skill, GPT agent, `SKILL.md` |
| `modele-ia` | A precisely named AI model | Claude Opus, GPT-5, Recraft V4.1, Veo |
| `outil-service` | A SaaS, app, service, framework | n8n, Cursor, Notion, a prompt directory |
| `astuce` | A reproducible method / technique / hack | shortcut, workflow, setting |
| `reference` | A work, book, brand, product, person | a book, a film, a brand |
| `inspiration-design` | A visual / artistic direction | poster style, palette, layout |
| `actualite` | A news item / watch item | model release, funding round |
| `aucun` | Nothing usable | pure entertainment |

Rule: when torn between two values, pick the **most actionable** one (e.g.
"new model + usage tip" → two entries: `modele-ia` + `astuce`).

## Shape of the analysis

One `analyses/<id>.json` per bundle:

```json
{
  "id": "DRk3mQ_abc",
  "source_url": "https://www.instagram.com/reel/...",
  "auteur": "@someone",
  "date_source": "2026-09-30",
  "canal": "reel",
  "extraction": [
    {
      "type_contenu": "prompt",
      "nom": "Experimental Graphics posters — Apple-studies",
      "resume": "Graphic poster prompt (3×3 grid of interpretations of a red apple) on Recraft V4.1.",
      "substance_technique": {
        "modele_cible": "Recraft V4.1",
        "stack": [],
        "methode": "3×3 grid, varied graphic languages, white background.",
        "etapes": [],
        "placeholders": [],
        "details": "Readable excerpt; full prompt behind a paywall."
      },
      "citation_cle": "Experimental graphic-design poster ... nine interpretations of a red apple arranged in a 3×3 grid.",
      "liens": ["https://www.filatov.design"],
      "illustrations": ["_images/02 Apple-studies.jpg"],
      "themes": ["tech-ia"],
      "casquettes": [],
      "projets_lies": [],
      "categorie_vault": "Veille",
      "tags_extra": ["🤖/prompt", "🤖/ia"],
      "confiance": "haute"
    }
  ]
}
```

### Fields (per extraction entry)

| Field | Required | Notes |
|---|---|---|
| `type_contenu` | yes | vocabulary above |
| `nom` | yes | short, explicit note title |
| `resume` | yes | 3–4 sentences, oriented to "why I kept it" |
| `exploitation` | yes | 1–3 bullets: how the item feeds a role/project. Never empty: propose at least one concrete lead, else `—`. |
| `substance_technique` | yes | object: `modele_cible`, `stack[]`, `methode`, `etapes[]`, `placeholders[]`, `details` — fill what exists, leave the rest empty |
| `citation_cle` | no | 1 short verbatim sentence |
| `liens` | no | exact URLs cited |
| `illustrations` | no | paths of visuals kept in `_images/` |
| `themes` | yes | vocabulary of your taxonomy |
| `casquettes` / `projets_lies` | yes (may be `[]`) | don't invent: leave empty if unsure |
| `categorie_vault` | yes | `Prompt` · `Veille` · `Article` · `Livre` · `Fiche` |
| `dossier_cible` | no | path **forcing** the destination (takes precedence over auto-routing) |
| `tags_extra` | no | extra tags added to the base tags |
| `confiance` | yes | `haute` · `moyenne` · `basse` — `basse` ⇒ inbox |

## Normalization prompt

Apply per bundle (with the frame sheet in view when available):

```
You receive a SAVED INSTAGRAM ITEM: its caption, its audio transcript and the
visual reading of its key images. Your task: extract the USABLE SUBSTANCE, not
an entertainment summary.

1. Split into independent substances (0..n). One item may contain a tool AND a
   tip AND a reference → one entry per substance.
2. For each substance, pick `type_contenu` from the provided vocabulary.
3. Fill the schema fields. Invent NOTHING: if a technical detail isn't legible,
   leave the field empty and lower `confiance`.
4. `nom` = explicit title you could find again in 6 months.
5. `themes`: only the provided taxonomy vocabulary.
6. If no usable substance: {"extraction": []}.
7. Fill `exploitation`: propose 1–3 concrete uses (target role/project). It is an
   expected value-add — never leave it empty.

Constraints:
- Do not copy a paid asset wholesale: extract + link.
- Distinguish the model CITED from the model USED to produce the content.
- The transcript can be noisy: don't infer a tool name from a mis-transcribed
  word — if in doubt, cite the link and mark `confiance: basse`.

[CAPTION]     : ...
[TRANSCRIPT]  : ...
[SCREEN READ] : ...
[METADATA]    : author=..., date=..., url=...
```

## Quality check (before filing)

- [ ] Every `type_contenu` is in the vocabulary.
- [ ] Every `nom` is unique and explicit.
- [ ] No `themes` outside the taxonomy.
- [ ] `casquettes`/`projets_lies` empty when unsure.
- [ ] `confiance: basse` ⇒ destination the configured `inbox_dir`.
- [ ] An item already present (same normalized `nom`) will be merged, not duplicated.
