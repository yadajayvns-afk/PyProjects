# Bill Organizer

Drop a bill into `drop_bills/`, run one command, and it gets sorted into a
`<Month><Year>/<Category>/` folder with a line added to that month's expense CSV.

```
drop_bills/swiggy_receipt.pdf
        │
        ▼  uv run python main.py
output/
  May2026/
    Food/
      swiggy_receipt.pdf
    Fuel/
    expenseMay2026.csv      # bill_no, bill_date, amount, vendor, category, ...
```

## How it works

A [CrewAI **Flow**](https://docs.crewai.com/) orchestrates the pipeline; a
single-agent CrewAI **Crew** handles the one fuzzy step (reading messy OCR text
into structured fields). Everything else is deterministic Python.

1. **Detect** — find new bills in `drop_bills/` (`.pdf/.jpg/.jpeg/.png`),
   skipping duplicates by content hash.
2. **Read** — text-based PDFs are read directly with PyMuPDF; scanned PDFs and
   images fall back to Tesseract OCR.
3. **Extract** — a CrewAI agent pulls the fields listed in `config/fields.yaml`
   (bill number, date, amount, vendor).
4. **Categorize** — keyword rules in `config/categories.yaml` decide the
   category (Food, Fuel, ...).
5. **Organize & record** — the file is moved into
   `output/<Month><Year>/<Category>/` and a row is appended to
   `output/<Month><Year>/expense<Month><Year>.csv`.

Unreadable bills are quarantined in `archive/failed/` instead of crashing the run.

## Prerequisites

### Python packages
Managed with [uv](https://docs.astral.sh/uv/). Python is pinned to 3.13
(CrewAI does not yet support 3.14).

```sh
uv sync
```

### System tools (not pip-installable)
The OCR path needs two native programs on your `PATH`:

- **Tesseract OCR** — [UB Mannheim Windows build](https://github.com/UB-Mannheim/tesseract/wiki).
- **Poppler** — required by `pdf2image`; download Poppler for Windows and add
  its `bin/` folder to `PATH`.

If you only ever process text-based PDFs, these are not strictly required.

### LLM API key
Field extraction uses an LLM via [OpenRouter](https://openrouter.ai/).

```sh
copy .env.example .env
```

Then put your key in `.env`:

```
OPENROUTER_API_KEY=sk-or-...
```

Optionally override the model with `BILL_ORGANIZER_MODEL` (any OpenRouter model
string; default `openrouter/anthropic/claude-3.5-sonnet`).

## Usage

```sh
# Drop bills into drop_bills/ then:
uv run python main.py

# Options:
uv run python main.py --drop drop_bills --output output --archive archive/failed -v
```

The run processes everything currently in the drop folder, then exits.

## Configuration

- **`config/fields.yaml`** — which fields the extraction agent pulls out. Add a
  field here and it is extracted automatically.
- **`config/categories.yaml`** — category → vendor/text keyword rules. Categories
  are matched top-to-bottom; first hit wins; no hit → `Uncategorized`.

## Development

```sh
uv run pytest          # full suite (the LLM crew is stubbed in tests)
```

## Project layout

```
config/                       # user-editable YAML config
src/bill_organizer/
  flow.py                      # BillFlow -- orchestrates the pipeline
  models.py                    # Pydantic models (ExtractedBill, Flow state)
  config.py                    # load + validate YAML
  detect.py                    # step 1: find new bills, dedup
  text_extract.py              # step 2: PDF text / OCR
  categorize.py                # step 3b: keyword categorization
  organize.py                  # steps 4-5: move file + write CSV
  crews/extraction_crew.py     # step 3a: the single-agent extraction crew
main.py                        # CLI entrypoint
tests/                         # pytest suite
```
