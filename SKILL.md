---
name: opencarnet
description: Turn saved Instagram reels/posts into structured, classified knowledge notes (destination configurable — Obsidian, Markdown, Notion/CSV). Extracts the substance (tool/service, skill, prompt, AI model, tip, reference) with technical details, routes each item via a config file, dedupes and updates the index. Use on "saved reels", "saved posts", "my Instagram saves", "Instagram backlog", a Meta export, a list of IG links or a folder of captures. FR — Transforme vos reels/posts Instagram enregistrés en fiches de connaissance classées (destination configurable). À utiliser sur "reels enregistrés", "posts sauvegardés", "mes sauvegardes Instagram", "traiter ma base Instagram", "backlog Instagram", un export Meta, une liste de liens IG ou un dossier de captures.
---

# OpenCarnet

Turn a **backlog of saved Instagram content** (reels, posts, carousels) into
**structured, filed knowledge notes** (destination configurable).

The hard part isn't filing — it's **ingestion**: a reel is not text. Its
substance lives in three layers that must be reassembled before any analysis:

| Layer | Source | Where it's captured |
|---|---|---|
| **Voice** | reel audio | transcription (Whisper) |
| **Screen** | on-screen text, UI, code, visuals | key-frame extraction → visual reading |
| **Text** | caption, author, hashtags | metadata (yt-dlp / export) |

Never file from the caption alone: first assemble a **bundle** (voice + screen +
text), then analyze it, then file it.

## Requirements

```bash
# Download + metadata + frames
brew install yt-dlp ffmpeg
# Transcription (faster-whisper recommended: no torch dependency)
python3 -m pip install --user faster-whisper
python3 -m pip install --user "av==13.1.0"   # pin: faster-whisper breaks with av>=14 (metadata_errors)
# or: python3 -m pip install --user openai-whisper   # alternative (torch-based)
```

Destination and routing come from a **config file** (neutral): see
`reference/configuration.md` and `config.example.json`. No path is hardcoded in
the engine.

## Workflow

### 1. Ingest — build the item list

Three input modes, combinable. Always normalize to an item list (`items.csv` or
JSON) with at least a `url` or `id` key.

**A. Meta export ("Download your information")** — gives the exhaustive list of
saves (author, date, collection) but **not always the direct URL**.

```bash
python3 scripts/parse_meta_export.py "~/Downloads/instagram-xxx/" --out items.csv
```

> Known limit: depending on the export version, the *Saved* section holds the
> author and date, not always the permalink. The script flags those items
> `url-missing` so they surface as "to complete" (step 5) instead of being
> analyzed blind. To complete them, see mode C.

**B. A list of links** (pasted by the user, or scraped by another tool) — the
most reliable mode. One link per line.

```bash
# items.csv with a url column
```

**C. Connected browser** — to recover missing permalinks, walk the "Saved" tab
with a driven browser and export the links, then switch to mode B.

**D. A folder of captures** (screen-recording, screenshots) — last resort, no
audio: skip transcription and analyze captures + caption.

### 2. Enrich — download + transcribe + read the screen

For each item with a `url`:

```bash
# Download video + info.json (caption, author) + frame sheet
bash scripts/fetch_media.sh "https://www.instagram.com/reel/..." ./work/

# Transcribe audio (faster-whisper if available, else whisper CLI)
python3 scripts/transcribe.py ./work/<id>.m4a --out ./work/<id>.txt
```

Then **read visually** the generated frame sheet (`<id>_sheet.jpg`) to recover
on-screen text (tool names, prompts, code, prices, UI). For carousels/posts, use
the caption + the downloaded slides.

> **Posts & carousels.** `yt-dlp` does not download a carousel's images.
> **Retained method (no session, no cookies)**: `instaloader` targeting the post
> shortcode directly:
>
> ```bash
> python3 -m instaloader --dirname-pattern="posts/{profile}" -- "-<SHORTCODE>"
> ```
>
> This fetches **all slides** of a **public** post (images + videos) without
> authentication — no account access, no cookies. Feed the resulting `.jpg`
> slides to the "read the screen" step.
>
> Limits: **private** or deleted posts fail (staying anonymous ⇒ skip those
> items). For a batch, loop with a rate-limit pause (`sleep` between posts;
> recent instaloader has no `--sleep` option). Fallback if a post truly resists:
> a browser session (`--load-cookies` / `--sessionfile`) — avoid unless needed.

Assemble everything into a bundle:

```bash
python3 scripts/build_bundle.py --work ./work --out ./bundles/
# → bundles/<id>.md : caption + transcript + metadata, ready to analyze
```

### 3. Analyze — apply the extraction schema

For each bundle, produce **one JSON extraction** with a controlled vocabulary.
The exact schema, the `type_contenu` vocabulary and the normalization prompt are
in **`reference/extraction-schema.md`** (read before this step).

Principle: a single item can hold several substances (e.g. a reel that cites a
tool **and** gives a tip) → allow several `extraction[]` per bundle, each routed
independently. `exploitation` (uses for a role/project) is filled automatically,
never left empty.

### 4. Compile — write the notes

Routing (type_contenu → folder + tags + index) is **not** in the code: it comes
from a **config file** (see **`reference/configuration.md`** and
`config.example.json`). The engine is therefore neutral and reusable.

```bash
# config is auto-detected (~/.config/opencarnet/config.json)
python3 scripts/compile.py --analysis ./analyses/<id>.json --dry-run
python3 scripts/compile.py --analysis ./analyses/<id>.json

# or explicitly
python3 scripts/compile.py --analysis ./analyses/<id>.json --config ./config.json
```

The engine:
- **dedupes** (normalized name already present → non-destructive merge) ;
- writes the note from the config's `frontmatter` and `route` ;
- adds the **index row** if a `moc` is configured ;
- sends `low-confidence` / URL-less items to `inbox_dir`.

### 5. Review & control

- **Low-confidence** or URL-less items go to the configured `inbox_dir` — never
  filed automatically.
- Produce a **digest note** for the batch: N items processed, breakdown by
  `type_contenu` and theme, duplicates detected, items to complete.
- Remind the **review**: notes arrive as `statut: À consulter`; turning them into
  action (`En cours` → `Opérationnel` → `Traité`) remains a human gesture.

## Guardrails

- **Volume**: process in batches (10–25 items). Validate the schema on 3–5 real
  items before a 200-item batch.
- **ToS / account**: downloading via an Instagram session is the user's
  responsibility. Never replay a bulk download from an account you don't own.
- **Copyright**: keep the **link** and a short quote; never copy a paid asset
  wholesale (extract + link).
- **Never invent**: if the technical substance isn't legible, say so
  (`confiance: basse`) instead of writing a plausible-but-false note.

## Skill files

| File | Role |
|---|---|
| `reference/extraction-schema.md` | Extraction schema + `type_contenu` vocabulary + normalization prompt |
| `reference/configuration.md` | Config schema (routing, themes, frontmatter, index) — neutral engine |
| `config.example.json` | Neutral default config (no personal paths) |
| `scripts/parse_meta_export.py` | Meta export → `items.csv` |
| `scripts/fetch_media.sh` | yt-dlp + ffmpeg: video, info.json, frame sheet |
| `scripts/transcribe.py` | Whisper (faster-whisper or CLI) → `.txt` |
| `scripts/build_bundle.py` | caption + transcript + metadata → `bundle.md` |
| `scripts/compile.py` | Neutral config-driven engine: writes/dedupes notes + index |
