---
name: opencarnet
description: Turn saved Instagram reels/posts (and X / Twitter likes & bookmarks, TikTok favorites, YouTube playlists, LinkedIn saved items) into structured, classified knowledge notes (destination and note format configurable — any Markdown notes app or a CSV/JSONL table). Extracts the substance (tool/service, skill, prompt, AI model, tip, reference) with technical details, routes each item via a config file, dedupes and updates the index. Use on "saved reels", "saved posts", "my Instagram saves", "Instagram backlog", a Meta export, "my TikTok favorites", a TikTok data export, "my YouTube likes / playlists", a Google Takeout, "my LinkedIn saved items", an X / Twitter archive, "my likes", "my bookmarks", a list of links or a folder of captures. FR — Transforme vos reels/posts Instagram enregistrés (et X / TikTok / YouTube / LinkedIn) en fiches de connaissance classées (destination configurable) ; utilisez sur "reels enregistrés", "favoris TikTok", "Takeout YouTube", "Saved Items LinkedIn", un export Meta, une archive X / Twitter, "mes J'aime", "mes signets".
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
brew install yt-dlp ffmpeg   # Linux: sudo apt install ffmpeg && pipx install yt-dlp
# Transcription (faster-whisper recommended: no torch dependency)
python3 -m pip install --user faster-whisper
python3 -m pip install --user "av==13.1.0"   # pin: faster-whisper breaks with av>=14 (metadata_errors)
# or: python3 -m pip install --user openai-whisper   # alternative (torch-based)
```

Destination and routing come from a **config file** (neutral): see
`reference/configuration.md` and `config.example.json`. No path is hardcoded in
the engine.

## Setup (once)

Create a working config without writing JSON by hand:

```bash
# guided (a few questions: notes app, destination, language, review folder)
python3 scripts/compile.py --init

# or non-interactive (for an AI assistant)
python3 scripts/compile.py --init --tool obsidian --language fr \
  --root ~/Documents/Obsidian --review-dir "OpenCarnet/to-review"
```

`--init` writes `~/.config/opencarnet/config.json` from a **preset**
(`plain-markdown`, `obsidian`, `logseq` — see `presets/`), copies the note
templates of the chosen language next to the config, and prints the next step.
Presets carry **no personal element**. Add `--force` to overwrite an existing
config. Messages and the generated prompt follow the chosen `language` (`en`|`fr`).

## Workflow

### 1. Ingest — build the item list

Several input modes, combinable. Always normalize to an item list (`items.csv`
or JSON) with at least a `url` or `id` key.

**A. Meta export ("Download your information")** — gives the exhaustive list of
saves (author, date, collection) but **not always the direct URL**.

```bash
python3 scripts/parse_meta_export.py "~/Downloads/instagram-xxx/" --out items.csv
```

> Known limit: depending on the export version, the *Saved* section holds the
> author and date, not always the permalink. Those items keep an empty `url`
> column and the script reports them as "to complete" (step 5) instead of
> letting them be analyzed blind. To complete them, see mode C.

**B. A list of links** (pasted by the user, or scraped by another tool) — the
most reliable mode. One link per line.

```bash
# items.csv with a url column
```

**C. Connected browser** — to recover missing permalinks, walk the "Saved" tab
with a driven browser and export the links, then switch to mode B.

**D. A folder of captures** (screen-recording, screenshots) — last resort, no
audio: skip transcription and analyze captures + caption.

**E. X / Twitter export** — same idea as the Meta export, for your likes and
bookmarks. X delivers a `.zip` whose `data/` folder holds small JS files
(`like.js`, `bookmarks.js`…). The parser normalizes them to the same item list.

```bash
python3 scripts/parse_x_export.py "~/Downloads/twitter-archive.zip" --out items.csv
```

> Only likes and bookmarks are kept; other archive files (DMs, deleted tweets,
> account…) are ignored. Add `--include-own-tweets` to also import your own posts.
>
> For X, most posts are text: the tweet text is already in the export, so you can
> often skip the download/transcribe step and analyze the text directly.

**F. TikTok export** ("Download your data", JSON) — **Favorite Videos** by default;
your **likes** are a weak, high-volume signal, opt-in only. Watch history, searches
and comments are ignored.

```bash
python3 scripts/parse_tiktok_export.py "~/Downloads/tiktok-data.zip" --out items.csv
# add --include-likes to also import your likes (collection: like)
```

**G. YouTube (Google Takeout)** — keep only the **playlists** (a save signal);
watch history is ignored.

```bash
python3 scripts/parse_youtube_takeout.py "~/Downloads/takeout-XXXX.zip" --out items.csv
```

> Playlist file/folder names are localized in Takeout: the parser recognizes them
> by structure (a video-id column **and** a "playlist" timestamp column), not by
> name. For long videos, prefer subtitles over Whisper (see step 2).

**H. LinkedIn archive** — `Saved Items.csv` holds **URL + date only** (no text).
These items are imported as **links to review**: the analysis is low-confidence by
construction, so `compile.py` sends them to the inbox. This is deliberate — never
file a note from a bare link.

```bash
python3 scripts/parse_linkedin_export.py "~/Downloads/linkedin-archive.zip" --out items.csv
```

All modes write the same pivot (`items.csv` + `items.json`), so steps 2–5 are
identical whatever the source. Only **save signals** are ingested — no watch
history, searches, DMs or private data. Parsers and `build_bundle.py` accept
`--language en|fr` (default: your config / `OPENCARNET_LANG` / system locale).

### 2. Enrich — download + transcribe + read the screen

For each item with a `url`:

```bash
# Download video + info.json (caption, author) + frame sheet
bash scripts/fetch_media.sh "https://www.instagram.com/reel/..." ./work/

