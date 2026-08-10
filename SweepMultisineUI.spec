# -*- mode: python ; coding: utf-8 -*-
hiddenimports = []

a = Analysis(
    ["scripts/run_gui.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('docs/USER_GUIDE_ZH.md', 'docs'),
        ('docs/QUICKSTART_UI_ZH.md', 'docs'),
        ('docs/TROUBLESHOOTING_UI_ZH.md', 'docs'),
        ('README.md', '.'),
        ('MIGRATION_V1_TO_V2.md', '.'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest", "pytestqt", "PyQt5", "PyQt6", "PySide2",
        "IPython", "jupyter", "jupyterlab", "notebook", "nbconvert", "nbformat",
        "sphinx", "docutils", "black", "dask", "distributed", "pyarrow",
        "bokeh", "panel", "plotly", "altair", "intake", "xarray",
        "tables", "h5py", "openpyxl", "sqlalchemy", "botocore",
        "skimage", "statsmodels", "numba", "llvmlite",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SweepMultisineUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SweepMultisineUI",
)
