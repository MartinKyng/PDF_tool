"""Unit tests for ``packaging/build_exe.py``.

The real PyInstaller / Inno Setup compilers are not required: the tool runners
(``_run_pyinstaller`` / ``_run_iscc``) and ``find_iscc`` are monkeypatched, so
these tests verify the build script's own logic (paths, argv construction,
artifact detection and error handling).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import pdf_tool

_BUILD_SCRIPT = Path(__file__).parent.parent / "packaging" / "build_exe.py"


def _load_build_module():
    spec = importlib.util.spec_from_file_location("build_exe_under_test", _BUILD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = _load_build_module()


class TestPureHelpers:
    def test_read_version_matches_the_package(self):
        assert build.read_version() == pdf_tool.__version__

    def test_pyinstaller_argv_targets_spec_and_paths(self, tmp_path):
        argv = build.pyinstaller_argv(
            tmp_path / "s.spec", tmp_path / "dist", tmp_path / "work"
        )
        assert argv[0] == str(tmp_path / "s.spec")
        assert "--distpath" in argv and str(tmp_path / "dist") in argv
        assert "--workpath" in argv and str(tmp_path / "work") in argv
        assert "--noconfirm" in argv

    def test_iscc_argv_carries_version_and_outdir(self, tmp_path):
        argv = build.iscc_argv(tmp_path / "installer.iss", "1.2.3", tmp_path / "dist")
        assert "/DAppVersion=1.2.3" in argv
        assert f"/O{tmp_path / 'dist'}" in argv
        assert str(tmp_path / "installer.iss") in argv

    def test_collect_artifacts_filters_to_build_outputs(self, tmp_path):
        (tmp_path / "pdf-join.exe").write_bytes(b"a")
        (tmp_path / "pdf-join-gui.exe").write_bytes(b"a")
        (tmp_path / "PDFTool-Setup-0.1.0.exe").write_bytes(b"a")
        (tmp_path / "notes.txt").write_bytes(b"a")
        (tmp_path / "subdir").mkdir()

        names = [p.name for p in build.collect_artifacts(tmp_path)]
        assert names == [
            "PDFTool-Setup-0.1.0.exe",
            "pdf-join-gui.exe",
            "pdf-join.exe",
        ]

    def test_collect_artifacts_empty_dir(self, tmp_path):
        assert build.collect_artifacts(tmp_path / "missing") == []


class TestFindIscc:
    def test_prefers_the_path(self, monkeypatch, tmp_path):
        fake = tmp_path / "ISCC.exe"
        fake.write_bytes(b"")
        monkeypatch.setattr(build.shutil, "which", lambda name: str(fake))
        assert build.find_iscc() == fake

    def test_falls_back_to_install_dirs(self, monkeypatch, tmp_path):
        monkeypatch.setattr(build.shutil, "which", lambda name: None)
        installed = tmp_path / "Inno Setup 6"
        installed.mkdir()
        iscc = installed / "ISCC.exe"
        iscc.write_bytes(b"")
        monkeypatch.setattr(build, "_INNO_DIRS", (str(installed),))
        assert build.find_iscc() == iscc

    def test_none_when_not_installed(self, monkeypatch, tmp_path):
        monkeypatch.setattr(build.shutil, "which", lambda name: None)
        monkeypatch.setattr(build, "_INNO_DIRS", (str(tmp_path / "empty"),))
        assert build.find_iscc() is None


class TestBuildExes:
    def test_invokes_pyinstaller_and_reports_artifacts(self, monkeypatch, tmp_path):
        captured = {}

        def fake_run(argv):
            captured["argv"] = argv
            i = argv.index("--distpath")
            dist = Path(argv[i + 1])
            dist.mkdir(parents=True, exist_ok=True)
            (dist / "pdf-join.exe").write_bytes(b"x")
            (dist / "pdf-join-gui.exe").write_bytes(b"x")

        monkeypatch.setattr(build, "_run_pyinstaller", fake_run)

        artifacts = build.build_exes(dist=tmp_path, work=tmp_path / "work")

        assert [a.name for a in artifacts] == ["pdf-join-gui.exe", "pdf-join.exe"]
        assert str(_BUILD_SCRIPT.parent / "pdf-tool.spec") == captured["argv"][0]


class TestBuildInstaller:
    def test_missing_iscc_is_a_clear_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(build, "find_iscc", lambda: None)
        with pytest.raises(RuntimeError, match="Inno Setup"):
            build.build_installer(dist=tmp_path)

    def test_compiles_and_returns_the_installer(self, monkeypatch, tmp_path):
        monkeypatch.setattr(build, "find_iscc", lambda: Path("/fake/ISCC.exe"))

        def fake_iscc(argv):
            out = None
            for token in argv:
                if token.startswith("/O"):
                    out = Path(token[2:])
            version = build.read_version()
            out.mkdir(parents=True, exist_ok=True)
            (out / f"PDFTool-Setup-{version}.exe").write_bytes(b"x")

        monkeypatch.setattr(build, "_run_iscc", fake_iscc)

        installer = build.build_installer(dist=tmp_path)
        assert installer.name == f"PDFTool-Setup-{pdf_tool.__version__}.exe"
        assert installer.is_file()


class TestMain:
    def test_main_builds_exes(self, monkeypatch, tmp_path, capsys):
        def fake_run(argv):
            i = argv.index("--distpath")
            dist = Path(argv[i + 1])
            dist.mkdir(parents=True, exist_ok=True)
            (dist / "pdf-join.exe").write_bytes(b"x")

        monkeypatch.setattr(build, "_run_pyinstaller", fake_run)

        assert build.main(["--dist", str(tmp_path)]) == 0
        assert "pdf-join.exe" in capsys.readouterr().out

    def test_main_with_installer_flag(self, monkeypatch, tmp_path, capsys):
        def fake_run(argv):
            i = argv.index("--distpath")
            dist = Path(argv[i + 1])
            dist.mkdir(parents=True, exist_ok=True)
            (dist / "pdf-join.exe").write_bytes(b"x")

        def fake_iscc(argv):
            out = next(Path(t[2:]) for t in argv if t.startswith("/O"))
            (out / f"PDFTool-Setup-{build.read_version()}.exe").write_bytes(b"x")

        monkeypatch.setattr(build, "_run_pyinstaller", fake_run)
        monkeypatch.setattr(build, "find_iscc", lambda: Path("/fake/ISCC.exe"))
        monkeypatch.setattr(build, "_run_iscc", fake_iscc)

        assert build.main(["--dist", str(tmp_path), "--installer"]) == 0
        printed = capsys.readouterr().out
        assert "installer" in printed
