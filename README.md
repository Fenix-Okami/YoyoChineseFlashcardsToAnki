# YoYoChinese → Anki Exporter

Export your YoYoChinese flashcards to Anki — with audio, level subdecks, and a polished card template.

---

## What it does

- Fetches your YoYoChinese flashcards via the site API (requires your browser Cookie)
- Exports Anki‑friendly TSV files (`simple` 2‑field or `rich` 7‑field)
- Optionally downloads audio and references it in cards as `[sound:...]`
- Optionally builds a ready‑to‑import `.apkg` package (requires `genanki`)

---

## Prerequisites

- **Python 3.8+**
- **YoYoChinese account** with flashcards saved
- **Browser Cookie** for `yoyochinese.com` — copy it from DevTools → Network → any request to yoyochinese.com → Request Headers → `Cookie`. Keep this private.
- *(Optional)* `genanki` for `.apkg` output: `pip install genanki`

---

## Quick Start

```bash
# 1. Set up your environment
cp .env.example .env
#    → paste your cookie into YOYO_COOKIE inside .env

# 2. Extract flashcards (interactive course selection)
python yoyo_to_anki.py extract

# 3. Download audio + build rich TSV
python yoyo_to_anki.py enrich export/YoYoChinese_Beginner_Conversational/manifest.json

# 4. Build the .apkg
python yoyo_to_anki.py load export/YoYoChinese_Beginner_Conversational/manifest.json
```

---

## Setup

Copy `.env.example` to `.env` and fill in your values:

```ini
YOYO_COOKIE=your_cookie_value_here
YOYO_DECK_NAME=YoYoChinese
YOYO_OUTPUT=export
```

CLI arguments always override `.env` values when provided.

---

## ETL Steps

The pipeline is split into four independent steps. Run them in sequence or re-run any step in isolation.

### Step 1 — Extract

Fetches flashcards from the YoYoChinese API and writes `manifest.json`, `cards.json`, and `simple.tsv` for each partition.

```bash
# Interactive course selection (recommended for first run)
python yoyo_to_anki.py extract

# Non-interactive: specify course directly
python yoyo_to_anki.py extract --course-id beginner-conversational

# Quick test run (first 50 cards only)
python yoyo_to_anki.py extract --max 50

# Export with level subdecks
python yoyo_to_anki.py extract --levels-subdecks

# Filter to cards you're still learning
python yoyo_to_anki.py extract --mastery-type learning

# Split output by word type (words vs sentences)
python yoyo_to_anki.py extract --split-by-wordtype

# Combine filters
python yoyo_to_anki.py extract --course-id beginner-conversational --level-id 12345 --mastery-type all
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--cookie <value>` | `YOYO_COOKIE` | Browser Cookie for yoyochinese.com |
| `--deck-name <name>` | `YoYoChinese` | Deck name used for folder/file naming |
| `--output <dir>` | `export` | Root output directory |
| `--course-id <id>` | *(prompted)* | Skip interactive course prompt |
| `--level-id <id>` | — | Filter to a single level |
| `--unit-id <id>` | — | Filter to a single unit |
| `--lesson-id <id>` | — | Filter to a single lesson |
| `--mastery-type <type>` | `all` | `all` / `learning` / `mastered` |
| `--levels-subdecks` | off | Write one folder per Level |
| `--split-by-wordtype` | off | Separate folders for Word and Sentence cards |
| `--per-page <n>` | `50` | Cards per API page |
| `--max <n>` | — | Cap total cards fetched (testing) |
| `--delay <secs>` | `0.2` | Delay between API pages |

---

### Step 2 — Enrich

Downloads audio files and writes `rich.tsv` for each partition. Safe to re-run — already-downloaded audio is skipped.

```bash
# Standard enrich
python yoyo_to_anki.py enrich export/YoYoChinese_Beginner_Conversational/manifest.json

# Use more download workers for faster audio fetching
python yoyo_to_anki.py enrich export/YoYoChinese_Beginner_Conversational/manifest.json --audio-workers 16
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--audio-workers <n>` | `8` | Concurrent audio downloads (`YOYO_AUDIO_WORKERS`) |

---

### Step 3 — Transform *(placeholder)*

Reserved for future transformation logic. Currently a no-op.

```bash
python yoyo_to_anki.py transform export/YoYoChinese_Beginner_Conversational/manifest.json
```

---

### Step 4 — Load

Assembles an `.apkg` Anki package from the extracted data. Requires `genanki`.

```bash
# Build the package
python yoyo_to_anki.py load export/YoYoChinese_Beginner_Conversational/manifest.json

# Override the deck name shown inside Anki
python yoyo_to_anki.py load export/YoYoChinese_Beginner_Conversational/manifest.json \
  --deck-name "YoYoChinese Beginner Conversational"

# Write the .apkg to a custom path
python yoyo_to_anki.py load export/YoYoChinese_Beginner_Conversational/manifest.json \
  --apkg-path ~/Desktop/YoYo.apkg
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--deck-name <name>` | *(from manifest)* | Override the deck name used inside Anki |
| `--apkg-path <path>` | *(auto)* | Explicit output path for the `.apkg` file |

---

## Output Structure

```
export/
└── YoYoChinese_Beginner_Conversational/
    ├── manifest.json          ← links all partitions together
    └── levels/
        ├── level01/
        │   ├── cards.json     ← raw card data
        │   ├── simple.tsv     ← 2-field TSV (Front / Back)
        │   ├── rich.tsv       ← 7-field TSV (after enrich)
        │   └── media/         ← audio files (after enrich)
        └── level02/
            └── ...
```

The `.apkg` is written alongside the manifest: `export/YoYoChinese_Beginner_Conversational.apkg`

---

## Importing into Anki

1. **File → Import** and select the TSV or `.apkg`.
2. For `simple` format: map **Field 1 → Front**, **Field 2 → Back**.
3. For `rich` format: create/match a note type with 7 fields, or ignore extra columns.
4. For audio: if Anki doesn't auto‑detect the `media/` folder, copy those files into Anki's media collection folder (**Tools → Check Media** to verify).

---

## Tips

- Run `--max 50` first to verify your cookie and course selection before a full export.
- Use `--audio-speed slow` to reference the slow recordings instead of normal speed.
- Some cards may be missing audio — they import and display fine without it.
- Re-running `enrich` is safe and fast since existing audio files are skipped.

---

## Notes

- **WordType** uses labels: `Word` (single word/phrase) or `Sentence` (full sentence). The Mastery field was removed — Anki manages its own SRS.
- **Level mappings** are defined in `LEVEL_IDS_BY_COURSE` inside `yoyo_to_anki.py`. Add entries there for new courses; display names go in `COURSE_NAMES`.
- **`.apkg` uniqueness**: notes include a hidden `index` field (lesson/code) to prevent Anki duplicate warnings while keeping the visible front unchanged.
- **Card templates** are read from `anki_front_template.html`, `anki_back_template.html`, and `anki_style.css` colocated with the script (fallback: `tools/` subdirectory).
- If `--course-id` is omitted, the extract step prompts you interactively. Deck name auto-expands from `YoYoChinese` to `YoYoChinese <Course Name>` when a course is selected this way.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `401` / `403` errors | Cookie is missing or expired — grab a fresh value from the browser |
| Empty results | Check filters (`--course-id`, `--mastery-type`), or verify your account has saved flashcards |
| Missing `.apkg` | Install `genanki`: `pip install genanki` |
| Audio download failures | The script retries with exponential backoff. Re-running `enrich` resumes where it left off |
