# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Adventurer Guild AI Windows desktop package."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


def _resolve_project_root() -> Path:
    """Resolve repository root safely when executed by PyInstaller."""
    spec_value = globals().get("SPEC")
    candidates: list[Path] = [Path.cwd()]
    if spec_value:
        spec_path = Path(spec_value).resolve()
        candidates.append(spec_path.parent)

    for candidate in candidates:
        current = candidate
        for _ in range(8):
            if (current / "run.py").exists() and (current / "packaging" / "windows").exists():
                return current
            if current.parent == current:
                break
            current = current.parent

    raise RuntimeError("Unable to resolve Adventurers Guild AI project root for PyInstaller spec execution.")


ROOT = _resolve_project_root()


def _tree_entries(src: Path, dest: str) -> list[tuple[str, str]]:
    if not src.exists():
        return []
    return [(str(path), str(Path(dest) / path.relative_to(src))) for path in src.rglob("*") if path.is_file()]

def _existing_entries(entries: list[tuple[Path, str]]) -> list[tuple[str, str]]:
    return [(str(src), dest) for src, dest in entries if src.exists()]


datas = []
datas.extend(_tree_entries(ROOT / "data", "data"))
datas.extend(_tree_entries(ROOT / "app" / "static", "app/static"))
datas.extend(_tree_entries(ROOT / "packaging" / "windows" / "runtime_bundle", "runtime_bundle"))
datas.extend(
    _existing_entries(
        [
            (ROOT / "data" / "dialogues.json", "data/dialogues.json"),
            (ROOT / "data" / "enemies.json", "data/enemies.json"),
            (ROOT / "data" / "items.json", "data/items.json"),
            (ROOT / "data" / "factions.json", "data/factions.json"),
            (ROOT / "data" / "npc_personalities.json", "data/npc_personalities.json"),
            (ROOT / "data" / "defaults" / "app_config.json", "data/defaults/app_config.json"),
            (ROOT / "data" / "workflows" / "scene_image.json", "data/workflows/scene_image.json"),
            (ROOT / "data" / "workflows" / "character_portrait.json", "data/workflows/character_portrait.json"),
            (ROOT / "app" / "static" / "index.html", "app/static/index.html"),
            (ROOT / "packaging" / "windows" / "runtime_bundle" / "THIRD_PARTY_NOTICES.txt", "runtime_bundle/THIRD_PARTY_NOTICES.txt"),
            (ROOT / "packaging" / "windows" / "runtime_bundle" / "workflows" / "scene_image.json", "runtime_bundle/workflows/scene_image.json"),
            (ROOT / "packaging" / "windows" / "runtime_bundle" / "workflows" / "character_portrait.json", "runtime_bundle/workflows/character_portrait.json"),
            (ROOT / "packaging" / "windows" / "runtime_bundle" / "comfyui" / "README.txt", "runtime_bundle/comfyui/README.txt"),
        ]
    )
)

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
webview_data, webview_binaries, webview_hiddenimports = collect_all("webview")

datas += fastapi_data + uvicorn_data + starlette_data + webview_data
binaries = fastapi_binaries + uvicorn_binaries + starlette_binaries + webview_binaries
hiddenimports += fastapi_hiddenimports + uvicorn_hiddenimports + starlette_hiddenimports + webview_hiddenimports


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
