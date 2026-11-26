param([Parameter(Mandatory=$true)][string]$Version, [switch]$ReusePortable)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed: $LASTEXITCODE" }
}
if (-not $ReusePortable) {
    Invoke-Checked python @('-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed',
        '--name','AkademikSohbetYoneticisi','--icon','assets/app.ico','--add-data','assets/rumeli_logo.png;assets',
        '--add-data','assets/app.ico;assets','--collect-submodules','telethon','--collect-submodules','keyring.backends',
        '--collect-data','certifi','main.py')
}
Invoke-Checked python @('-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed',
    '--name','Updater','--distpath','dist/installer-helper','--workpath','build/updater',
    '--collect-data','certifi','updater.py')
$iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
if (-not (Test-Path $iscc)) { throw "Inno Setup 6 is required: $iscc" }
Invoke-Checked $iscc @("/DAppVersion=$Version", 'installer/setup.iss')
if (-not (Test-Path 'dist/AcademicChatManager-Setup.exe')) { throw 'Installer missing' }
