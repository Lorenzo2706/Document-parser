"""Excel → CSV conversion: one CSV per worksheet, grouped under ``<stem>/``.

Unlike the slide backends this path does not touch Docling or ``md_writer`` — a
workbook is read with pandas and each sheet is written verbatim to a CSV. Cells
are read as strings (``dtype=str``) and blanks are emptied (``fillna("")``) so
nothing is coerced to floats and blank cells don't become ``"nan"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from document_parser.utils import doc_stem, ensure_dir, slugify


@dataclass(slots=True)
class ExcelResult:
    source: Path
    out_subdir: Path
    csv_paths: list[Path]
    n_sheets: int
    warnings: list[str] = field(default_factory=list)


def convert_excel(
    input_path: str | Path,
    *,
    out_dir: str | Path,
    stem: str | None = None,
    sep: str = ",",
) -> ExcelResult:
    """Convert every worksheet of ``input_path`` to a CSV under ``out_dir/<stem>/``.

    Returns an :class:`ExcelResult`. A workbook with one sheet still gets its own
    ``<stem>/`` subfolder so the layout is uniform and predictable.
    """
    input_path = Path(input_path)
    out_dir = Path(out_dir)
    stem = stem or doc_stem(input_path)

    # sheet_name=None → ordered dict of {sheet_name: DataFrame}.
    sheets = pd.read_excel(input_path, sheet_name=None, dtype=str)

    target = ensure_dir(out_dir / stem)
    csv_paths: list[Path] = []
    used: set[str] = set()
    for name, df in sheets.items():
        base = slugify(name)
        slug = base
        n = 2
        while slug in used:  # disambiguate sheets that slugify identically
            slug = f"{base}-{n}"
            n += 1
        used.add(slug)
        csv_path = target / f"{slug}.csv"
        df.fillna("").to_csv(csv_path, index=False, sep=sep)
        csv_paths.append(csv_path)

    return ExcelResult(
        source=input_path,
        out_subdir=target,
        csv_paths=csv_paths,
        n_sheets=len(csv_paths),
    )
