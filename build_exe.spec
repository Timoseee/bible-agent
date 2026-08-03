"""PyInstaller build definition for the BibleAI desktop application."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPEC).resolve().parent
icon_path = project_root / "assets" / "bibleai.ico"

hiddenimports = [
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "docx",
    "dotenv",
    "PIL",
    "mutagen",
    "pydub",
    "openai",
]
hiddenimports += collect_submodules("frontend")
hiddenimports += collect_submodules("modules")

datas = [
    (str(project_root / "templates"), "templates"),
    (str(project_root / "database"), "database"),
    (str(project_root / "prompts"), "prompts"),
]

a = Analysis(
    [str(project_root / "frontend" / "app.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    name="BibleAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(icon_path) if icon_path.exists() else None,
    exclude_binaries=True,
    contents_directory=".",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="BibleAI",
)
