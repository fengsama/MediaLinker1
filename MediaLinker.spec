# -*- mode: python ; coding: utf-8 -*-
import sys

from PyInstaller.utils.hooks import collect_all

uvicorn_datas, uvicorn_binaries, uvicorn_hiddenimports = collect_all("uvicorn")

a = Analysis(
    ["backend/run.py"],
    pathex=["backend"],
    binaries=uvicorn_binaries,
    datas=uvicorn_datas + [
        ("frontend/dist", "frontend_dist"),
        ("PORTABLE-README.txt", "."),
    ],
    hiddenimports=uvicorn_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MediaLinker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    icon="assets/MediaLinker.ico" if sys.platform == "win32" else None,
    console=sys.platform != "win32",
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MediaLinker",
)
