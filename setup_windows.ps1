$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectRoot ".venv"
$requirementsPath = Join-Path $projectRoot "requirements.txt"

Write-Host "Project root: $projectRoot"

$pythonCmd = Get-Command py -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    throw "Python launcher 'py' was not found. Install Python 3.11 (64-bit) from python.org and try again."
}

$python311 = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
if (-not $python311) {
    throw "Python 3.11 is not installed. Install Python 3.11 (64-bit), then rerun this script."
}

Write-Host "Using Python 3.11: $python311"

if (-not (Test-Path -LiteralPath $venvPath)) {
    & py -3.11 -m venv $venvPath
}

$venvPython = Join-Path $venvPath "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Virtual environment creation failed. Expected interpreter not found at $venvPython"
}

& $venvPython -m pip install --upgrade pip wheel
& $venvPython -m pip install "setuptools<81"
& $venvPython -m pip install cmake
& $venvPython -m pip install -r $requirementsPath

Write-Host ""
Write-Host "Windows setup completed."
Write-Host "Run the app with:"
Write-Host "  .\\run_windows.bat"
