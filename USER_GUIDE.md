# Document Parser — User Guide

> Convert PDF and PPTX slide decks to LLM-ready Markdown — fully local, no API costs.

## Table of Contents

- [Part I — Getting Started](#part-i--getting-started)
  - [What is document-parser?](#what-is-document-parser)
  - [Installation](#installation)
  - [Your first parse](#your-first-parse)
- [Part II — CLI Reference](#part-ii--cli-reference)
  - [parse](#parse)
  - [excel](#excel)
  - [mirror](#mirror)
  - [zip](#zip)
  - [Output format explained](#output-format-explained)
- [Part III — Using with Claude](#part-iii--using-with-claude)
  - [The golden rule](#the-golden-rule)
  - [Workflow recipe 1: mirror → read → ask](#workflow-recipe-1-mirror--read--ask)
  - [Workflow recipe 2: run inline in Claude Code](#workflow-recipe-2-run-inline-in-claude-code)
  - [Prompt templates](#prompt-templates)
  - [Python API + Anthropic SDK pipeline](#python-api--anthropic-sdk-pipeline)

---

## Part I — Getting Started

### What is document-parser?

**document-parser** converts PDF and PPTX slide decks into clean, structured Markdown files
that are immediately ready for LLM workflows. It runs entirely on your machine — no cloud API,
no per-page costs, no data leaving your environment.

Key features at a glance:

| Feature | Detail |
|---------|--------|
| **Formats** | PDF, PPTX (parse); XLSX/XLS/XLSM (excel); DOCX/HTML/TXT (mirror copies verbatim) |
| **Engine** | [Docling](https://github.com/docling-project/docling) (IBM, MIT licence) for layout-aware extraction |
| **OCR** | Tesseract — reads text inside diagrams, screenshots, and scanned slides |
| **Speaker notes** | Extracted via `python-pptx` and merged as blockquotes — zero data loss |
| **Output** | One `.md` file per document + `<stem>/assets/` directory for images |
| **Excel** | Each worksheet becomes a separate CSV — no float coercion, no `NaN` |
| **Batch** | `mirror` walks any folder tree recursively and is resumable |
| **Archive** | `zip` packages a converted output tree and optionally deletes the source |

---

### Installation

#### 1. Install Tesseract

Tesseract is a free OCR engine required for reading text inside images. Install it once at
the system level.

**Windows**

Download and run the installer from the
[UB-Mannheim release page](https://github.com/UB-Mannheim/tesseract/wiki).
During install, tick the language packs you need (e.g. Italian). After install, make sure
the `tesseract` binary is on your `PATH` — open a new terminal and run `tesseract --version`
to verify.

**macOS**

```bash
brew install tesseract
brew install tesseract-lang   # optional: installs all language packs
```

**Linux (Debian/Ubuntu)**

```bash
sudo apt install -y tesseract-ocr
sudo apt install -y tesseract-ocr-ita   # add language packs as needed
```

Run `tesseract --list-langs` to see which languages are installed.

#### 2. Install the Python package

Python 3.10 or later is required.

```bash
# Clone the repository, then from the repo root:
pip install -e .            # standard install
pip install -e '.[dev]'     # includes pytest and ruff for development
```

#### 3. Download Docling models (first PDF run only)

The first time you parse a PDF, Docling downloads its layout and table-structure model
weights from Hugging Face (~several hundred MB, cached under `~/.cache/docling/models/`).
This is a one-time cost. To prefetch in advance or in a CI environment:

```bash
docling-tools models download layout tableformer
```

**PPTX parsing is fully offline** — no model download required.

---

### Your first parse

**Parse a PPTX file**

```bash
document-parser parse my-deck.pptx -o ./output
```

This creates:

```
output/
├── my-deck.md                              ← the Markdown file you feed to Claude
└── my-deck/
    └── assets/
        ├── slide-001-01-a3f8c12b4d56.png
        └── slide-002-01-9e1f47c83a21.png
```

**Parse a PDF with multi-language OCR**

```bash
document-parser parse report.pdf -o ./output --ocr --lang ita+eng
```

**Parse a folder of decks in parallel**

```bash
document-parser parse ./decks/*.pptx -o ./output --workers 4
```

Once the `.md` file is on disk, open it in any text editor or feed it to Claude — that
single file contains everything: all slide text, tables, speaker notes, and image references
in document order.

---

## Part II — CLI Reference

### parse

Converts one or more PDF or PPTX files to Markdown.

```bash
document-parser parse [OPTIONS] INPUTS...
```

**Arguments**

| Argument | Description |
|----------|-------------|
| `INPUTS` | One or more `.pdf` or `.pptx` file paths. Glob patterns work (e.g. `./decks/*.pdf`). |

**Options**

| Flag | Default | Description |
|------|---------|-------------|
| `--out`, `-o` | `./out` | Output directory. Created automatically if it doesn't exist. |
| `--ocr` / `--no-ocr` | `--ocr` (on) | Enable Tesseract OCR. For PDFs, OCR is applied during the full Docling layout pipeline. For PPTX, OCR runs on each extracted slide image. |
| `--lang`, `-l` | `eng` | Tesseract language code(s). Combine multiple with `+`: `ita+eng`, `fra+eng`. Run `tesseract --list-langs` to see available codes. |
| `--images` / `--no-images` | auto | Extract slide images to `<stem>/assets/` and link them inline in the Markdown. **Default coupling**: when `--ocr` is on, images default to off (OCR text replaces them, producing smaller and cleaner LLM input); when `--no-ocr`, images default to on. Pass the flag explicitly to override. |
| `--workers`, `-j` | `1` | Number of parallel workers for batch processing. 2–4 is a good starting point; very large PDFs may exhaust RAM at higher counts. |
| `--verbose`, `-v` | off | Print per-file progress and settings. |

**Examples**

```bash
# Single PPTX, defaults (OCR on, images off, output in ./out)
document-parser parse deck.pptx

# Specify output directory
document-parser parse deck.pptx -o ./markdown

# PDF with Italian + English OCR
document-parser parse report.pdf --ocr --lang ita+eng -o ./out

# Keep images AND OCR text side by side
document-parser parse deck.pptx --ocr --images -o ./out

# Batch: all PDFs in a folder, 4 parallel workers, verbose
document-parser parse ./decks/*.pdf -o ./out --workers 4 -v

# PPTX with no OCR — good for text-only decks with no image content
document-parser parse deck.pptx --no-ocr -o ./out
```

**Exit codes**: `0` on full success, `1` if any file failed (all other files still complete).

---

### excel

Converts Excel workbooks to CSV — one CSV per worksheet.

```bash
document-parser excel [OPTIONS] INPUTS...
```

**Arguments**

| Argument | Description |
|----------|-------------|
| `INPUTS` | One or more `.xlsx`, `.xlsm`, or `.xls` file paths. |

**Options**

| Flag | Default | Description |
|------|---------|-------------|
| `--out`, `-o` | `./out` | Output directory. CSVs land in `<out>/<stem>/`. |
| `--sep` | `,` | CSV field separator. Use `';'` for European locales. |
| `--workers`, `-j` | `1` | Parallel workers for batch conversion. |
| `--verbose`, `-v` | off | Verbose logging. |

**Output layout**

```
out/
└── report/                ← one subfolder per workbook (stem of the filename)
    ├── summary.csv        ← one CSV per worksheet (sheet name is slugified)
    ├── data.csv
    └── raw-numbers.csv
```

Cells are always read as strings. Blank cells become empty strings — never `"nan"`. This
makes the CSVs safe to paste into a prompt or load with any CSV reader without type
surprises.

Single-sheet workbooks still get their own `<stem>/` subfolder so the layout is uniform
across the whole output tree.

**Examples**

```bash
# Single workbook
document-parser excel report.xlsx -o ./out

# Semicolon separator (common in Italy/Europe)
document-parser excel report.xlsx -o ./out --sep ';'

# Batch: all workbooks, 4 workers
document-parser excel ./books/*.xlsx -o ./out --workers 4
```

---

### mirror

Walks an entire source folder tree and mirrors it to a destination, processing each file
type correctly.

```bash
document-parser mirror [OPTIONS] SRC DST
```

**This is the primary entry point for multi-document batch work.**

**Arguments**

| Argument | Description |
|----------|-------------|
| `SRC` | Source folder to scan recursively. |
| `DST` | Destination folder (created if it doesn't exist). |

**Options**

| Flag | Default | Description |
|------|---------|-------------|
| `--ocr` / `--no-ocr` | `--ocr` (on) | OCR setting applied to all parsed files. |
| `--lang`, `-l` | `eng` | Tesseract language(s) for OCR. |
| `--images` / `--no-images` | auto | Image extraction (same auto-coupling as `parse`). |
| `--verbose`, `-v` | off | Print verbose per-file progress, including skipped and ignored files. |

**What mirror does with each file type**

| Extension | Action |
|-----------|--------|
| `.pdf`, `.pptx` | Parsed → `<stem>.md` + `<stem>/assets/` in the mirrored location |
| `.xlsx`, `.xlsm`, `.xls` | Converted → `<stem>/` subfolder of CSVs |
| `.docx`, `.doc`, `.html`, `.htm`, `.txt` | Copied verbatim to the same relative path |
| Everything else | Silently ignored (shown with `-v`) |

**Resumability**: mirror checks whether the output file is newer than the source. If it is,
the file is skipped without reprocessing. Large re-runs (after adding a few new files to a
big folder) complete almost instantly.

**Summary line**: mirror always prints a final count:

```
Done. parsed=12 excel=3 copied=8 skipped=45 ignored=7 failed=0
```

**Examples**

```bash
# Mirror a full folder tree with defaults
document-parser mirror ./source_docs ./mirrored

# With Italian + English OCR, verbose
document-parser mirror ./source_docs ./mirrored --lang ita+eng -v

# Re-run after adding new files — only new/changed files are processed
document-parser mirror ./source_docs ./mirrored --lang ita+eng
```

**Exit code**: `1` if any file failed; all other files are still processed to completion.

---

### zip

Archives a folder into a `.zip` file and optionally deletes the source.

```bash
document-parser zip [OPTIONS] FOLDER
```

Typical use: archive a `mirror` output tree for long-term storage or sharing.

**Arguments**

| Argument | Description |
|----------|-------------|
| `FOLDER` | The folder to archive. |

**Options**

| Flag | Default | Description |
|------|---------|-------------|
| `--out`, `-o` | `<folder>.zip` | Archive path. Defaults to `<folder>.zip` placed alongside the folder. |
| `--keep` / `--delete` | `--delete` | Keep or delete the source folder. The source is **only deleted when there are zero errors**. |
| `--verbose`, `-v` | off | Print each file as it is added to the archive. |

**Log file**: `zip` always writes a `<archive>.log` next to the archive listing every added
file and any errors. The log survives even after the source folder is deleted — useful for
audit trails.

**Examples**

```bash
# Archive and delete source (default behaviour)
document-parser zip ./mirrored

# Archive but keep source intact
document-parser zip ./mirrored --keep

# Custom archive path
document-parser zip ./mirrored -o ./backup/2026-06-04-mirrored.zip

# Verbose: print each file as it is zipped
document-parser zip ./mirrored -v
```

---

### Output format explained

Every `.md` file written by `parse` or `mirror` has the same structure:

```markdown
---
source: deck.pptx
n_slides: 12
parsed_at: 2026-05-06T17:05:13+00:00
ocr_enabled: true
ocr_lang: ita+eng
generator: document-parser
---

## Slide 1

Title of the first slide

- Bullet point one
- Bullet point two

> **Speaker notes:**
> Notes written by the presenter for this slide are here as a blockquote.

## Slide 2

| Metric | Value  |
|--------|--------|
| MAU    | 12,400 |

## Slide 3

![Image](deck/assets/slide-003-01-28ca76fb84a7.png)
```

**YAML frontmatter** — Exposes provenance and OCR settings. Useful for filtering or routing
in automated LLM pipelines (e.g. "only process files where `ocr_enabled: true`").

**`## Slide N` headings** — Each slide gets its own level-2 heading. This lets you target
specific slides in a prompt ("look at Slide 4") or split the file programmatically by
heading.

**Speaker notes** — Extracted via a separate `python-pptx` pass and appended as a
`> **Speaker notes:**` blockquote immediately after the corresponding slide body. This is
the mechanism that guarantees zero data loss for PPTX files — Docling alone does not surface
speaker notes.

**Images** — Named `slide-{page:03d}-{index:02d}-{sha1[:12]}.png` under `<stem>/assets/`.
The SHA-1 prefix makes filenames content-addressed: re-running parse on the same file
produces identical filenames for identical images.

**Tables** — Rendered as GitHub-Flavored Markdown (GFM) tables, which Claude and most
Markdown renderers read natively.

**OCR / images trade-off** — When OCR is enabled, extracted text replaces image placeholders
in the Markdown body. This produces smaller files that are easier for Claude to reason over.
When OCR is disabled, images are embedded as inline references. Passing `--ocr --images`
together includes both OCR text and the image reference side by side.

---

## Part III — Using with Claude

### The golden rule

> **Never load raw PDF or PPTX files into Claude. Always run `document-parser` first and
> feed Claude the `.md` output.**

Loading a raw slide deck into a Claude conversation:

- Burns context tokens on binary data Claude cannot parse efficiently
- Loses speaker notes, OCR'd image text, and table structure entirely
- Produces worse answers than feeding structured Markdown

The correct workflow is always: **CLI first → Markdown on disk → read only the `.md` into
Claude**.

---

### Workflow recipe 1: mirror → read → ask

This is the recommended pattern for working with a folder of documents in Claude Code.

**Step 1 — Convert everything**

```bash
document-parser mirror ./source_docs ./mirrored --lang ita+eng -v
```

This produces a `./mirrored/` tree with one `.md` per slide deck and one CSV subfolder per
workbook. Subsequent runs skip files that are already up to date.

**Step 2 — Read only what you need**

In Claude Code, read a specific output file:

```
Read ./mirrored/Q1-results.md
```

The Markdown is small enough that a 30-slide deck fits comfortably in a single Claude
context window.

**Step 3 — Ask your question**

Because the Markdown is structured — YAML frontmatter, `## Slide N` headings, GFM tables,
speaker notes as blockquotes — Claude can answer precise questions:

```
What are the key KPIs mentioned in Slide 5?
Include any numbers from the speaker notes.
```

```
Which slides contain a table? Summarize each table in one sentence.
```

```
List every person or team mentioned in the speaker notes across all slides.
```

---

### Workflow recipe 2: run inline in Claude Code

When you're already in a Claude Code session, run `document-parser` without leaving the
conversation using the `!` prefix. The command executes in the current terminal session and
its output appears directly in the conversation.

**Convert a single new file inline**

```
! document-parser parse ./new-deck.pptx -o ./out --lang ita+eng
```

Then immediately read and query the output:

```
Read ./out/new-deck.md
Summarize this deck in 5 bullet points and extract all action items.
```

**Batch mirror inline**

```
! document-parser mirror ./source_docs ./mirrored --lang ita+eng -v
```

Once it completes, pick any output file:

```
Read ./mirrored/subfolder/presentation-name.md
What conclusions does this deck reach?
```

**Why this works well**: you never leave the Claude Code context. The `!` command runs in
the same shell session, so relative paths resolve correctly and you can immediately read the
output file in the next message.

---

### Prompt templates

These are ready-to-use prompts. Read the relevant `.md` file first, then paste the prompt.

---

**Summarize a deck**

```
You have been given the full text of a slide deck converted to Markdown.
Summarize it in 5–7 bullet points. Focus on:
1. The main argument or purpose of the deck
2. Key data points, metrics, or findings (include exact numbers)
3. Any conclusions or recommendations

Use only information from the document. Do not add assumptions.
```

---

**Extract action items**

```
Read the slide deck Markdown and extract every action item, task, or next
step mentioned — in the slide body OR in the speaker notes.

For each action item output:
- Action: [what needs to be done]
- Owner: [person or team, if mentioned — otherwise "not specified"]
- Deadline: [date or timeframe, if mentioned — otherwise "not specified"]
- Slide: [slide number where it appears]

List items in slide order.
```

---

**Compare two decks**

```
You have been given two slide deck Markdowns. Compare them on these dimensions:
1. Main thesis or purpose
2. Key metrics or KPIs presented (list with values)
3. Conclusions and recommendations
4. Tone and intended audience

For each dimension, note agreements, contradictions, or gaps between the two
decks. Output a structured comparison table followed by a short paragraph
synthesis.
```

---

**Deep Q&A over a document**

```
I will ask you questions about the document you just read. Answer only from
the document. If the answer is not present, say so explicitly — do not guess.

When citing text, include the slide number (e.g. "Slide 3 states: ...").
```

---

**Extract and structure all tables**

```
Find every Markdown table in this document. For each table:
1. State which slide it is on
2. Give it a short descriptive title based on its content
3. Reproduce the table exactly
4. Write one sentence interpreting what the table shows

Output all tables in slide-number order.
```

---

**Translate speaker notes**

```
Extract every speaker notes block from this Markdown (they appear as
"> **Speaker notes:**" blockquotes). Translate each one to English.
Output in this format:

Slide N:
[translated notes]

Skip slides with no speaker notes.
```

---

### Python API + Anthropic SDK pipeline

For automated pipelines — processing many documents without manual steps — combine the
`document_parser` Python API with the Anthropic SDK.

**Install the Anthropic SDK**

```bash
pip install anthropic
```

---

**Basic pipeline: parse a deck and send to Claude**

```python
import anthropic
from document_parser import parse

# 1. Convert the deck to Markdown
result = parse("./decks/Q1-results.pptx", out_dir="./out", lang="ita+eng")
markdown = result.markdown_path.read_text(encoding="utf-8")

# 2. Ask Claude about it
client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": (
                f"Here is a slide deck converted to Markdown:\n\n{markdown}\n\n"
                "Summarize the key findings in 5 bullet points."
            ),
        }
    ],
)

print(response.content[0].text)
```

---

**Batch pipeline: mirror a folder, then summarize every Markdown**

```python
import subprocess
import anthropic
from pathlib import Path

# 1. Mirror the source folder (resumable — safe to re-run)
subprocess.run(
    ["document-parser", "mirror", "./source_docs", "./mirrored", "--lang", "ita+eng"],
    check=True,
)

# 2. Find all generated Markdown files
md_files = list(Path("./mirrored").rglob("*.md"))

client = anthropic.Anthropic()
summaries: dict[str, str] = {}

for md_path in md_files:
    markdown = md_path.read_text(encoding="utf-8")
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Slide deck Markdown:\n\n{markdown}\n\n"
                    "Give a 3-sentence executive summary. Be factual and concise."
                ),
            }
        ],
    )
    summaries[md_path.stem] = response.content[0].text
    print(f"[OK] {md_path.name}")

# 3. Write all summaries to a single report
report_lines = [f"## {stem}\n\n{text}" for stem, text in summaries.items()]
Path("./summaries.md").write_text("\n\n".join(report_lines), encoding="utf-8")
print("Summaries written to summaries.md")
```

---

**With prompt caching (recommended for repeated queries on large documents)**

When you query the same document multiple times, use Anthropic's prompt caching to avoid
re-sending the full Markdown on every call. The document is sent once and cached for up to
5 minutes; subsequent calls reuse the cache, cutting both latency and token cost.

```python
import anthropic
from document_parser import parse

result = parse("./decks/Q1-results.pptx", out_dir="./out")
markdown = result.markdown_path.read_text(encoding="utf-8")

client = anthropic.Anthropic()


def ask(question: str) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": (
                    "You are a document analyst. "
                    "Answer only from the provided document. "
                    "Quote slide numbers when relevant."
                ),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Document:\n\n{markdown}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": question,
                    },
                ],
            }
        ],
    )
    return response.content[0].text


# First call: full processing. Subsequent calls within 5 min: cached.
print(ask("What is the main KPI highlighted in this deck?"))
print(ask("Which slide contains the revenue forecast?"))
print(ask("Are there any risks mentioned in the speaker notes?"))
```

---

**Lower-level API reference**

```python
from document_parser import parse_pdf, parse_pptx, convert_excel, ParseResult, ExcelResult

# PDF with OCR + images both enabled
result: ParseResult = parse_pdf(
    "slides.pdf",
    out_dir="./out",
    ocr=True,
    lang="ita+eng",
    with_images=True,
)
print(f"Slides: {result.n_slides}")
print(f"Has speaker notes: {result.has_notes}")
print(f"Warnings: {result.warnings}")
print(f"Markdown: {result.markdown_path}")
print(f"Assets: {result.assets_dir}")

# PPTX (no OCR — fast, offline)
result: ParseResult = parse_pptx("deck.pptx", out_dir="./out")

# Excel workbook with semicolon separator
xls: ExcelResult = convert_excel("report.xlsx", out_dir="./out", sep=";")
print(f"Sheets: {xls.n_sheets}")
print(f"CSV paths: {xls.csv_paths}")
```

`ParseResult` fields:

| Field | Type | Description |
|-------|------|-------------|
| `source` | `Path` | Input file path |
| `markdown_path` | `Path` | Path to the written `.md` file |
| `assets_dir` | `Path` | Path to the `<stem>/assets/` directory |
| `n_slides` | `int` | Number of slides parsed |
| `has_notes` | `bool` | Whether any speaker notes were found (PPTX only) |
| `warnings` | `list[str]` | Non-fatal warnings from the parse |

`ExcelResult` fields:

| Field | Type | Description |
|-------|------|-------------|
| `source` | `Path` | Input file path |
| `out_subdir` | `Path` | Path to the `<out>/<stem>/` subfolder |
| `csv_paths` | `list[Path]` | Paths to every CSV written |
| `n_sheets` | `int` | Number of worksheets converted |
| `warnings` | `list[str]` | Non-fatal warnings |

---

*Generated with [document-parser](https://github.com/lorenzo2706/document-parser) — MIT licence.*
