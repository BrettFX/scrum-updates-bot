$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $RootDir ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
	throw "Missing virtual environment. Create .venv and install .[dev,build] before building."
}

Set-Location $RootDir
& $PythonExe -m PyInstaller --noconfirm --clean --onedir --paths src --name scrum-updates-bot src/scrum_updates_bot/main.py