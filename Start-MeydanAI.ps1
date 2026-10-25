param([switch]$Rebuild)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker Desktop is required. Start Docker Desktop and try again.'
}
if ($Rebuild) {
    docker compose build backend frontend
    if ($LASTEXITCODE -ne 0) { throw 'The MeydanAI images could not be built.' }
}
docker compose up -d --wait postgres
if ($LASTEXITCODE -ne 0) { throw 'The MeydanAI database could not start.' }
docker compose run --rm --no-deps backend alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'The MeydanAI database migrations could not be applied.' }
docker compose up -d --wait backend frontend
if ($LASTEXITCODE -ne 0) { throw 'The MeydanAI services could not start.' }

& (Join-Path $PSScriptRoot 'Start-AnalysisWorker.ps1') -CheckOnly
$runtimeRoot = Join-Path $PSScriptRoot 'backend\var'
$workerPidFile = Join-Path $runtimeRoot 'analysis-worker.pid'
$workerRunning = $false
if (Test-Path -LiteralPath $workerPidFile) {
    $storedWorkerPid = [int](Get-Content -LiteralPath $workerPidFile -Raw).Trim()
    $workerProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$storedWorkerPid" -ErrorAction SilentlyContinue
    $workerRunning = $workerProcess -and $workerProcess.CommandLine -like '*Start-AnalysisWorker.ps1*'
}
if (-not $workerRunning) {
    $workerShell = (Get-Process -Id $PID).Path
    $workerArguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $PSScriptRoot 'Start-AnalysisWorker.ps1') + '"'
    $workerProcess = Start-Process -FilePath $workerShell -ArgumentList $workerArguments -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtimeRoot 'analysis-worker.stdout.log') `
        -RedirectStandardError (Join-Path $runtimeRoot 'analysis-worker.stderr.log')
    Set-Content -LiteralPath $workerPidFile -Value $workerProcess.Id
}
Write-Host 'MeydanAI: http://localhost:3000'
Write-Host 'Create match -> Manage match -> Upload match video'
Write-Host "Worker logs: $runtimeRoot\analysis-worker.stderr.log"
