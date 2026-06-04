from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from document_parser.cli import app


def test_cli_pptx(tmp_path: Path, sample_pptx: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["parse", str(sample_pptx), "-o", str(tmp_path), "--no-ocr"],
    )
    assert result.exit_code == 0, result.output
    out_md = tmp_path / "sample.md"
    assert out_md.exists()
    md = out_md.read_text(encoding="utf-8")
    assert "## Slide 1" in md
    assert "**Speaker notes:**" in md


def test_cli_unsupported(tmp_path: Path) -> None:
    bogus = tmp_path / "doc.txt"
    bogus.write_text("nope")
    runner = CliRunner()
    result = runner.invoke(
        app, ["parse", str(bogus), "-o", str(tmp_path), "--no-ocr"]
    )
    assert result.exit_code != 0
