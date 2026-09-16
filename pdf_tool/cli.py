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
from .compress import CompressResult, compress_files
from .images import ImagesToPdfResult, images_to_pdf
from .join import JoinResult, join_pdfs
from .units import ensure_pdf_suffix, human_size

PROGRAM_NAME = "pdf-join"

EPILOG = """\
examples:
  %(prog)s first.pdf second.pdf -o combined.pdf
  %(prog)s chapter*.pdf --output book.pdf
  %(prog)s a.pdf b.pdf c.pdf -o out/all.pdf --overwrite
  %(prog)s --images photo.jpg scan.png -o album.pdf
  %(prog)s --images --separate photo.jpg scan.png -o album.pdf
  %(prog)s --images --separate --keep-names photo.jpg scan.png -o ./out
  %(prog)s --compress bulky.pdf -o smaller.pdf
  %(prog)s --compress photo.jpg -o photo.jpg --quality strong
"""


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser (exposed for tests and --help)."""
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description=(
            "Join two or more PDF files into one, in the order given, "
            "without editing their contents. Pass --images to turn "
            "JPEG, PNG and other pictures into a PDF instead."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        metavar="INPUT",
        help="PDF files to join (or pictures when --images is set)",
    )
    parser.add_argument(
        "--images",
        action="store_true",
        help="treat inputs as pictures (JPEG, PNG, BMP, GIF, TIFF, WebP) "
        "and write PDF pages from them",
    )
    parser.add_argument(
        "--compress",
        action="store_true",
        help="shrink PDFs and pictures instead of joining them",
    )
    parser.add_argument(
        "--quality",
        choices=("light", "balanced", "strong"),
        default="balanced",
        help="how aggressively --compress should shrink files (default: balanced)",
    )
    parser.add_argument(
        "--separate",
        action="store_true",
        help="with --images, write one PDF per picture instead of combining",
    )
    parser.add_argument(
        "--keep-names",
        action="store_true",
        help="with --separate, name each PDF after its picture "
        "(photo.jpg → photo.pdf)",
    )
    parser.add_argument(
        "--name",
        action="append",
        dest="names",
        metavar="PDF",
        help="with --separate, an explicit output name (repeat once per image)",
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


def _report_images(
    result: ImagesToPdfResult, renamed_from: Path | None, quiet: bool
) -> None:
    if quiet:
        return
    print(f"Converting {len(result.files)} image file(s):")
    for index, item in enumerate(result.files, start=1):
        extra = f" → {item.output.name}" if not result.combined else ""
        print(f"  {index}. {item.path} ({item.width}×{item.height}){extra}")
    if renamed_from is not None and result.combined:
        print(
            f"note: '{renamed_from}' has no .pdf extension, "
            f"wrote '{result.output}' instead"
        )
    if result.combined:
        print(
            f"Wrote {result.output} "
            f"({result.total_pages} page(s), {human_size(result.size_bytes)})"
        )
    else:
        print(
            f"Wrote {len(result.outputs)} PDF file(s) "
            f"({human_size(result.size_bytes)})"
        )


def _report_compress(result: CompressResult, quiet: bool) -> None:
    if quiet:
        return
    print(
        f"Compressed {len(result.outputs)} file(s): "
        f"{human_size(result.original_bytes)} → {human_size(result.size_bytes)}"
    )
    for path in result.outputs:
        print(f"  {path}")


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
        f"({result.total_pages} page(s), {human_size(result.size_bytes)})"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    args = build_parser().parse_args(argv)

    raw_output = Path(args.output).expanduser()
    if args.compress:
        output, renamed = raw_output, False
    elif args.images and args.separate and (args.keep_names or raw_output.is_dir()):
        output, renamed = raw_output, False
    else:
        output, renamed = ensure_pdf_suffix(raw_output)

    try:
        if args.compress:
            result = compress_files(
                args.inputs,
                output,
                overwrite=args.overwrite,
                preset=args.quality,
            )
        elif args.images:
            result = images_to_pdf(
                args.inputs,
                output,
                overwrite=args.overwrite,
                combined=not args.separate,
                inherit_names=args.keep_names,
                names=args.names,
            )
        else:
            result = join_pdfs(
                args.inputs,
                output,
                overwrite=args.overwrite,
                keep_bookmarks=not args.no_bookmarks,
            )
    except PdfToolError as exc:
        print(f"{PROGRAM_NAME}: error: {exc}", file=sys.stderr)
        return 1

    note = Path(args.output).expanduser() if renamed else None
    if args.compress:
        _report_compress(result, args.quiet)
    elif args.images:
        _report_images(result, note, args.quiet)
    else:
        _report(result, note, args.quiet)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
