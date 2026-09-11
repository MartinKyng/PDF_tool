"""Helpers that build small, valid PDF files from scratch.

These exist so the tests do not depend on a PDF *generation* library
(ReportLab, WeasyPrint, ...).  Every byte of the fixture files is produced
here, which means the tests can assert that a join left page content
streams byte-for-byte identical to the originals.
"""

from __future__ import annotations

from pathlib import Path

MEDIA_BOX = (0, 0, 612, 792)  # US Letter


def _escape_pdf_string(text: str) -> bytes:
    """Escape a string for use inside a PDF literal string ``( ... )``."""
    out = bytearray()
    for char in text.encode("latin-1", "replace"):
        if char in b"()\\":
            out += b"\\" + bytes([char])
        else:
            out.append(char)
    return bytes(out)


def build_pdf_bytes(page_labels: list[str]) -> bytes:
    """Return the bytes of a minimal valid PDF with one page per label.

    Each page draws its label with Helvetica at the top-left area, so the
    page content is both visible in a viewer and unique per page.
    """
    if not page_labels:
        raise ValueError("need at least one page label")

    n_pages = len(page_labels)
    # Object 1 = catalog, object 2 = page tree, then (page, content) pairs,
    # and finally the shared font.
    font_obj = 3 + 2 * n_pages
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n_pages))

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode("ascii"),
    ]

    for index, label in enumerate(page_labels):
        page_obj = 3 + 2 * index
        content_obj = page_obj + 1
        box = " ".join(str(v) for v in MEDIA_BOX)
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [{box}] "
                f"/Resources << /Font << /F1 {font_obj} 0 R >> >> "
                f"/Contents {content_obj} 0 R >>"
            ).encode("ascii")
        )
        stream = b"BT /F1 24 Tf 72 720 Td (" + _escape_pdf_string(label) + b") Tj ET"
        objects.append(
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\n"
            b"stream\n" + stream + b"\nendstream"
        )

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    return assemble(objects)


def build_image_pdf_bytes(label: str, rgb: bytes, width: int, height: int) -> bytes:
    """Return a one page PDF that draws raw RGB pixels plus a text label.

    The image is stored uncompressed, so its bytes can be compared exactly
    before and after a join to prove nothing was re-encoded.
    """
    if len(rgb) != width * height * 3:
        raise ValueError("rgb data does not match the given width and height")

    stream = (
        f"q {width} 0 0 {height} 72 500 cm /Im1 Do Q\n".encode("ascii")
        + b"BT /F1 24 Tf 72 720 Td ("
        + _escape_pdf_string(label)
        + b") Tj ET"
    )
    box = " ".join(str(v) for v in MEDIA_BOX)

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [{box}] "
            "/Resources << /Font << /F1 5 0 R >> /XObject << /Im1 6 0 R >> >> "
            "/Contents 4 0 R >>"
        ).encode("ascii"),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\n"
        b"stream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
            f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Length {len(rgb)} >>"
        ).encode("ascii")
        + b"\nstream\n" + rgb + b"\nendstream",
    ]

    return assemble(objects)


def assemble(objects: list[bytes]) -> bytes:
    """Serialise indirect objects into a complete PDF file with an xref table."""
    body = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for number, payload in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{number} 0 obj\n".encode("ascii") + payload + b"\nendobj\n"

    xref_at = len(body)
    body += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    body += b"0000000000 65535 f \n"
    for offset in offsets:
        body += f"{offset:010d} 00000 n \n".encode("ascii")
    body += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode("ascii")

    return bytes(body)


def write_pdf(path: Path, page_labels: list[str]) -> Path:
    """Write :func:`build_pdf_bytes` output to ``path`` and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_pdf_bytes(page_labels))
    return path
