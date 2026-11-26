param([Parameter(Mandatory=$true)][string]$Version)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$root = Join-Path $env:RUNNER_TEMP ('acm-smoke-' + [Guid]::NewGuid().ToString())
$setup = (Resolve-Path 'dist/AcademicChatManager-Setup.exe').Path
$install = Start-Process -FilePath $setup -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',('/DIR="' + $root + '"')) -Wait -PassThru
if ($install.ExitCode -ne 0) { throw "Installer failed: $($install.ExitCode)" }
try {
    $app = Join-Path $root 'AkademikSohbetYoneticisi.exe'
    $helper = Join-Path $root 'Updater.exe'
    if (-not (Test-Path $app) -or -not (Test-Path $helper)) { throw 'Installed files missing' }
    $process = Start-Process -FilePath $app -ArgumentList @('--self-test',$Version) -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "Installed application smoke test failed: $($process.ExitCode)" }
} finally {
    $uninstall = Join-Path $root 'unins000.exe'
    if (Test-Path $uninstall) {
        $result = Start-Process -FilePath $uninstall -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -Wait -PassThru
        if ($result.ExitCode -ne 0) { throw "Uninstall failed: $($result.ExitCode)" }
    }
}
