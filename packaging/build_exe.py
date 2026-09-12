"""Build the frozen executables (and, on Windows, the installer).

This is the single entry point the release workflow uses.  It

1. drives PyInstaller from :mod:`packaging/pdf-tool.spec` to produce the
   ``pdf-join`` and ``pdf-join-gui`` single-file executables, and
2. optionally (``--installer``, Windows only) compiles
   :mod:`packaging/installer.iss` with the Inno Setup compiler to produce a
   ``PDFTool-Setup-<version>.exe`` installer.

Run it from anywhere::

    python packaging/build_exe.py                 # exes only
    python packaging/build_exe.py --installer     # exes + Windows installer

The heavy tools (PyInstaller, Inno Setup) are invoked only when asked, so the
module's pure helpers can be unit-tested without them.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SPEC = "packaging/pdf-tool.spec"
ISS = "packaging/installer.iss"

#: Fallback locations for the Inno Setup compiler on Windows.
_INNO_DIRS = (
    r"C:\Program Files (x86)\Inno Setup 6",
    r"C:\Program Files\Inno Setup 6",
    r"C:\Program Files (x86)\Inno Setup 5",
)


def repo_root() -> Path:
    """The repository root (the parent of the ``packaging`` directory)."""
    return Path(__file__).resolve().parent.parent


def read_version() -> str:
    """Return the package version without installing it."""
    root = repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import pdf_tool

    return pdf_tool.__version__


def pyinstaller_argv(spec: Path, dist: Path, work: Path) -> list[str]:
    """The argument list handed to ``PyInstaller.__main__.run``."""
    return [
        str(spec),
        "--noconfirm",
        "--distpath", str(dist),
        "--workpath", str(work),
        "--log-level", "WARN",
    ]


def iscc_argv(iss: Path, version: str, outdir: Path) -> list[str]:
    """The argument list handed to the Inno Setup compiler."""
    return [
        f"/DAppVersion={version}",
        f"/O{outdir}",
        "/Q",
        str(iss),
    ]


def find_iscc() -> Path | None:
    """Locate the Inno Setup compiler, or ``None`` if it is not installed."""
    for name in ("ISCC.exe", "iscc"):
        found = shutil.which(name)
        if found:
            return Path(found)
    for base in _INNO_DIRS:
        candidate = Path(base) / "ISCC.exe"
        if candidate.is_file():
            return candidate
    return None


def collect_artifacts(dist: Path) -> list[Path]:
    """The build artifacts currently sitting in ``dist``."""
    if not dist.is_dir():
        return []
    wanted = []
    for entry in sorted(dist.iterdir()):
        if not entry.is_file():
            continue
        if entry.name.startswith("pdf-join") or entry.name.lower().endswith(".exe"):
            wanted.append(entry)
    return wanted


# -- tool runners (monkeypatched in the tests) ------------------------------
def _run_pyinstaller(argv: list[str]) -> None:  # pragma: no cover - needs the tool
    from PyInstaller.__main__ import run

    run(argv)


def _run_iscc(argv: list[str]) -> None:  # pragma: no cover - needs the tool
    subprocess.run(argv, check=True)


def build_exes(dist: Path | None = None, work: Path | None = None) -> list[Path]:
    """Run PyInstaller over the spec and return the artifacts produced."""
    root = repo_root()
    dist = dist or (root / "dist")
    work = work or (root / "build")
    _run_pyinstaller(pyinstaller_argv(root / SPEC, dist, work))
    return collect_artifacts(dist)


def build_installer(dist: Path | None = None) -> Path:
    """Compile the Inno Setup installer and return its path."""
    root = repo_root()
    dist = dist or (root / "dist")
    iscc = find_iscc()
    if iscc is None:
        raise RuntimeError(
            "Inno Setup compiler (ISCC.exe) not found; install Inno Setup "
            "(e.g. 'choco install innosetup') or omit --installer"
        )
    version = read_version()
    _run_iscc([str(iscc), *iscc_argv(root / ISS, version, dist)])
    installer = dist / f"PDFTool-Setup-{version}.exe"
    if not installer.is_file():
        raise RuntimeError(f"expected installer was not produced: {installer}")
    return installer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--installer",
        action="store_true",
        help="also compile the Windows installer with Inno Setup",
    )
    parser.add_argument(
        "--dist",
        type=Path,
        default=None,
        help="output directory for artifacts (default: <repo>/dist)",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    dist = args.dist or (root / "dist")

    print(f"pdf_tool {read_version()} -> building executables into {dist}")
    artifacts = build_exes(dist=dist)
    for path in artifacts:
        print(f"  built {path.name}")

    if args.installer:
        installer = build_installer(dist=dist)
        print(f"  built installer {installer.name}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
