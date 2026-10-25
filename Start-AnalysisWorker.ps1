param([switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot 'backend')
$workerPython = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $workerPython)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 or newer is required.' }
}

$envFile = Join-Path $PSScriptRoot 'backend\.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item (Join-Path $PSScriptRoot 'backend\.env.example') $envFile
}
foreach ($line in Get-Content -LiteralPath $envFile) {
    $entry = $line.Trim()
    if (-not $entry -or $entry.StartsWith('#') -or -not $entry.Contains('=')) { continue }
    $name, $value = $entry.Split('=', 2)
    Set-Item -Path "Env:$($name.Trim())" -Value $value.Trim().Trim('"').Trim("'")
}

$env:FOOTBALLVISION_ENABLED = '1'
$env:FOOTBALLVISION_ROOT = (Resolve-Path (Join-Path $PSScriptRoot 'footballvision-ai')).Path
$env:FOOTBALLVISION_CONFIG = Join-Path $env:FOOTBALLVISION_ROOT 'configs\config.yaml'
$videoRoot = Join-Path $PSScriptRoot 'backend\var\videos'
New-Item -ItemType Directory -Force -Path $videoRoot | Out-Null
$env:VIDEO_STORAGE_PATH = (Resolve-Path $videoRoot).Path
if (-not $env:API_BASE_URL) { $env:API_BASE_URL = 'http://127.0.0.1:8000' }
if (-not $env:FOOTBALLVISION_DEVICE) { $env:FOOTBALLVISION_DEVICE = 'auto' }
if (-not $env:FOOTBALLVISION_IMAGE_SIZE) { $env:FOOTBALLVISION_IMAGE_SIZE = '640' }
if (-not $env:FOOTBALLVISION_RENDER) { $env:FOOTBALLVISION_RENDER = '0' }
if (-not $env:FOOTBALLVISION_PLAYER_CLIPS) { $env:FOOTBALLVISION_PLAYER_CLIPS = '0' }
if (-not $env:FOOTBALLVISION_FRAME_STRIDE) { $env:FOOTBALLVISION_FRAME_STRIDE = '1' }
if (-not $env:FOOTBALLVISION_BATCH) { $env:FOOTBALLVISION_BATCH = '2' }
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'

& $workerPython -c 'import torch, ultralytics, supervision, trackers, scipy, sklearn, pandas, yaml, fastapi, psycopg, rapidocr, onnxruntime'
if ($LASTEXITCODE -ne 0) {
    & $workerPython -m pip install -e '.[demo]' -r (Join-Path $env:FOOTBALLVISION_ROOT 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'FootballVision dependencies could not be installed.' }
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw 'FFmpeg was not found on PATH. Install FFmpeg and reopen the terminal.'
}
& $workerPython -c 'import torch; print("Analysis device:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU")'
if ($LASTEXITCODE -ne 0) { throw 'The analysis runtime could not start.' }
& $workerPython -c 'from app.worker.api import WorkerApi, worker_settings; WorkerApi(*worker_settings()[:2]).list_queued(); print("Worker API connection: OK")'
if ($LASTEXITCODE -ne 0) { throw 'The worker could not connect to the API. Check API_BASE_URL and INTERNAL_WORKER_TOKEN.' }
if ($CheckOnly) { return }
Write-Host "MeydanAI video worker: $env:API_BASE_URL"
& $workerPython -m app.worker
if ($LASTEXITCODE -ne 0) { throw 'The video worker stopped unexpectedly. Check the worker log.' }
