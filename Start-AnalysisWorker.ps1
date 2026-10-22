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
$videoRoot = Join-Path $PSScriptRoot "backend\var\videos"
New-Item -ItemType Directory -Force -Path $videoRoot | Out-Null
$env:VIDEO_STORAGE_PATH = (Resolve-Path $videoRoot).Path

Set-Location .\backend
if (Test-Path .\.venv\Scripts\Activate.ps1) {
  .\.venv\Scripts\Activate.ps1
}

$env:FOOTBALLVISION_DEVICE = "0"
$env:FOOTBALLVISION_IMAGE_SIZE = "640"
$cudaReady = python -c "import torch; print(torch.cuda.is_available())"
if ($cudaReady -ne "True") {
  Write-Host "CUDA PyTorch qurulur (RTX GPU)..."
  python -m pip install --upgrade torch torchvision --index-url https://download.pytorch.org/whl/cu128
}
python -c "import torch; print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU fallback')"
python -m app.worker
