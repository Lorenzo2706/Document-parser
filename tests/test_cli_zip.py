"""Smoke tests for the `document-parser zip` subcommand."""

from __future__ import annotations

import zipfile
from pathlib import Path

from typer.testing import CliRunner

from document_parser.cli import app


def _build_folder(root: Path) -> None:
    (root / "nested").mkdir(parents=True)
    (root / "a.md").write_text("alpha", encoding="utf-8")
    (root / "nested" / "b.csv").write_text("x,y\n1,2\n", encoding="utf-8")


def test_zip_then_delete(tmp_path: Path) -> None:
    folder = tmp_path / "out"
    folder.mkdir()
    _build_folder(folder)

    runner = CliRunner()
    result = runner.invoke(app, ["zip", str(folder)])
    assert result.exit_code == 0, result.output

    archive = tmp_path / "out.zip"
    log = tmp_path / "out.zip.log"
    assert archive.exists()
    assert log.exists()
    assert not folder.exists()  # source deleted by default

    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
    assert "out/a.md" in names
    assert "out/nested/b.csv" in names

    log_text = log.read_text(encoding="utf-8")
    assert "ADDED out/a.md" in log_text
    assert "ADDED out/nested/b.csv" in log_text
    assert f"DELETED {folder}" in log_text
    assert "files=2 errors=0" in log_text


def test_zip_keep(tmp_path: Path) -> None:
    folder = tmp_path / "keepme"
    folder.mkdir()
    _build_folder(folder)

    runner = CliRunner()
    result = runner.invoke(app, ["zip", str(folder), "--keep"])
    assert result.exit_code == 0, result.output

    assert (tmp_path / "keepme.zip").exists()
    assert folder.exists()  # retained with --keep
    log_text = (tmp_path / "keepme.zip.log").read_text(encoding="utf-8")
    assert f"KEPT {folder}" in log_text
