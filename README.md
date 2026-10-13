**English** · [Français](README.fr.md)

# OpenCarnet

> Turns the Instagram reels and posts you save into a clean, organized notebook, instead of a long list of links you never reopen.

You save reels. They pile up. What you meant to keep gets lost: a tool, a tip, a place, a book, a prompt. It all ends up in a grid of thumbnails you stop scrolling. OpenCarnet collects that material and files it for you, into the notebook you already use (Obsidian, Notion, a plain notes folder).

> **A note from the author.** I have not tested this tool in its packaged form: it is derived from my own way of working, extracted and simplified. It is not perfect, and it can be improved. Rough edges may remain. I am open to any improvement suggestion.

## Why it works

A reel is not text. The useful information is spread across three places:

- what is said out loud,
- what is written on screen (text, interface, code),
- the caption.

OpenCarnet brings those three parts together, makes a readable note, and files it. It never files from the caption alone: without the sound and the image, you miss the point.

## How it runs

Three steps, one command each:

1. **Get the list** of everything you saved (from the official export of Instagram, X, TikTok, YouTube or LinkedIn, or a simple list of links).
2. **Read each item**: OpenCarnet downloads the video, transcribes what is said, and reads the text on screen.
3. **File it**: your AI assistant turns it into a short note (what it is, the useful details, a link to the original), then OpenCarnet files it in the right place, with no duplicates.

## What you need

- A Mac or Linux computer.
- An AI assistant you already use (Claude Code, Cursor, an extension for ChatGPT, etc.).
- Three free tools, one install command each (shown below).

No programming needed. You copy commands into a terminal, that's all.

## Not technical? Let your AI do it

OpenCarnet ships with instructions written for AI assistants (`SKILL.md`). So you can simply **hand the repo link to your AI** (Claude, ChatGPT, Cursor…) and ask it to explain, or to do it for you.

Example prompts:
- "Here is a GitHub project: [link]. Explain what it does and how to use it."
- "Install and set up this project for me, step by step."
- "Here are my Instagram and X exports. Set this project up and file my saves into my Obsidian notebook."

Put plainly: if you can copy a link, you can use OpenCarnet.

## Export your Instagram data

This is step 1, and the only manual one. You ask Instagram for a copy of your data, then collect the file.

Start here, because Instagram can take a few hours (sometimes a day or two) to prepare the file.

1. In the Instagram app: **Settings**, then **Accounts Center** (at the top).
2. **Your information and permissions** → **Export your information**.
3. **Create an export**, pick your profile, then **Export to device**.
4. Under content, choose **"Some of your information"** and tick only **Saved** (and, if you want, **Likes**). No need to export anything else.
5. **Format**: JSON. **Date range**: all time.
6. Start the export. Instagram emails you a link when it is ready.

Important: the download link **expires after a few days**. Download the file and keep it in your Documents.

You will get a folder containing `saved_posts.json` (your saves) and, if you ticked it, `liked_posts.json` (your likes). That is the folder you hand to OpenCarnet.

> If you only care about your saves, tick only **Saved**: the file that matters is `saved_posts.json`.

### And your X / Twitter data

Same idea for X (Twitter): download your data archive, and OpenCarnet pulls your likes and bookmarks from it.

1. On x.com: the **More** menu, then **Settings and privacy** → **Your account** → **Download an archive of your data**.
2. Confirm, then request the archive. X notifies you when it is ready (often within 24h).
3. Download the `.zip`. It contains a `data/` folder with your likes (`like.js`) and, if you use them, your bookmarks.

Then:

```bash
python3 scripts/parse_x_export.py "~/Downloads/twitter-archive.zip" --out items-x.csv
```

On X, most posts are text: the content is already in the export. So you can often skip the download and transcribe step and go straight to analysis.

### TikTok, LinkedIn, YouTube

Same idea on these platforms: ask for your data export, then OpenCarnet pulls the **save signals** (no watch history, no DMs). Each export is turned into the same list of saves:

```bash
python3 scripts/parse_tiktok_export.py "~/Downloads/tiktok-data.zip" --out items.csv
python3 scripts/parse_youtube_takeout.py "~/Downloads/takeout-XXXX.zip" --out items.csv
python3 scripts/parse_linkedin_export.py "~/Downloads/linkedin-archive.zip" --out items.csv
```

