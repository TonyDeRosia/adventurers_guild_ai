# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Adventurer Guild AI Windows desktop package."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(__file__).resolve().parents[2]


def _tree_entries(src: Path, dest: str) -> list[tuple[str, str]]:
    if not src.exists():
        return []
    return [(str(path), str(Path(dest) / path.relative_to(src))) for path in src.rglob("*") if path.is_file()]


datas = []
datas.extend(_tree_entries(ROOT / "data", "data"))
datas.extend(_tree_entries(ROOT / "app" / "static", "app/static"))
datas.extend(_tree_entries(ROOT / "packaging" / "windows" / "runtime_bundle", "runtime_bundle"))

hiddenimports = []
hiddenimports.extend(collect_submodules("app"))
hiddenimports.extend(collect_submodules("engine"))
hiddenimports.extend(collect_submodules("images"))
hiddenimports.extend(collect_submodules("memory"))
hiddenimports.extend(collect_submodules("models"))
hiddenimports.extend(collect_submodules("prompts"))
hiddenimports.extend(collect_submodules("rules"))

fastapi_data, fastapi_binaries, fastapi_hiddenimports = collect_all("fastapi")
uvicorn_data, uvicorn_binaries, uvicorn_hiddenimports = collect_all("uvicorn")
starlette_data, starlette_binaries, starlette_hiddenimports = collect_all("starlette")

datas += fastapi_data + uvicorn_data + starlette_data
binaries = fastapi_binaries + uvicorn_binaries + starlette_binaries
hiddenimports += fastapi_hiddenimports + uvicorn_hiddenimports + starlette_hiddenimports


block_cipher = None


a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AdventurerGuildAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AdventurerGuildAI",
)
