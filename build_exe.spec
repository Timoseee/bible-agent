"""PyInstaller build definition for the BibleAI desktop application."""

from pathlib import Path

project_root = Path(SPEC).resolve().parent
icon_path = project_root / "assets" / "bibleai.ico"

hiddenimports = [
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
    # Keep the runtime focused on the desktop app. These packages are pulled
    # in by optional tooling installed in the build environment, not by BibleAI.
    excludes=[
        "tkinter",
        "IPython",
        "jupyter",
        "jupyter_client",
        "jupyter_core",
        "matplotlib",
        "notebook",
        "pandas",
        "scipy",
        "zmq",
        # BibleAI uses Qt Core/Gui/Widgets/Network only. Excluding unused Qt
        # bindings prevents their matching Qt DLLs from entering the package.
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtGraphs",
        "PySide6.QtHttpServer",
        "PySide6.QtLocation",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtNetworkAuth",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtPositioning",
        "PySide6.QtPrintSupport",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtQuickControls2",
        "PySide6.QtQuickWidgets",
        "PySide6.QtRemoteObjects",
        "PySide6.QtScxml",
        "PySide6.QtSensors",
        "PySide6.QtSerialBus",
        "PySide6.QtSerialPort",
        "PySide6.QtSpatialAudio",
        "PySide6.QtSql",
        "PySide6.QtStateMachine",
        "PySide6.QtTest",
        "PySide6.QtTextToSpeech",
        "PySide6.QtUiTools",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
        "PySide6.QtWebView",
        "PySide6.QtXml",
        "PySide6.QtXmlPatterns",
    ],
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
