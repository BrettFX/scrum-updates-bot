param(
    [string]$ShortcutName = "Scrum Updates Bot (WSL)",
    [string]$Distro,
    [string]$LinuxProjectDir,
    [switch]$UsePackagedBinary
)

$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent $PSScriptRoot
$desktopDir = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopDir ($ShortcutName + ".lnk")
$targetPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$launcherPath = Join-Path $rootDir "scripts\run_via_wsl.ps1"

function Convert-WindowsRepoDirToLinuxPath {
    param(
        [string]$WindowsRepoDir,
        [string]$DistroName
    )

    if ($WindowsRepoDir -match '^\\\\wsl(?:\.localhost)?\\([^\\]+)\\(.+)$') {
        $distroFromPath = $Matches[1]
        $linuxRemainder = $Matches[2] -replace '\\', '/'
        return @{
            LinuxPath = "/$linuxRemainder"
            Distro = if ($DistroName) { $DistroName } else { $distroFromPath }
        }
    }

    $wslArgs = @()
    if ($DistroName) {
        $wslArgs += @("-d", $DistroName)
    }

    $translatedPath = & wsl.exe @wslArgs wslpath -a $WindowsRepoDir
    if ($LASTEXITCODE -eq 0 -and $translatedPath) {
        return @{
            LinuxPath = $translatedPath.Trim()
            Distro = $DistroName
        }
    }

    return $null
}

function Resolve-LinuxProjectDirForShortcut {
    param(
        [string]$ExplicitLinuxProjectDir,
        [string]$WindowsRepoDir,
        [string]$RepoName,
        [string]$DistroName
    )

    if ($ExplicitLinuxProjectDir) {
        return @{
            LinuxPath = $ExplicitLinuxProjectDir
            Distro = $DistroName
        }
    }

    $translated = Convert-WindowsRepoDirToLinuxPath -WindowsRepoDir $WindowsRepoDir -DistroName $DistroName
    $effectiveDistro = $DistroName
    $wslArgs = @()
    if ($translated) {
        $effectiveDistro = $translated.Distro
        if ($effectiveDistro) {
            $wslArgs += @("-d", $effectiveDistro)
        }
        $trimmed = $translated.LinuxPath
        & wsl.exe @wslArgs bash -lc "test -d '$trimmed'"
        if ($LASTEXITCODE -eq 0) {
            return @{
                LinuxPath = $trimmed
                Distro = $effectiveDistro
            }
        }
    }

    if ($DistroName) {
        $wslArgs = @("-d", $DistroName)
    } else {
        $wslArgs = @()
    }

        $searchScriptTemplate = @'
repo_name='$RepoName'
for candidate in "\$HOME/GitHub/\$repo_name" "\$HOME/\$repo_name" "\$HOME/src/\$repo_name" "\$HOME/projects/\$repo_name"; do
    if [ -d "\$candidate" ]; then
        printf '%s\n' "\$candidate"
        exit 0
    fi
done
find "\$HOME" -maxdepth 4 -type d -name "\$repo_name" 2>/dev/null | head -n 1
'@
    $searchScript = $searchScriptTemplate.Replace('$RepoName', $RepoName)
    $discoveredPath = & wsl.exe @wslArgs bash -lc $searchScript
    if ($LASTEXITCODE -eq 0 -and $discoveredPath) {
        return @{
            LinuxPath = $discoveredPath.Trim()
            Distro = $DistroName
        }
    }

    throw @"
Unable to determine the Linux project directory automatically.

Re-run the shortcut creator with an explicit path, for example:
  .\scripts\create_windows_wsl_shortcut.ps1 -LinuxProjectDir /home/<you>/GitHub/$RepoName
"@
}

$repoName = Split-Path $rootDir -Leaf
$resolved = Resolve-LinuxProjectDirForShortcut -ExplicitLinuxProjectDir $LinuxProjectDir -WindowsRepoDir $rootDir -RepoName $repoName -DistroName $Distro
$resolvedLinuxProjectDir = $resolved.LinuxPath
$resolvedDistro = $resolved.Distro

$arguments = @(
    "-ExecutionPolicy", "Bypass",
    "-NoProfile",
    "-File", ('"' + $launcherPath + '"'),
    "-LinuxProjectDir", ('"' + $resolvedLinuxProjectDir + '"')
)

if ($resolvedDistro) {
    $arguments += @("-Distro", ('"' + $resolvedDistro + '"'))
}

if ($UsePackagedBinary) {
    $arguments += "-UsePackagedBinary"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.Arguments = ($arguments -join ' ')
$shortcut.WorkingDirectory = $rootDir
$shortcut.IconLocation = "$targetPath,0"
$shortcut.Save()

Write-Host "Created desktop shortcut: $shortcutPath"
Write-Host "Linux project directory: $resolvedLinuxProjectDir"
if ($resolvedDistro) {
    Write-Host "WSL distro: $resolvedDistro"
}