# Transcribe audio (faster-whisper if available, else whisper CLI)
python3 scripts/transcribe.py ./work/<id>.m4a --out ./work/<id>.txt
```

> **Long videos (YouTube…).** Downloading a 30-minute video, transcribing it and
> reading 12 frames is slow and rarely useful. Fetch **subtitles first** — they
> become `<id>.txt` directly, no Whisper:
>
> ```bash
> bash scripts/fetch_media.sh "<url>" ./work --subs
> ```
>
> Fall back to the normal download only when no subtitle exists. Add
> `--no-frames` to skip the frame sheet when it adds nothing, and `--sub-langs`
> (default `en.*,fr.*`; e.g. `all,-live_chat`) to widen the subtitle languages.

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
The exact schema is in **`reference/extraction-schema.md`** (read before this
step). Get the prompt for the active config — vocabulary, themes and the user's
custom fields — with:

```bash
python3 scripts/compile.py --print-prompt
```

Then **validate** the analyses against the config before filing — unknown
`type_contenu`, themes outside the taxonomy, invalid `confiance`, unknown
`format`, computed values in `donnees`, wrong custom-field types. Each message
names the file and the extraction, so fix the JSON and re-run until it is clean:

```bash
python3 scripts/compile.py --check ./analyses/      # a file or a folder; writes nothing
```

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

# a whole folder of analyses at once (deduped across files; an unreadable
# JSON is reported, the others are still filed, exit code 1)
python3 scripts/compile.py --analysis ./analyses/

# or explicitly
python3 scripts/compile.py --analysis ./analyses/<id>.json --config ./config.json
```

The engine:
- **dedupes** by normalized name across `index.scan_dir` and `review_dir`: an
  existing note is never overwritten — the new source URL is appended to it
  (non-destructive merge) ;
- writes the note from the config's `frontmatter` and `route` ;
- adds the **index row** if a `moc` is configured ;
- shapes the note by **format** (recipe, place, web resource, book, film, product):
  its own properties and template, plus computed values (Google Maps link,
  optional GPS, total time, domain) — see `reference/formats.md` ;
- writes **one Markdown file per note** by default, or a single table
  (`"output": "csv"` / `"jsonl"`) for Notion / Airtable / Sheets — see
  `reference/configuration.md` (Output formats) ;
- sends `low-confidence` / URL-less items to `review_dir`.

### 5. Review & control

- **Low-confidence** or URL-less items go to the configured `review_dir` — never
  filed automatically.
- Produce a **digest note** for the batch: N items processed, breakdown by
  `type_contenu` and theme, duplicates detected, items to complete.
- Remind the **review**: notes arrive with the configured status (e.g.
  `status: to-review`); turning them into action remains a human gesture.

## Guardrails

- **Volume**: process in batches (10–25 items). Validate the schema on 3–5 real
  items before a 200-item batch.
- **Paths**: the analysis-driven `dossier_cible` is always **confined to `root`**
  (absolute path or `../` refused → the item goes to review). No AI-provided
  value can make the engine write outside your notes folder.
- **Nothing to file**: an extraction with no content — empty `resume`,
  `substance_technique`, `citation_cle` **and** format `donnees` — goes to
  `review_dir` even if the analysis claims high confidence. A bare `liens` alone
  (e.g. a LinkedIn link) is **not** content.
- **Language**: run the parsers and `build_bundle.py` with `--language fr|en`
  (or `OPENCARNET_LANG`), matching your config's `language`. The default follows
  your config (`$OPENCARNET_CONFIG`), then the system locale.
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
| `reference/configuration.md` | Config schema (routing, themes, frontmatter, custom fields, index) — neutral engine |
| `reference/formats.md` | Note formats (recipe, place…), template syntax, computed values |
| `formats/` · `templates/` | Provided formats and templates, FR and EN |
| `presets/` | Ready configs for `--init` (plain-markdown, obsidian, logseq) — no personal element |
| `config.example.json` | Neutral default config (no personal paths) |
| `scripts/_pivot.py` | Shared pivot helpers (canonical URLs, id, CSV+JSON output, recap) |
| `scripts/parse_meta_export.py` | Meta (Instagram) export → `items.csv` |
| `scripts/parse_x_export.py` | X / Twitter archive → `items.csv` |
| `scripts/parse_tiktok_export.py` | TikTok export → `items.csv` (favorites; `--include-likes`) |
| `scripts/parse_youtube_takeout.py` | Google Takeout (YouTube playlists) → `items.csv` |
| `scripts/parse_linkedin_export.py` | LinkedIn `Saved Items.csv` → `items.csv` (links to review) |
| `scripts/fetch_media.sh` | yt-dlp + ffmpeg: video, info.json, frame sheet (`--subs` for long videos) |
| `scripts/transcribe.py` | Whisper (faster-whisper or CLI) → `.txt` |
| `scripts/build_bundle.py` | caption + transcript + metadata → `bundle.md` |
| `scripts/compile.py` | Neutral config-driven engine: `--init` setup, writes/dedupes notes + index (`--analysis` file or folder), `--check`, `--print-prompt` |
| `scripts/templating.py` · `scripts/enrich.py` | Template engine · computed values (maps link, geocoding…) |
| `tests/` | Unit + end-to-end tests: `python3 -m unittest discover -s tests -t .` |
