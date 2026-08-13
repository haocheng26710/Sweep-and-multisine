param(
    [string]$PythonExecutable = "python",
    [switch]$SkipPyInstaller
)

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SpecPath = Join-Path $ProjectRoot "SweepMultisineUI.spec"
$BuildRoot = Join-Path $ProjectRoot "build"
$StagingRoot = Join-Path $BuildRoot "release_staging"
$VerificationPath = Join-Path $StagingRoot "build_verification_source.json"
$DistRoot = Join-Path $ProjectRoot "dist"
$ApplicationRoot = Join-Path $DistRoot "SweepMultisineUI"

# This is the first operation that can terminate the formal build. Nothing has
# been written before clean source provenance is captured.
$GitStatusBefore = @(git -C $ProjectRoot status --porcelain)
if ($LASTEXITCODE -ne 0) {
    Write-Error "Formal release build stopped: cannot read Git status."
    exit 3
}
if ($GitStatusBefore.Count -ne 0) {
    $DirtyMessage = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("5q2j5byP5Y+R5biD5p6E5bu65bey5Lit5q2i77yaR2l0IOW3peS9nOagkeS4jeW5suWHgOOAguivt+WFiOaPkOS6pOaIluenu+mZpOaJgOacieS/ruaUue+8jOWGjeS7jiBjbGVhbiBjb21taXQg6YeN5paw5p6E5bu644CC"))
    Write-Error $DirtyMessage
    exit 3
}
$SourceCommit = (git -C $ProjectRoot rev-parse HEAD).Trim()
$SourceBranch = (git -C $ProjectRoot branch --show-current).Trim()

if (-not $SkipPyInstaller) {
    if (Test-Path -LiteralPath $StagingRoot) {
        $ResolvedBuild = (Resolve-Path -LiteralPath $BuildRoot).Path
        $ResolvedStaging = (Resolve-Path -LiteralPath $StagingRoot).Path
        $BuildPrefix = $ResolvedBuild + [IO.Path]::DirectorySeparatorChar
        if (-not $ResolvedStaging.StartsWith($BuildPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            Write-Error "Formal release build stopped: staging is outside build/."
            exit 3
        }
        Remove-Item -LiteralPath $ResolvedStaging -Recurse -Force
    }
    New-Item -ItemType Directory -Path $StagingRoot -Force | Out-Null

    & $PythonExecutable (Join-Path $ProjectRoot "scripts\build_acceptance_verification.py") `
        --output $VerificationPath `
        --source-commit $SourceCommit `
        --source-branch $SourceBranch
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $PythonExecutable (Join-Path $ProjectRoot "scripts\build_acceptance_assets.py") `
        --output-root $StagingRoot `
        --build-verification $VerificationPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $env:SWEEP_MULTISINE_RELEASE_STAGING = $StagingRoot
    $env:QT_API = "pyside6"
    & $PythonExecutable -m PyInstaller --noconfirm --clean --distpath $DistRoot --workpath $BuildRoot $SpecPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$GitStatusAfter = @(git -C $ProjectRoot status --porcelain)
$CurrentCommit = (git -C $ProjectRoot rev-parse HEAD).Trim()
if ($GitStatusAfter.Count -ne 0 -or $CurrentCommit -ne $SourceCommit) {
    Write-Error "Formal release build stopped: source tree or Git HEAD changed during build."
    exit 3
}

$PythonVersion = (& $PythonExecutable -c "import platform; print(platform.python_version())").Trim()
$PyInstallerVersion = (& $PythonExecutable -c "import PyInstaller; print(PyInstaller.__version__)").Trim()
$PySideVersion = (& $PythonExecutable -c "import PySide6; print(PySide6.__version__)").Trim()
$ExecutablePath = Join-Path $ApplicationRoot "SweepMultisineUI.exe"
$PackagedVerificationPath = Join-Path $ApplicationRoot "_internal\validation_assets\pre_experiment_acceptance\build_verification.json"
if (-not (Test-Path -LiteralPath $ExecutablePath) -or -not (Test-Path -LiteralPath $PackagedVerificationPath)) {
    Write-Error "Formal release build stopped: executable or packaged verification is missing."
    exit 3
}
$PackagedVerification = Get-Content -Raw -LiteralPath $PackagedVerificationPath | ConvertFrom-Json
if ($PackagedVerification.source_commit -ne $SourceCommit -or $PackagedVerification.source_git_dirty -ne $false) {
    Write-Error "Formal release build stopped: packaged provenance does not match the clean source commit."
    exit 3
}

$BuildManifest = [ordered]@{
    schema_version = "1.0.0"
    build_kind = "windows_one_folder"
    application = "SweepMultisineUI"
    executable = "SweepMultisineUI.exe"
    executable_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $ExecutablePath).Hash.ToLowerInvariant()
    python_version = $PythonVersion
    pyinstaller_version = $PyInstallerVersion
    pyside6_version = $PySideVersion
    git_commit = $SourceCommit
    source_commit = $SourceCommit
    source_branch = $SourceBranch
    git_dirty = $false
    source_git_dirty = $false
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
Write-Output "Source commit: $SourceCommit"
Write-Output "Source dirty: false"
Write-Output "SHA-256: $((Get-FileHash -Algorithm SHA256 -LiteralPath $ExecutablePath).Hash.ToLowerInvariant())"
