"""Tests for the ``pdf-join`` command line interface."""

from __future__ import annotations

import sys

import pytest

from helpers import outline_titles, page_labels, read, write_bookmarked_pdf

from pdf_tool.cli import build_parser, main


class TestHappyPath:
    def test_joins_and_reports_a_summary(self, two_pdfs, tmp_path, capsys):
        first, second = two_pdfs
        out = tmp_path / "combined.pdf"

        exit_code = main([str(first), str(second), "--output", str(out)])
        printed = capsys.readouterr().out

        assert exit_code == 0
        assert page_labels(read(out)) == [
            "first-1",
            "first-2",
            "second-1",
            "second-2",
            "second-3",
        ]
        assert "Joining 2 PDF file(s)" in printed
        assert "first.pdf (2 page(s))" in printed
        assert "second.pdf (3 page(s))" in printed
        assert "Wrote" in printed and "5 page(s)" in printed

    def test_short_output_flag_works(self, two_pdfs, tmp_path):
        first, second = two_pdfs
        out = tmp_path / "short.pdf"

        assert main([str(first), str(second), "-o", str(out)]) == 0
        assert out.exists()

    def test_a_name_without_pdf_extension_gets_one(self, two_pdfs, tmp_path, capsys):
        first, second = two_pdfs

        exit_code = main([str(first), str(second), "-o", str(tmp_path / "report")])
        printed = capsys.readouterr().out

        assert exit_code == 0
        assert (tmp_path / "report.pdf").exists()
        assert not (tmp_path / "report").exists()
        assert "no .pdf extension" in printed

    def test_uppercase_extension_is_left_alone(self, two_pdfs, tmp_path):
        first, second = two_pdfs
        out = tmp_path / "combined.PDF"

        main([str(first), str(second), "-o", str(out)])

        assert out.exists()

    def test_quiet_prints_nothing(self, two_pdfs, tmp_path, capsys):
        first, second = two_pdfs

        assert main([str(first), str(second), "-o", str(tmp_path / "c.pdf"), "-q"]) == 0
        assert capsys.readouterr().out == ""

    def test_overwrite_flag_replaces_the_output(self, two_pdfs, tmp_path):
        first, second = two_pdfs
        out = tmp_path / "combined.pdf"
        out.write_bytes(b"precious")

        assert main([str(first), str(second), "-o", str(out), "--overwrite"]) == 0
        assert len(read(out).pages) == 5

    def test_no_bookmarks_flag_reaches_the_join(self, tmp_path):
        """``--no-bookmarks`` must actually change the output, not just exit 0."""
        first = write_bookmarked_pdf(tmp_path / "first.pdf", ["f-1"], "Chapter One")
        second = write_bookmarked_pdf(tmp_path / "second.pdf", ["s-1"], "Chapter Two")
        kept = tmp_path / "kept.pdf"
        dropped = tmp_path / "dropped.pdf"

        assert main([str(first), str(second), "-o", str(kept)]) == 0
        assert main(
            [str(first), str(second), "-o", str(dropped), "--no-bookmarks"]
        ) == 0

        assert outline_titles(read(kept)) == ["Chapter One", "Chapter Two"]
        assert outline_titles(read(dropped)) == []


class TestErrors:
    def test_single_input_exits_1_with_a_message(self, make_pdf, tmp_path, capsys):
        only = make_pdf("only.pdf", ["lonely"])

        exit_code = main([str(only), "-o", str(tmp_path / "c.pdf")])
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "at least 2" in captured.err
        assert not (tmp_path / "c.pdf").exists()

    def test_missing_input_exits_1(self, make_pdf, tmp_path, capsys):
        present = make_pdf("present.pdf", ["here"])

        exit_code = main(
            [str(present), str(tmp_path / "ghost.pdf"), "-o", str(tmp_path / "c.pdf")]
        )
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "ghost.pdf" in captured.err
        assert captured.out == ""

    def test_existing_output_exits_1(self, two_pdfs, tmp_path, capsys):
        first, second = two_pdfs
        out = tmp_path / "combined.pdf"
        out.write_bytes(b"precious")

        exit_code = main([str(first), str(second), "-o", str(out)])
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "already exists" in captured.err
        assert out.read_bytes() == b"precious"

    def test_missing_output_argument_is_an_argparse_error(self, two_pdfs):
        first, second = two_pdfs

        with pytest.raises(SystemExit) as exit_info:
            main([str(first), str(second)])

        assert exit_info.value.code == 2

    def test_no_traceback_escapes_to_the_user(self, make_pdf, tmp_path, capsys):
        only = make_pdf("only.pdf", ["lonely"])

        main([str(only), "-o", str(tmp_path / "c.pdf")])

        assert "Traceback" not in capsys.readouterr().err


class TestParser:
    def test_version_is_reported(self, capsys):
        with pytest.raises(SystemExit) as exit_info:
            build_parser().parse_args(["--version"])

        assert exit_info.value.code == 0
        assert "pdf-join" in capsys.readouterr().out

    def test_help_names_the_two_or_more_inputs_rule(self, capsys):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--help"])

        printed = capsys.readouterr().out
        assert "Join two or more PDF files" in printed
        assert "without editing their contents" in printed


class TestModuleEntryPoint:
    def test_python_dash_m_pdf_tool_runs(self, two_pdfs, tmp_path):
        """``python -m pdf_tool`` must behave like the console script."""
        import subprocess

        first, second = two_pdfs
        out = tmp_path / "module.pdf"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pdf_tool",
                str(first),
                str(second),
                "-o",
                str(out),
            ],
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0, completed.stderr
        assert out.exists()
        assert "Wrote" in completed.stdout
