from __future__ import annotations

from pathlib import Path


def test_windows_one_folder_recipe_is_windowed_and_excludes_sensitive_inputs() -> None:
    root = Path(__file__).resolve().parents[1]
    spec = (root / "SweepMultisineUI.spec").read_text(encoding="utf-8")
    build = (root / "scripts" / "build_windows_gui.ps1").read_text(encoding="utf-8")

    assert "name=\"SweepMultisineUI\"" in spec
    assert "console=False" in spec
    assert "COLLECT(" in spec
    assert "SWEEP_MULTISINE_RELEASE_STAGING" in spec
    assert "os.path.join(staging_root, 'config')" in spec
    assert "('tests'," not in spec
    assert '"pytest", "pytestqt", "PyQt5", "PyQt6", "PySide2"' in spec
    assert '"jupyter"' in spec and '"pyarrow"' in spec
    assert "final-test" not in spec.lower()
    assert "build_manifest.json" in build
    assert "SHA256SUMS.txt" in build
    assert "Get-FileHash" in build
    assert "SkipPyInstaller" in build
    assert "$DirtyMessage" in build
    assert "source_git_dirty = $false" in build
    assert "$PackagedVerification.source_commit -ne $SourceCommit" in build
