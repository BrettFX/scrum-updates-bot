param(
    [switch]$SetupOnly,
    [switch]$BuildOnly,
    [switch]$WithInstaller
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $RootDir ".venv\Scripts\python.exe"
$SpecFile = Join-Path $RootDir "scrum-updates-bot.spec"
$InstallerScript = Join-Path $RootDir "packaging\windows\scrum-updates-bot.iss"
$InnoCompiler = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
$SupportedPythonMinors = @(12, 11)

if ($SetupOnly -and $BuildOnly) {
    throw "Choose either -SetupOnly or -BuildOnly, not both."
}

Set-Location $RootDir

function Test-SupportedPythonMinor {
    param(
        [int]$Major,
        [int]$Minor
    )

    if ($Major -ne 3) {
        return $false
    }

    return $SupportedPythonMinors -contains $Minor
}

function Get-PythonBootstrapCommand {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        foreach ($versionArg in @("-3.12", "-3.11")) {
            try {
                & py $versionArg -c "import sys; print(sys.version)" *> $null
                if ($LASTEXITCODE -eq 0) {
                    return @{ FilePath = "py"; Arguments = @($versionArg, "-m", "venv", ".venv") }
                }
            } catch {
            }
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        try {
            $versionText = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
            if ($LASTEXITCODE -eq 0) {
                $parts = $versionText.Trim().Split('.')
                if (Test-SupportedPythonMinor -Major ([int]$parts[0]) -Minor ([int]$parts[1])) {
                    return @{ FilePath = "python"; Arguments = @("-m", "venv", ".venv") }
                }
            }
        } catch {
        }
    }

    return $null
}

function Ensure-Venv {
    if (-not (Test-Path $PythonExe)) {
        $bootstrap = Get-PythonBootstrapCommand
        if (-not $bootstrap) {
            throw @"
No suitable native Windows Python 3.11+ runtime was found.

Recommended fixes:
1. Install Python 3.12 for Windows from python.org and enable the launcher / PATH option during install.
2. Or install Python 3.11 if you specifically need that line.
3. Re-run .\scripts\install_windows.ps1 after `py -0p` shows Python 3.12 or 3.11.
4. If you only have Python 3.13, use the GitHub Actions Windows build or a published GitHub Release instead of local packaging.

Helpful checks:
  py -0p
  python --version
"@
        }

    $bootstrapArgs = $bootstrap.Arguments
    & $bootstrap.FilePath @bootstrapArgs
    }

    if (-not (Test-Path $PythonExe)) {
        throw "Virtual environment creation failed. The expected interpreter was not created at $PythonExe"
    }
}

function Install-Dependencies {
    Ensure-Venv
    $versionText = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    $parts = $versionText.Trim().Split('.')
    if (-not (Test-SupportedPythonMinor -Major ([int]$parts[0]) -Minor ([int]$parts[1]))) {
        throw @"
Local Windows packaging is currently supported only on Python 3.12 or 3.11.

The current virtual environment is using Python $versionText, which is likely to produce a broken PySide6 executable on Windows.

Recommended options:
1. Install Python 3.12 and rebuild from a fresh source bundle.
2. Or use the GitHub Actions Windows build / published release artifacts instead of building locally.
"@
    }

    & $PythonExe -m pip install --upgrade pip
    & $PythonExe -m pip install -e ".[build]"
}

function Build-Executable {
    if (-not (Test-Path $PythonExe)) {
        throw "Missing virtual environment. Run .\scripts\install_windows.ps1 first."
    }

    if (-not (Test-Path $SpecFile)) {
        throw "Missing PyInstaller spec file: $SpecFile"
    }

    & $PythonExe -m PyInstaller --noconfirm --clean $SpecFile

    $exePath = Join-Path $RootDir "dist\scrum-updates-bot\scrum-updates-bot.exe"
    if (-not (Test-Path $exePath)) {
        throw "Build completed without producing the expected executable: $exePath"
    }

    Write-Host "Windows build complete: $exePath"
}

function Build-Installer {
    if (-not (Test-Path $InstallerScript)) {
        throw "Missing Inno Setup script: $InstallerScript"
    }

    if (-not (Test-Path $InnoCompiler)) {
        throw "Inno Setup 6 was not found at '$InnoCompiler'. Install Inno Setup 6 to build the Windows installer."
    }

    & $InnoCompiler $InstallerScript
    Write-Host "Windows installer build complete. Check output\\windows-installer."
}

$shouldSetup = -not $BuildOnly
$shouldBuild = -not $SetupOnly

if ($shouldSetup) {
    Install-Dependencies
}

if ($shouldBuild) {
    if (-not $shouldSetup -and -not (Test-Path $PythonExe)) {
        throw "Missing virtual environment. Run .\scripts\install_windows.ps1 first."
    }
    Build-Executable
}

if ($WithInstaller) {
    Build-Installer
}

if ($SetupOnly) {
    Write-Host "Windows environment is ready."
    Write-Host "Run the app with: .\\.venv\\Scripts\\python.exe -m scrum_updates_bot"
} elseif ($WithInstaller) {
    Write-Host "Run the packaged app with: .\\dist\\scrum-updates-bot\\scrum-updates-bot.exe"
} else {
    Write-Host "Run the packaged app with: .\\dist\\scrum-updates-bot\\scrum-updates-bot.exe"
}