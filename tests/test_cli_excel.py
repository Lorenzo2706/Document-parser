"""Smoke tests for the `document-parser excel` subcommand."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from document_parser.cli import app


def test_excel_multi_sheet(tmp_path: Path, sample_xlsx: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["excel", str(sample_xlsx), "-o", str(tmp_path)])
    assert result.exit_code == 0, result.output

    subdir = tmp_path / "sample"
    metrics = subdir / "metrics.csv"
    roadmap = subdir / "roadmap.csv"
    assert metrics.exists()
    assert roadmap.exists()

    metrics_text = metrics.read_text(encoding="utf-8")
    assert "Metric" in metrics_text and "MAU" in metrics_text
    roadmap_text = roadmap.read_text(encoding="utf-8")
    assert "Quarter" in roadmap_text and "Ship parser MVP" in roadmap_text


def test_excel_unsupported(tmp_path: Path) -> None:
    bogus = tmp_path / "doc.txt"
    bogus.write_text("nope")
    runner = CliRunner()
    result = runner.invoke(app, ["excel", str(bogus), "-o", str(tmp_path)])
    assert result.exit_code != 0
