# Document-parser

Convert **PDF** and **PPTX** slide decks to **LLM-ready Markdown** with zero
data loss — fully local, no API costs.

- **Engine**: [Docling](https://github.com/docling-project/docling) (IBM, MIT)
  for layout-aware extraction of text, tables, headings and pictures.
- **OCR**: Tesseract (free, offline) for text inside diagrams / screenshots.
- **PPTX speaker notes**: extracted via `python-pptx` and merged in as
  blockquote blocks per slide — Docling alone does not surface them, so
  this step is what guarantees zero data loss for PPTX input.
- **Output**: one `<stem>.md` file per document plus a `<stem>/assets/`
  directory containing all extracted images, referenced via relative paths.

## Install

```bash
# 1. Tesseract binary (one-time, system package).
sudo apt install -y tesseract-ocr            # Debian/Ubuntu
# brew install tesseract                     # macOS
# Optional language packs, e.g. Italian: tesseract-ocr-ita

# 2. Python package (editable for local dev).
pip install -e .
```

Python 3.10+ required.

## CLI

Four subcommands: `parse` (explicit file list), `excel` (workbooks → CSV),
`mirror` (walk a folder), and `zip` (archive a folder).

```bash
document-parser parse deck.pptx -o ./out
document-parser parse slides.pdf -o ./out --ocr --lang ita+eng
document-parser parse ./decks/*.pdf -o ./out --workers 4

# Excel → CSV: one CSV per worksheet, grouped under ./out/<stem>/.
document-parser excel report.xlsx -o ./out
document-parser excel ./books/*.xlsx -o ./out --workers 4 --sep ';'

# Mirror a whole tree: parse .pdf/.pptx, convert .xlsx/.xlsm/.xls to CSV,
# copy .docx/.doc/.html/.htm/.txt, skip everything else.
# Up-to-date outputs are skipped on re-runs.
document-parser mirror ./source_docs ./mirrored --lang ita+eng -v

# Archive a folder into <folder>.zip and delete the source, writing a
# <archive>.log of every file added. Use --keep to retain the folder.
document-parser zip ./mirrored
document-parser zip ./mirrored --keep -o backup.zip
```

`parse` flags:

| flag | default | description |
| --- | --- | --- |
| `--out`, `-o` | `./out` | Output directory. |
| `--ocr/--no-ocr` | on | Tesseract OCR for PDF (PPTX is structure-only). |
| `--lang`, `-l` | `eng` | Tesseract language(s), e.g. `ita+eng`. |
| `--images/--no-images` | on | Extract images into `<stem>/assets/`. |
| `--workers`, `-j` | `1` | Parallel workers for batch parsing. |
| `--verbose`, `-v` | off | Verbose logging. |

`excel` flags:

| flag | default | description |
| --- | --- | --- |
| `--out`, `-o` | `./out` | Output directory (CSVs land in `<out>/<stem>/`). |
| `--sep` | `,` | CSV field separator. |
| `--workers`, `-j` | `1` | Parallel workers for batch conversion. |
| `--verbose`, `-v` | off | Verbose logging. |

`zip` flags:

| flag | default | description |
| --- | --- | --- |
| `--out`, `-o` | `<folder>.zip` | Archive path. |
| `--keep/--delete` | `--delete` | Keep or delete the source folder after a clean archive. |
| `--verbose`, `-v` | off | Verbose logging. |

## Python API

```python
from document_parser import parse

result = parse("deck.pptx", out_dir="./out")
print(result.markdown_path, result.n_slides, result.has_notes)

# Lower-level helpers if you need fine-grained control:
from document_parser import parse_pdf, parse_pptx
parse_pdf("slides.pdf", out_dir="./out", ocr=True, lang="eng")
parse_pptx("deck.pptx", out_dir="./out")

# Excel → CSV (one CSV per worksheet):
from document_parser import convert_excel
xls = convert_excel("report.xlsx", out_dir="./out")
print(xls.out_subdir, xls.n_sheets, xls.csv_paths)
```

`ParseResult` exposes `markdown_path`, `assets_dir`, `n_slides`,
`has_notes`, and `warnings`.

## Output format

Each output Markdown file looks like:

```markdown
---
source: deck.pptx
n_slides: 12
parsed_at: 2026-05-06T17:05:13+00:00
ocr_enabled: false
ocr_lang: n/a
generator: document-parser
---

## Slide 1

Title

- bullet 1
- bullet 2

> **Speaker notes:**
> Speaker notes for this slide go here.

## Slide 2

| Metric | Value |
|--------|-------|
| MAU    | 12,400 |

![Image](deck/assets/slide-002-01-28ca76fb84a7.png)
```

Front-matter exposes provenance / OCR settings to downstream LLM
pipelines, the `## Slide N` heading anchors each slide for retrieval,
and images live next to the Markdown so the file is portable.

## How "zero data loss" works

| Aspect | Source | Where it lands in MD |
| --- | --- | --- |
| Slide titles, paragraphs, bullets | Docling | Body of `## Slide N`. |
| Tables (with structure) | Docling | GFM tables. |
| Embedded pictures | Docling → `picture.get_image()` | Files in `<stem>/assets/`, linked inline. |
| Text inside images / diagrams (PDF) | Tesseract via Docling pipeline | Inline text on the slide. |
| **PPTX speaker notes** | `python-pptx` (separate pass) | `> **Speaker notes:**` blockquote per slide. |
| Slide order | Docling page numbers | One `## Slide N` per page. |

## First PDF run downloads models

Docling downloads layout / table-structure model weights from Hugging Face
on the first PDF parse (~hundreds of MB, cached under
`~/.cache/docling/models/`). To prefetch in CI:

```bash
docling-tools models download layout tableformer
```

PPTX parsing is offline-only (no models required).

## Development

```bash
pip install -e '.[dev]'
pytest -q
ruff check src tests
```

`tests/conftest.py` regenerates `tests/fixtures/sample.pptx`,
`sample.pdf`, and `sample.xlsx` on demand. The PDF integration test is
skipped automatically when the Docling models cannot be fetched (e.g.
offline CI).

## License

MIT.
