$ErrorActionPreference = 'Stop'

$packageRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $packageRoot '../../..')).Path
$packageRelative = 'outputs/thesis/THESIS_DRAFT_5_INTRO_REPRO_IEEE'

$relativePaths = @(
    "$packageRelative/README.md",
    "$packageRelative/REVISION_SUMMARY.md",
    "$packageRelative/REVIEW_RESPONSE_AND_OPEN_ITEMS.md",
    "$packageRelative/AUTHOR_CONFIRMATION_REQUIRED.md",
    "$packageRelative/VALIDATION_REPORT.md",
    "$packageRelative/FIGURE1_GEOMETRY_PROVENANCE.md",
    "$packageRelative/NAMING_CROSSWALK.md",
    "$packageRelative/NAMING_CROSSWALK.csv",
    "$packageRelative/redraw_publication_figures.py",
    "$packageRelative/make_architecture_figure.py",
    "$packageRelative/build_artifact_inventory.ps1",
    "$packageRelative/THESIS_DRAFT_5_INTRO_REPRO_IEEE_EN.pdf",
    "$packageRelative/THESIS_DRAFT_5_INTRO_REPRO_IEEE_ZH.pdf",
    "$packageRelative/THESIS_DRAFT_5_INTRO_REPRO_IEEE_EN_OVERLEAF.zip",
    "$packageRelative/THESIS_DRAFT_5_INTRO_REPRO_IEEE_ZH_OVERLEAF.zip",
    "$packageRelative/english/main.tex",
    "$packageRelative/english/references.bib",
    "$packageRelative/english/OVERLEAF_README.md",
    "$packageRelative/chinese/main.tex",
    "$packageRelative/chinese/references.bib",
    "$packageRelative/chinese/OVERLEAF_README.md",
    'docs/thesis/IEEE_BILINGUAL_DRAFT_5_INTRO_REPRO.md'
)

foreach ($language in @('english', 'chinese')) {
    $relativePaths += Get-ChildItem -LiteralPath (Join-Path $packageRoot "$language/sections") -Filter '*.tex' |
        Sort-Object Name |
        ForEach-Object { "$packageRelative/$language/sections/$($_.Name)" }
    $relativePaths += Get-ChildItem -LiteralPath (Join-Path $packageRoot "$language/figures") -File |
        Where-Object { $_.Extension -in @('.png', '.pdf') } |
        Sort-Object Name |
        ForEach-Object { "$packageRelative/$language/figures/$($_.Name)" }
}

$relativePaths = $relativePaths | Sort-Object -Unique

$artifacts = foreach ($relativePath in $relativePaths) {
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
    package = 'THESIS_DRAFT_5_INTRO_REPRO_IEEE'
    date = '2026-08-31'
    status = 'IEEE_BILINGUAL_DRAFT_5_INTRO_REPRO_COMPLETE'
    final_test_read = $false
    new_scientific_runs = 0
    scope = 'existing-evidence introduction, recent-literature, reproducibility, bilingual alignment, and IEEE typesetting revision only'
    formats = [ordered]@{
        english = [ordered]@{
            document_class = 'IEEEtran journal'
            columns = 2
            compiler = 'pdfLaTeX + BibTeX'
            pages = 17
        }
        chinese = [ordered]@{
            document_class = 'IEEEtran journal'
            columns = 2
            compiler = 'LuaLaTeX + BibTeX'
            pages = 13
        }
    }
    matched_structure = [ordered]@{
        body_sections = 8
        appendices = 2
        subsections_including_appendices = 54
        equations = 16
        tables = 12
        figure_environments = 4
        included_image_assets = 6
        labels = 44
    }
    protected_claims = @(
        'The four-state grouped-recognition negative is retained as a main result.',
        'The integrated physical device supports bounded two-state magnitude-spectrum selectivity within one closure.',
        'The 80/80 result is limited to the sealed five-node idealised reduced model.',
        'No physical, full-wave, causal, manufacturing, or construction-family conclusion follows from the 80/80 result.'
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