**TikTok**
1. Profile → menu ☰ → **Settings and privacy**.
2. **Account** → **Download your data**.
3. Choose "All data" (or at least **Activity**), format **JSON**.
4. Request it, then download within ~4 days. Your **favorites** are imported (add `--include-likes` for your likes too).

**LinkedIn** (desktop only)
1. **Me** icon → **Settings & Privacy**.
2. **Data Privacy** → **Download your data**.
3. Tick **Saved Items** → **Request archive**.
4. Download the file (link valid 72h). You get `Saved Items.csv` — links only, so these notes land in your "to review" folder.

**YouTube**
1. Go to `takeout.google.com`.
2. Deselect everything, then tick **YouTube and YouTube Music**.
3. Keep **playlists** (that is the save signal).
4. Create the export. Google emails you a link.

> These export screens change often. If a step looks different, tell your AI to
> adapt — the parsers are written to be tolerant to format changes.

## Getting started

```bash
# 0. get OpenCarnet
git clone https://github.com/LCQuentin/opencarnet
cd opencarnet

# 1. install the 3 free tools
brew install yt-dlp ffmpeg
python3 -m pip install --user faster-whisper "av==13.1.0"
python3 -m pip install --user instaloader

# 2. set it up — a few questions (your notes app, where notes go, language)
python3 scripts/compile.py --init

# 3. get the list of your saves
python3 scripts/parse_meta_export.py "~/Downloads/instagram-export/" --out items.csv
```

Then, for each item: OpenCarnet downloads it, transcribes it, assembles it, and your AI assistant turns it into a note. The full commands are further down, in "Going further".

## Where your notes go (settings)

OpenCarnet does not decide for you where notes go. You tell it, in **a small settings file** you write once.

You say, for example:
- the folder where notes go (Obsidian, Logseq, any Markdown folder…),
- how to name notes,
- which keywords to add,
- where to set aside uncertain notes.

`--init` writes that settings file for you from a **preset** (plain Markdown folder, Obsidian, or Logseq), and copies the note templates so you can edit them. Prefer to do it by hand? A neutral example is included (`config.example.json`) — copy and adapt it. Either way, OpenCarnet works with **any notebook**, without rewriting anything.

Rather have a table (a Notion database, Airtable, Google Sheets) than separate notes? Set `output` to `csv` or `jsonl` in the same file: your saves land in one spreadsheet-ready file instead.

### Notes shaped by what they contain

A recipe does not look like a tool, and a restaurant does not look like a book. OpenCarnet gives each kind its own layout:
- **recipe**: servings, prep / cook / total time, ingredients with quantities, tools, numbered steps;
- **place**: address, a ready-made **Google Maps link**, optional **GPS coordinates** (to see your places on a map);
- **web resource**: the tool's own link, pricing, platforms, what it does;
- **book**, **film / series**, **product** (with the date the price was seen).

Times and servings are real numbers, so you can filter ("recipes under 30 minutes"). Layouts are plain Markdown templates you can copy and change. Facts the AI could get wrong — coordinates, map links, totals — are computed, never guessed.

## How it compares

Most tools in this space are closed apps (Resurfy, SocialMarks, Recall, Fabric…) that file your saves **inside their app**, with a subscription. Others are open but can only file to **one place** (one specific notebook, one specific database).

OpenCarnet does it differently:
- **it files where you want** (Obsidian, Logseq, any Markdown folder),
- **it runs with your own AI assistant**, not a separate paid one,
- **no lock-in**: no account, no subscription,
- **everything stays with you**.

## What OpenCarnet does not do

- **Private or deleted** posts cannot be retrieved. They are simply skipped.
- If an item is unreadable (poor audio), the note is **set aside** rather than invented. It never guesses.
- OpenCarnet does not copy paid content: it keeps a link and a short quote.

## Going further

The technical details (full commands, the note format, advanced settings) are here:

- `reference/extraction-schema.md`: what each note contains.
- `reference/configuration.md`: every available setting.
- `scripts/`: the tools, one per step.
- `tests/`: the test suite — `python3 -m unittest discover -s tests -t .`.

## Roadmap

- [x] **X / Twitter**: your likes and bookmarks, same notes as Instagram.
- [x] **TikTok**: your favorites (likes optional).
- [x] **YouTube**: your playlists (Google Takeout).
- [x] **LinkedIn**: your saved items (imported as links to review).

Parsers and export steps are in place; each source is refined as real exports come in.

## License

MIT, see `LICENSE`.
