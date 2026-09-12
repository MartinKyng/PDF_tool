"""Build the PDF Tool desktop executables.

This is the one build entry point used by CI.  It bundles the application
source into native executables with PyInstaller; it does not create a wheel or
an installable Python package.

Examples::

    python packaging/build_exe.py
    python packaging/build_exe.py --channel beta --stage release-assets
    python packaging/build_exe.py --installer   # Windows only

The source version lives in ``pdf_tool/version.py``.  The stable workflow uses
that value as-is.  Branch builds get a generated ``-beta.<run>`` release label
without changing any source file.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

SPEC = "packaging/pdf-tool.spec"
ISS = "packaging/installer.iss"
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)

#: Fallback locations for the Inno Setup compiler on Windows.
_INNO_DIRS = (
    r"C:\Program Files (x86)\Inno Setup 6",
    r"C:\Program Files\Inno Setup 6",
    r"C:\Program Files (x86)\Inno Setup 5",
)


def repo_root() -> Path:
    """The repository root (the parent of the ``packaging`` directory)."""
    return Path(__file__).resolve().parent.parent


def validate_version(version: str) -> str:
    """Validate and return a semantic version used by a desktop release."""
    if not SEMVER_RE.fullmatch(version):
        raise ValueError(
            f"invalid version {version!r}; expected semantic version X.Y.Z"
        )
    return version


def read_version() -> str:
    """Return the one source-controlled application version."""
    root = repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from pdf_tool.version import __version__

    return validate_version(__version__)


def release_version(channel: str = "stable", build_number: str | None = None) -> str:
    """Return the version label for a stable or branch build.

    ``pdf_tool/version.py`` always contains the stable base version.  Beta
    builds add a monotonically increasing CI run number, so every branch build
    can be installed and published without editing or dirtying the checkout.
    """
    base = read_version()
    if channel == "stable":
        return base
    if channel != "beta":
        raise ValueError(f"unknown release channel: {channel}")

    # A prerelease already present in the base is stripped before adding the
    # generated beta identifier.  Normal releases should keep the file at
    # X.Y.Z, but this keeps local builds predictable if that rule is relaxed.
    stable_base = base.split("-", 1)[0].split("+", 1)[0]
    number = build_number or os.environ.get("GITHUB_RUN_NUMBER") or "local"
    safe_number = re.sub(r"[^0-9A-Za-z-]+", "-", str(number)).strip("-") or "local"
    return validate_version(f"{stable_base}-beta.{safe_number}")


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
    # Sort on the raw name so the order is identical on case-sensitive
    # (Linux/macOS) and case-insensitive (Windows) filesystems.
    for entry in sorted(dist.iterdir(), key=lambda p: p.name):
        if not entry.is_file():
            continue
        if entry.name.startswith("pdf-join") or entry.name.lower().endswith(".exe"):
            wanted.append(entry)
    return wanted


def _platform_slug() -> str:
    """The short platform name used in public release asset names."""
    names = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}
    return names.get(platform.system(), platform.system().lower())


def stage_artifacts(
    dist: Path,
    destination: Path,
    version: str,
    channel: str = "stable",
) -> list[Path]:
    """Copy build outputs to uniquely named assets for a GitHub release.

    PyInstaller deliberately uses stable internal names (``pdf-join-gui``),
    while release assets include app, version and platform names.  This avoids
    collisions when the three matrix jobs are downloaded together.
    """
    validate_version(version)
    destination.mkdir(parents=True, exist_ok=True)
    slug = _platform_slug()
    staged: list[Path] = []

    for source in collect_artifacts(dist):
        lower_name = source.name.lower()
        if lower_name.startswith("pdftool-setup"):
            label = "PDFTool-Setup"
        elif "gui" in source.stem.lower():
            label = "PDFTool"
        elif source.stem.lower().startswith("pdf-join"):
            label = "PDFTool-cli"
        else:
            continue
        target = destination / f"{label}-{version}-{slug}{source.suffix}"
        shutil.copy2(source, target)
        staged.append(target)

    return staged


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


def build_installer(dist: Path | None = None, version: str | None = None) -> Path:
    """Compile the Windows installer and return its path."""
    root = repo_root()
    dist = dist or (root / "dist")
    iscc = find_iscc()
    if iscc is None:
        raise RuntimeError(
            "Inno Setup compiler (ISCC.exe) not found; install Inno Setup "
            "(e.g. 'choco install innosetup') or omit --installer"
        )
    version = validate_version(version or read_version())
    _run_iscc([str(iscc), *iscc_argv(root / ISS, version, dist)])
    installer = dist / f"PDFTool-Setup-{version}.exe"
    if not installer.is_file():
        raise RuntimeError(f"expected installer was not produced: {installer}")
    return installer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--channel",
        choices=("stable", "beta"),
        default="stable",
        help="release channel (stable for main, beta for other branches)",
    )
    parser.add_argument(
        "--build-number",
        default=None,
        help="beta identifier; defaults to GITHUB_RUN_NUMBER",
    )
    parser.add_argument(
        "--installer",
        action="store_true",
        help="also compile the Windows installer with Inno Setup",
    )
    parser.add_argument(
        "--stage",
        type=Path,
        default=None,
        help="copy uniquely named release assets into this directory",
    )
    parser.add_argument(
        "--stage-only",
        action="store_true",
        help="stage existing artifacts without running PyInstaller again",
    )
    parser.add_argument(
        "--dist",
        type=Path,
        default=None,
        help="output directory for PyInstaller artifacts (default: <repo>/dist)",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    dist = args.dist or (root / "dist")
    version = release_version(args.channel, args.build_number)

    if args.stage_only:
        if args.stage is None:
            parser.error("--stage-only requires --stage")
        staged = stage_artifacts(dist, args.stage, version, args.channel)
        for path in staged:
            print(f"  staged {path.name}")
        return 0

    print(
        f"PDF Tool {version} ({args.channel}) -> "
        f"building desktop executables into {dist}"
    )
    artifacts = build_exes(dist=dist)
    for path in artifacts:
        print(f"  built {path.name}")

    # Inno Setup accepts the stable numeric version.  Branch builds publish
    # the GUI executable as beta assets; only main creates the installer.
    if args.installer:
        installer = build_installer(dist=dist, version=read_version())
        print(f"  built installer {installer.name}")

    if args.stage is not None:
        staged = stage_artifacts(dist, args.stage, version, args.channel)
        for path in staged:
            print(f"  staged {path.name}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
