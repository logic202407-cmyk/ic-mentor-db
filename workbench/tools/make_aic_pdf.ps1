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
    # x86 优先：本机实测 Edge 安装在 Program Files (x86)，而 Program Files 下没有。
    # 顺序反过来的话会先命中一个不存在的路径再退回，虽然也能跑，但更容易误判。
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
)
$edge = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $edge) { throw "找不到 Microsoft Edge 或 Chrome，无法渲染 PDF" }

# Isolated profile so the print job never touches the real browser profile.
$profileDir = Join-Path ([System.IO.Path]::GetTempPath()) ("edgepdf_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $profileDir | Out-Null

$htmlUri = ([System.Uri]$htmlPath).AbsoluteUri
Write-Host "rendering: $htmlUri"

# 这里**不要**重定向浏览器的 stdout/stderr。
# 本机实测：一旦用 `*> $logFile` 或管道接管浏览器 stdio，Edge 会在启动阶段退出、
# 不写 PDF（子进程拿不到可用的管道句柄）。因此改为继承控制台句柄，并让
# Start-Process -Wait 等待进程真正结束——浏览器自己会打印少量无害诊断。
$arguments = @(
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-extensions',
    '--disable-sync',
    "--user-data-dir=$profileDir",
    '--no-pdf-header-footer',
    "--print-to-pdf=$pdfFull",
    $htmlUri
)

$proc = Start-Process -FilePath $edge -ArgumentList $arguments -NoNewWindow -PassThru -Wait

# Edge returns before the file is always flushed; wait briefly for it to settle.
$deadline = (Get-Date).AddSeconds(45)
while (-not (Test-Path -LiteralPath $pdfFull) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 400
}
Start-Sleep -Milliseconds 500

Remove-Item -LiteralPath $profileDir -Recurse -Force -ErrorAction SilentlyContinue

if (-not (Test-Path -LiteralPath $pdfFull)) {
    throw "PDF 未生成: $pdfFull（浏览器退出码 $($proc.ExitCode)）"
}
$size = (Get-Item -LiteralPath $pdfFull).Length
Write-Host ("done: {0}  ({1:N0} bytes)" -f $pdfFull, $size)
