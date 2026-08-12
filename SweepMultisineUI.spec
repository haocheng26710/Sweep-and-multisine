# -*- mode: python ; coding: utf-8 -*-
hiddenimports = []

a = Analysis(
    ["scripts/run_gui.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ('config', 'config'),
        (
            'validation_assets/pre_experiment_acceptance/assets_manifest.json',
            'validation_assets/pre_experiment_acceptance',
        ),
        (
            'validation_assets/pre_experiment_acceptance/build_verification.json',
            'validation_assets/pre_experiment_acceptance',
        ),
        (
            'validation_assets/pre_experiment_acceptance/rew/external_reference',
            'validation_assets/pre_experiment_acceptance/rew/external_reference',
        ),
        ('docs/USER_GUIDE_ZH.md', 'docs'),
        ('docs/QUICKSTART_UI_ZH.md', 'docs'),
        ('docs/TROUBLESHOOTING_UI_ZH.md', 'docs'),
        ('docs/progress/DEV-C16_PRE_EXPERIMENT_ACCEPTANCE.md', 'docs/progress'),
        ('docs/experiment/DEV_D_REAL_EXPERIMENT_ENTRY_CHECKLIST.md', 'docs/experiment'),
        ('docs/experiment/REAL_DATA_REPLACEMENT_GUIDE.md', 'docs/experiment'),
        ('docs/experiment/DEV_D_ACQUISITION_PLAN_TEMPLATE.md', 'docs/experiment'),
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
