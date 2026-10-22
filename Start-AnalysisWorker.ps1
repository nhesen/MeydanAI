# Production match-video worker. Uses FootballVision, not the YOLO demo UI.
Set-Location $PSScriptRoot
$env:FOOTBALLVISION_ENABLED = "1"
$env:FOOTBALLVISION_ROOT = (Resolve-Path .\footballvision-ai).Path
$env:FOOTBALLVISION_CONFIG = (Resolve-Path .\footballvision-ai\configs\config.yaml).Path

$envFile = Join-Path $PSScriptRoot "backend\.env"
if (-not (Test-Path $envFile)) {
  Copy-Item (Join-Path $PSScriptRoot "backend\.env.example") $envFile
}
Get-Content $envFile | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { return }
  $name, $value = $line.Split("=", 2)
  Set-Item -Path "Env:$($name.Trim())" -Value $value.Trim()
}

Set-Location .\backend
if (Test-Path .\.venv\Scripts\Activate.ps1) {
  .\.venv\Scripts\Activate.ps1
}
python -m app.worker
