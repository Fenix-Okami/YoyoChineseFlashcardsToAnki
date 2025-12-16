YoYoChinese → Anki Exporter

What it does
- Fetches your YoYoChinese flashcards via the site API (requires your browser Cookie).
- Exports an Anki‑friendly TSV file.
- Optionally downloads audio and references it in the TSV as `[sound:...]`.
 - Optionally builds an `.apkg` (requires `genanki`).

Prereqs
- Python 3.8+ (no external packages needed).
- Your logged‑in `Cookie` for yoyochinese.com (copied from your browser DevTools → Network → any request to yoyochinese.com → Request Headers → Cookie). Keep this private.

Usage
1) Create a `.env` file (recommended)

  Copy `.env.example` → `.env`, then paste your YoYoChinese cookie into `YOYO_COOKIE`.
  You can also set other defaults there (deck name, output folder, per-page, etc.).

2) Extract (fetch flashcards)

  python yoyo_to_anki.py extract --include-audio

  This writes a `manifest.json` under `export/<deck-slug>/manifest.json` along with per-partition outputs.

3) Enrich (optional: download audio + write rich.tsv)

  python yoyo_to_anki.py enrich export/<deck-slug>/manifest.json

  Note: `enrich` requires the manifest path produced by `extract`.

4) Load (optional: build an .apkg)

  python yoyo_to_anki.py load export/<deck-slug>/manifest.json

Notes
- CLI arguments override `.env` values when provided.
- If you omit `--course-id`, the extract step prompts you to select a course and:
  - Uses Level subdecks (`Level 1..N`) and writes per-level folders.
  - Deck name handling: if your deck name is exactly `YoYoChinese` (note the capitalization), it is auto-set to `YoYoChinese <Course Name>` (e.g., `YoYoChinese Beginner Conversational`).
- `--audio-workers` can be set via `YOYO_AUDIO_WORKERS` in `.env`.
- Use filters if needed: `--course-id`, `--level-id`, `--unit-id`, `--lesson-id`, `--mastery-type`.

Output
- TSV at `export/<deck-name>.<format>.tsv` (or two files when using `--split-by-wordtype`, or one per level when using `--levels-subdecks`)
 - If `--make-apkg`, an Anki package at `export/<apkg-base>.apkg` (see above) containing subdecks, fields, styling, and audio (when downloaded).
- Media (if `--include-audio`) in `export/media/` with filenames matching `[sound:...]` in TSV

Import into Anki
- File → Import → select the TSV.
- For `simple` format: map Field 1 → Front, Field 2 → Back.
- For `rich` format: create/match a note type with 7 fields or map the fields you want; extra TSV columns can be ignored.
- For audio: if Anki doesn’t auto‑detect the `export/media/` folder, copy those files into Anki’s media folder after importing (Anki → Tools → Check Media to verify).

Tips
- Use `--max 50` for a quick test run.
- Use `--audio-speed slow` to use the slow recording when available.
- Some entries may be missing audio; they will import fine without sound.

Notes
- The `WordType` column now uses labels: `Word` (single word/phrase) or `Sentence` (full sentence). The Mastery field was removed as Anki will manage its own SRS.
 - Level subdecks use a manual mapping of course → ordered level IDs defined in `LEVEL_IDS_BY_COURSE` inside `yoyo_to_anki.py`. Add entries there for future courses. Course display names are defined in `COURSE_NAMES`.
 - When building an `.apkg`, notes include a first field `index` (not shown on the card) containing the lesson/code. This makes the first field unique to prevent Anki duplicate warnings while keeping the visible front unchanged.
 - HTML/CSS templates are read from files colocated with the script (`anki_front_template.html`, `anki_back_template.html`, `anki_style.css`), with a fallback to the same filenames under `tools/` if present.

Troubleshooting
- 401/403 errors: your Cookie is likely missing/expired. Grab a fresh value from the browser.
- Empty results: adjust filters, or verify your account has flashcards on the site.
- Missing `.apkg`: install `genanki` → `pip install genanki`, then rerun with `--make-apkg`.
 - Audio download errors: the script automatically retries transient failures (e.g., SSL EOF) with exponential backoff and cleans up partial files. If specific files keep failing, you can rerun and it will skip any audio already downloaded.
