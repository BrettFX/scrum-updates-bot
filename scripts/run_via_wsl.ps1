param(
    [string]$Distro,
    [string]$LinuxProjectDir,
    [switch]$UsePackagedBinary
)

$ErrorActionPreference = "Stop"

$wslArgs = @()
if ($Distro) {
    $wslArgs += @("-d", $Distro)
}

function Convert-WindowsRepoDirToLinuxPath {
    param(
        [string]$WindowsRepoDir,
        [string[]]$ResolvedWslArgs
    )

    if ($WindowsRepoDir -match '^\\\\wsl(?:\.localhost)?\\([^\\]+)\\(.+)$') {
        $distroFromPath = $Matches[1]
        $linuxRemainder = $Matches[2] -replace '\\', '/'
        if (-not $Distro) {
            $script:Distro = $distroFromPath
            $script:wslArgs = @('-d', $distroFromPath)
        }
        return "/$linuxRemainder"
    }

    $resolvedPath = & wsl.exe @ResolvedWslArgs wslpath -a $WindowsRepoDir
    if ($LASTEXITCODE -eq 0 -and $resolvedPath) {
        return $resolvedPath.Trim()
    }

    return $null
}

function Resolve-LinuxProjectDir {
    param(
        [string]$ExplicitLinuxProjectDir,
        [string[]]$ResolvedWslArgs
    )

    if ($ExplicitLinuxProjectDir) {
        return $ExplicitLinuxProjectDir
    }

    $windowsRepoDir = Split-Path -Parent $PSScriptRoot
    $resolvedPath = Convert-WindowsRepoDirToLinuxPath -WindowsRepoDir $windowsRepoDir -ResolvedWslArgs $ResolvedWslArgs
    if (-not $resolvedPath) {
        throw @"
Unable to determine the Linux project directory automatically.

Pass it explicitly, for example:
  .\scripts\run_via_wsl.ps1 -LinuxProjectDir /home/<you>/GitHub/scrum-updates-bot
"@
    }

    return $resolvedPath.Trim()
}

$resolvedLinuxProjectDir = Resolve-LinuxProjectDir -ExplicitLinuxProjectDir $LinuxProjectDir -ResolvedWslArgs $wslArgs

$linuxCommand = if ($UsePackagedBinary) {
    "cd '$resolvedLinuxProjectDir' && ./dist/scrum-updates-bot/scrum-updates-bot"
} else {
    "cd '$resolvedLinuxProjectDir' && ./scripts/run_linux.sh"
}

& wsl.exe @wslArgs bash -lc $linuxCommand