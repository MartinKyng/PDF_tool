# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec producing two single-file executables.

The spec is invoked by the Python build script
(``python packaging/build_exe.py``), which is also what the release workflow
runs. To build by hand::

    pyinstaller packaging/pdf-tool.spec --noconfirm

Artifacts land in ``dist/``:

* ``pdf-join``     - the console tool (small; no Qt bundled)
* ``pdf-join-gui`` - the PySide6 desktop app (windowed)

``pathex`` points at the repository root so PyInstaller bundles the source
``pdf_tool`` package directly, without requiring an editable install.
"""

from pathlib import Path

block_cipher = None
REPO_ROOT = str(Path(SPECPATH).parent)

COMMON = dict(
    pathex=[REPO_ROOT],
    binaries=[],
    datas=[],
    hiddenimports=["pdf_tool", "pypdf", "PIL"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# --- console tool -----------------------------------------------------------
cli = Analysis(["cli_launcher.py"], **COMMON)
cli_pyz = PYZ(cli.pure, cli.zipped_data, cipher=block_cipher)
cli_exe = EXE(
    cli_pyz,
    cli.scripts,
    cli.binaries,
    cli.zipfiles,
    cli.datas,
    [],
    name="pdf-join",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,           # terminal tool
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# --- GUI --------------------------------------------------------------------
gui = Analysis(
    ["gui_launcher.py"],
    hiddenimports=["pdf_tool", "pdf_tool.gui", "pypdf", "PIL"],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
gui_pyz = PYZ(gui.pure, gui.zipped_data, cipher=block_cipher)
gui_exe = EXE(
    gui_pyz,
    gui.scripts,
    gui.binaries,
    gui.zipfiles,
    gui.datas,
    [],
    name="pdf-join-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # no console window on double-click
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
