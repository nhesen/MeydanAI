$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot 'backend')
$demoPython = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $demoPython)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 or newer is required.' }
}
& $demoPython -c 'import ultralytics, fastapi, multipart, lap'
if ($LASTEXITCODE -ne 0) {
    & $demoPython -m pip install -e '.[demo]'
    if ($LASTEXITCODE -ne 0) { throw 'Demo dependencies could not be installed.' }
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw 'FFmpeg was not found on PATH. Install FFmpeg, reopen the terminal and try again.'
}
Write-Host 'MeydanAI YOLO demo: http://127.0.0.1:8010'
Write-Host 'Keep this terminal running. Press Ctrl+C to stop.'
& $demoPython -m uvicorn app.demo.main:app --host 127.0.0.1 --port 8010
