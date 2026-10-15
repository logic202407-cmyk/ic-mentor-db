# Render a print-ready HTML file to PDF with Microsoft Edge headless.
#
# Usage:
#   pwsh -File workbench/tools/make_aic_pdf.ps1 -Html <input.html> -Pdf <output.pdf>

param(
    [Parameter(Mandatory = $true)][string]$Html,
    [Parameter(Mandatory = $true)][string]$Pdf
)

$ErrorActionPreference = 'Continue'

$htmlPath = (Resolve-Path -LiteralPath $Html).Path
$pdfFull = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Pdf))
$pdfDir = Split-Path -Parent $pdfFull
if (-not (Test-Path -LiteralPath $pdfDir)) {
    New-Item -ItemType Directory -Force -Path $pdfDir | Out-Null
}
if (Test-Path -LiteralPath $pdfFull) { Remove-Item -LiteralPath $pdfFull -Force }

$candidates = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
)
$edge = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $edge) { throw "找不到 Microsoft Edge，无法渲染 PDF" }

# Isolated profile so the print job never touches the real browser profile.
$profileDir = Join-Path ([System.IO.Path]::GetTempPath()) ("edgepdf_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $profileDir | Out-Null

$htmlUri = ([System.Uri]$htmlPath).AbsoluteUri
Write-Host "rendering: $htmlUri"

# Edge writes benign diagnostics (field-trial, importer, fontconfig) to stderr.
# Redirect to a log file so noisy output never aborts the script.
$logFile = Join-Path ([System.IO.Path]::GetTempPath()) ("edgepdf_" + [guid]::NewGuid().ToString("N") + ".log")

& $edge `
    --headless=new `
    --disable-gpu `
    --no-first-run `
    --no-default-browser-check `
    --disable-extensions `
    --disable-sync `
    --user-data-dir="$profileDir" `
    --no-pdf-header-footer `
    --print-to-pdf="$pdfFull" `
    "$htmlUri" *> $logFile

# Edge returns before the file is always flushed; wait briefly for it to settle.
$deadline = (Get-Date).AddSeconds(45)
while (-not (Test-Path -LiteralPath $pdfFull) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 400
}
Start-Sleep -Milliseconds 500

Remove-Item -LiteralPath $profileDir -Recurse -Force -ErrorAction SilentlyContinue

if (-not (Test-Path -LiteralPath $pdfFull)) {
    Write-Host "--- Edge 输出（末尾 25 行）---"
    Get-Content -LiteralPath $logFile -Tail 25 -ErrorAction SilentlyContinue | Out-Host
    throw "PDF 未生成: $pdfFull"
}
Remove-Item -LiteralPath $logFile -Force -ErrorAction SilentlyContinue
$size = (Get-Item -LiteralPath $pdfFull).Length
Write-Host ("done: {0}  ({1:N0} bytes)" -f $pdfFull, $size)
