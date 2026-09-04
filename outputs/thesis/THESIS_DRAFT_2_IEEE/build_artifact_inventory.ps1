$ErrorActionPreference = 'Stop'

$packageRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $packageRoot '../../..')).Path
$packageRelative = 'outputs/thesis/THESIS_DRAFT_2_IEEE'

$relativePaths = @(
    "$packageRelative/README.md",
    "$packageRelative/VALIDATION_REPORT.md",
    "$packageRelative/NAMING_CROSSWALK.md",
    "$packageRelative/NAMING_CROSSWALK.csv",
    "$packageRelative/redraw_publication_figures.py",
    "$packageRelative/build_artifact_inventory.ps1",
    "$packageRelative/THESIS_DRAFT_2_IEEE_EN.pdf",
    "$packageRelative/THESIS_DRAFT_2_IEEE_ZH.pdf",
    "$packageRelative/THESIS_DRAFT_2_IEEE_ZH_FIXED.pdf",
    "$packageRelative/THESIS_DRAFT_2_IEEE_EN_OVERLEAF.zip",
    "$packageRelative/THESIS_DRAFT_2_IEEE_ZH_OVERLEAF.zip",
    "$packageRelative/THESIS_DRAFT_2_IEEE_ZH_OVERLEAF_FIXED.zip",
    "$packageRelative/english/main.tex",
    "$packageRelative/english/references.bib",
    "$packageRelative/english/OVERLEAF_README.md",
    "$packageRelative/chinese/main.tex",
    "$packageRelative/chinese/references.bib",
    "$packageRelative/chinese/OVERLEAF_README.md",
    'docs/thesis/IEEE_BILINGUAL_DRAFT_2.md'
)

$relativePaths += Get-ChildItem -LiteralPath (Join-Path $packageRoot 'english/sections') -Filter '*.tex' |
    Sort-Object Name |
    ForEach-Object { "$packageRelative/english/sections/$($_.Name)" }
$relativePaths += Get-ChildItem -LiteralPath (Join-Path $packageRoot 'chinese/sections') -Filter '*.tex' |
    Sort-Object Name |
    ForEach-Object { "$packageRelative/chinese/sections/$($_.Name)" }

foreach ($language in @('english', 'chinese')) {
    foreach ($figure in @(
        'r3_isolated_connected.png',
        'e2_validation_family.png',
        'e2_dev_validation.png',
        'e2_family_mechanisms.png'
    )) {
        $relativePaths += "$packageRelative/$language/figures/$figure"
    }
}

$artifacts = foreach ($relativePath in $relativePaths | Sort-Object -Unique) {
    $absolutePath = Join-Path $repoRoot $relativePath
    if (-not (Test-Path -LiteralPath $absolutePath -PathType Leaf)) {
        throw "Required artifact is missing: $relativePath"
    }
    $item = Get-Item -LiteralPath $absolutePath
    [ordered]@{
        path = $relativePath.Replace('\', '/')
        bytes = $item.Length
        sha256 = (Get-FileHash -LiteralPath $absolutePath -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

$inventory = [ordered]@{
    schema_version = '1.0'
    package = 'THESIS_DRAFT_2_IEEE'
    date = '2026-08-30'
    status = 'IEEE_BILINGUAL_DRAFT_2_COMPLETE'
    final_test_read = $false
    new_scientific_runs = 0
    formats = [ordered]@{
        english = [ordered]@{
            document_class = 'IEEEtran journal'
            columns = 2
            compiler = 'pdfLaTeX + BibTeX'
            pages = 18
        }
        chinese = [ordered]@{
            document_class = 'IEEEtran journal'
            columns = 2
            compiler = 'LuaLaTeX + BibTeX'
            pages = 12
        }
    }
    protected_claims = @(
        'The four-state grouped-recognition negative is retained.',
        'The 80/80 result is limited to the sealed five-node idealised reduced-order model.',
        'No physical, full-wave, causal, or family-superiority conclusion follows from the 80/80 result.'
    )
    artifacts = $artifacts
}

$inventoryPath = Join-Path $packageRoot 'artifact_inventory.json'
$inventory | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $inventoryPath -Encoding utf8

$sumPaths = @($relativePaths) + "$packageRelative/artifact_inventory.json"
$sumLines = foreach ($relativePath in $sumPaths | Sort-Object -Unique) {
    $absolutePath = Join-Path $repoRoot $relativePath
    $hash = (Get-FileHash -LiteralPath $absolutePath -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $($relativePath.Replace('\', '/'))"
}
$sumPath = Join-Path $packageRoot 'SHA256SUMS.txt'
$sumLines | Set-Content -LiteralPath $sumPath -Encoding utf8
