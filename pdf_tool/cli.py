"""Command line interface for pdf_tool.

Usage::

    pdf-join report-part1.pdf report-part2.pdf -o report.pdf
    python -m pdf_tool a.pdf b.pdf c.pdf --output combined.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .errors import PdfToolError
from .join import JoinResult, join_pdfs

PROGRAM_NAME = "pdf-join"

EPILOG = """\
examples:
  %(prog)s first.pdf second.pdf -o combined.pdf
  %(prog)s chapter*.pdf --output book.pdf
  %(prog)s a.pdf b.pdf c.pdf -o out/all.pdf --overwrite
"""


def _human_size(size_bytes: int) -> str:
    """Format a byte count the way a person would read it."""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"  # pragma: no cover - unreachable


def _add_pdf_suffix(path: Path) -> tuple[Path, bool]:
    """Append ``.pdf`` to ``path`` when it has no PDF extension.

    Returns the path to use and whether it was changed, so the caller can
    tell the user about it.
    """
    if path.suffix.lower() == ".pdf":
        return path, False
    return path.with_suffix(path.suffix + ".pdf"), True


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser (exposed for tests and --help)."""
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description=(
            "Join two or more PDF files into one, in the order given, "
            "without editing their contents."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        metavar="INPUT",
        help="PDF files to join, in the order they should appear",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        metavar="NAME",
        help="name of the combined PDF to write (.pdf is added if missing)",
    )
    parser.add_argument(
        "-f",
        "--overwrite",
        action="store_true",
        help="replace the output file if it already exists",
    )
    parser.add_argument(
        "--no-bookmarks",
        action="store_true",
        help="do not copy bookmarks (outline entries) from the inputs",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="only report errors",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _report(result: JoinResult, renamed_from: Path | None, quiet: bool) -> None:
    """Print a short summary of what was joined."""
    if quiet:
        return
    print(f"Joining {len(result.files)} PDF file(s):")
    for index, item in enumerate(result.files, start=1):
        print(f"  {index}. {item.path} ({item.pages} page(s))")
    if renamed_from is not None:
        print(
            f"note: '{renamed_from}' has no .pdf extension, "
            f"wrote '{result.output}' instead"
        )
    print(
        f"Wrote {result.output} "
        f"({result.total_pages} page(s), {_human_size(result.size_bytes)})"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    args = build_parser().parse_args(argv)

    output, renamed = _add_pdf_suffix(Path(args.output).expanduser())

    try:
        result = join_pdfs(
            args.inputs,
            output,
            overwrite=args.overwrite,
            keep_bookmarks=not args.no_bookmarks,
        )
    except PdfToolError as exc:
        print(f"{PROGRAM_NAME}: error: {exc}", file=sys.stderr)
        return 1

    _report(result, Path(args.output).expanduser() if renamed else None, args.quiet)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
