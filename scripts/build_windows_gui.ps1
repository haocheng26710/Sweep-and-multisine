param(
    [string]$PythonExecutable = "python",
    [switch]$SkipPyInstaller
)

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SpecPath = Join-Path $ProjectRoot "SweepMultisineUI.spec"
$DistRoot = Join-Path $ProjectRoot "dist"
$ApplicationRoot = Join-Path $DistRoot "SweepMultisineUI"

if (-not $SkipPyInstaller) {
    & $PythonExecutable (Join-Path $ProjectRoot "scripts\build_acceptance_assets.py")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $PythonExecutable (Join-Path $ProjectRoot "scripts\build_acceptance_verification.py")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $PythonExecutable (Join-Path $ProjectRoot "scripts\build_acceptance_assets.py")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $env:QT_API = "pyside6"
    & $PythonExecutable -m PyInstaller --noconfirm --clean --distpath $DistRoot --workpath (Join-Path $ProjectRoot "build") $SpecPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$PythonVersion = (& $PythonExecutable -c "import platform; print(platform.python_version())").Trim()
$PyInstallerVersion = (& $PythonExecutable -c "import PyInstaller; print(PyInstaller.__version__)").Trim()
$PySideVersion = (& $PythonExecutable -c "import PySide6; print(PySide6.__version__)").Trim()
$GitCommit = (git -C $ProjectRoot rev-parse HEAD).Trim()
$GitDirty = [bool](git -C $ProjectRoot status --porcelain)
$ExecutablePath = Join-Path $ApplicationRoot "SweepMultisineUI.exe"

$BuildManifest = [ordered]@{
    schema_version = "1.0.0"
    build_kind = "windows_one_folder"
    application = "SweepMultisineUI"
    executable = "SweepMultisineUI.exe"
    executable_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $ExecutablePath).Hash.ToLowerInvariant()
    python_version = $PythonVersion
    pyinstaller_version = $PyInstallerVersion
    pyside6_version = $PySideVersion
    git_commit = $GitCommit
    git_dirty = $GitDirty
    source_spec = "SweepMultisineUI.spec"
    contains_tests = $false
    contains_real_data = $false
    contains_final_test = $false
    contains_git_credentials = $false
    created_utc = [DateTime]::UtcNow.ToString("o")
}
$BuildManifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $ApplicationRoot "build_manifest.json") -Encoding utf8

$ChecksumLines = Get-ChildItem -LiteralPath $ApplicationRoot -File -Recurse |
    Where-Object { $_.Name -ne "SHA256SUMS.txt" } |
    Sort-Object FullName |
    ForEach-Object {
        $Relative = $_.FullName.Replace($ApplicationRoot + "\", "").Replace("\", "/")
        $Digest = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
        "$Digest  $Relative"
    }
$ChecksumLines | Set-Content -LiteralPath (Join-Path $ApplicationRoot "SHA256SUMS.txt") -Encoding ascii

Write-Output "Built: $ExecutablePath"
Write-Output "SHA-256: $((Get-FileHash -Algorithm SHA256 -LiteralPath $ExecutablePath).Hash.ToLowerInvariant())"
