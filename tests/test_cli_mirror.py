"""Smoke tests for the `slide-parser mirror` subcommand."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from typer.testing import CliRunner

from slide_parser.cli import app


def _build_tree(root: Path, sample_pptx: Path) -> None:
    (root / "nested").mkdir(parents=True)
    shutil.copy2(sample_pptx, root / "deck.pptx")
    shutil.copy2(sample_pptx, root / "nested" / "deck2.pptx")
    (root / "readme.txt").write_text("hello")
    (root / "nested" / "page.html").write_text("<p>hi</p>")
    (root / "ignored.bin").write_bytes(b"\x00\x01")


def test_mirror_basic(tmp_path: Path, sample_pptx: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    _build_tree(src, sample_pptx)

    runner = CliRunner()
    result = runner.invoke(app, ["mirror", str(src), str(dst)])
    assert result.exit_code == 0, result.output

    assert (dst / "deck.md").exists()
    assert (dst / "nested" / "deck2.md").exists()
    assert (dst / "readme.txt").read_text() == "hello"
    assert (dst / "nested" / "page.html").exists()
    assert not (dst / "ignored.bin").exists()


def test_mirror_skips_up_to_date(tmp_path: Path, sample_pptx: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    _build_tree(src, sample_pptx)

    runner = CliRunner()
    assert runner.invoke(app, ["mirror", str(src), str(dst)]).exit_code == 0

    md = dst / "deck.md"
    copied = dst / "readme.txt"
    mtime_md = md.stat().st_mtime
    mtime_txt = copied.stat().st_mtime

    time.sleep(0.05)
    result = runner.invoke(app, ["mirror", str(src), str(dst)])
    assert result.exit_code == 0
    assert "skipped=" in result.output
    assert md.stat().st_mtime == mtime_md
    assert copied.stat().st_mtime == mtime_txt
