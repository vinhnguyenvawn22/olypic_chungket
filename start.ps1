param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8000,
    [switch]$Rebuild
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$appUrl = "http://127.0.0.1:$Port"
$listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
if ($listeners | Where-Object { $_.Port -eq $Port }) {
    $isClassroom = $false
    try {
        $health = Invoke-RestMethod -Uri "$appUrl/api/health" -TimeoutSec 3
        $modelList = Invoke-RestMethod -Uri "$appUrl/api/models" -TimeoutSec 3
        $modelIds = @($modelList.models | ForEach-Object { $_.id } | Sort-Object)
        $isClassroom = $health.status -eq 'ok' -and $modelList.default -eq 'uneti15' -and ($modelIds -join ',') -eq 'btc,uneti15'
    } catch {
        $isClassroom = $false
    }
    if ($isClassroom) {
        Write-Host "UNETI Smart Classroom da chay: $appUrl" -ForegroundColor Green
        Write-Host 'Mo dia chi tren trong trinh duyet. Khong can chay them server.'
        Write-Host 'Neu can chay rieng tren cong khac: .\start.ps1 -Port 8001'
        return
    }
    throw "Cong $Port dang duoc ung dung khac su dung. Thu: .\start.ps1 -Port 8001"
}

$frontendEntry = Join-Path $projectRoot 'frontend/dist/index.html'
if ($Rebuild -or -not (Test-Path -LiteralPath $frontendEntry)) {
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        if (-not (Test-Path -LiteralPath 'node_modules')) {
            npm ci --include=dev --no-fund --no-audit
            if ($LASTEXITCODE -ne 0) { throw 'Khong cai duoc frontend dependencies.' }
        }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build that bai.' }
    } finally { Pop-Location }
} else {
    Write-Host 'Su dung giao dien da build san; khong can npm hoac ket noi mang.' -ForegroundColor Green
}
Push-Location $projectRoot
try {
    Write-Host "UNETI Smart Classroom: $appUrl" -ForegroundColor Green
    python -m uvicorn backend.main:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Khong khoi dong duoc server. Kiem tra thong bao loi phia tren.' }
} finally { Pop-Location }
