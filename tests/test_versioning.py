"""Tests for the desktop application's single-source release versioning."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from pdf_tool.version import __version__


_BUILD_SCRIPT = Path(__file__).parent.parent / "packaging" / "build_exe.py"


def _build_module():
    spec = importlib.util.spec_from_file_location("build_exe_versioning", _BUILD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stable_version_is_read_from_the_one_source_file():
    build = _build_module()

    assert build.read_version() == __version__
    assert build.release_version("stable") == __version__


def test_beta_version_is_generated_without_editing_the_source_version():
    build = _build_module()

    assert build.release_version("beta", "123") == f"{__version__}-beta.123"
    assert build.read_version() == __version__


def test_stage_names_are_unique_and_identify_the_desktop_platform(tmp_path):
    build = _build_module()
    dist = tmp_path / "dist"
    staged = tmp_path / "release-assets"
    dist.mkdir()
    (dist / "pdf-join-gui").write_bytes(b"gui")
    (dist / "pdf-join").write_bytes(b"cli")

    result = build.stage_artifacts(dist, staged, "0.1.0-beta.123", "beta")
    names = {path.name for path in result}

    assert any(name.startswith("PDFTool-0.1.0-beta.123-") for name in names)
    assert any(name.startswith("PDFTool-cli-0.1.0-beta.123-") for name in names)
    assert len(names) == 2
