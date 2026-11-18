param(
    [switch]$NoPause
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$LogPath = Join-Path $ProjectRoot 'build_windows.log'
$TranscriptStarted = $false
$BuildSucceeded = $false

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Program,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    Write-Host ("`n> {0} {1}" -f $Program, ($Arguments -join ' ')) -ForegroundColor Cyan
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw ("Komut başarısız oldu (çıkış kodu {0}): {1}" -f $LASTEXITCODE, $Program)
    }
}

try {
    Set-Location $ProjectRoot
    Start-Transcript -Path $LogPath -Append | Out-Null
    $TranscriptStarted = $true

    Write-Host 'Akademik Sohbet Yöneticisi Windows derlemesi' -ForegroundColor White
    Write-Host "Proje klasörü: $ProjectRoot"
    Write-Host "Ayrıntılı kayıt: $LogPath"

    $PythonLauncher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if (-not $PythonLauncher) {
        $PythonLauncher = Get-Command 'py' -ErrorAction SilentlyContinue
    }
    if (-not $PythonLauncher) {
        throw 'Python Launcher (py) bulunamadı. Python 3.12 x64 kurup kurulum sırasında "Add python.exe to PATH" seçeneğini etkinleştirin.'
    }

    Invoke-Checked $PythonLauncher.Source @('-3.12', '--version')
    Invoke-Checked $PythonLauncher.Source @('-3.12', '-m', 'venv', '.venv')

    $VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path $VenvPython)) {
        throw "Sanal ortam oluşturulamadı: $VenvPython"
    }

    Invoke-Checked $VenvPython @('-m', 'pip', 'install', '--upgrade', 'pip')
    Invoke-Checked $VenvPython @('-m', 'pip', 'install', '-r', 'requirements-dev.txt')
    Invoke-Checked $VenvPython @('-m', 'PyInstaller', '--noconfirm', '--clean', 'AcademicChatManager.spec')
    Invoke-Checked $VenvPython @(
        '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
        '--name', 'AkademikSohbetYoneticisi-OneFile', '--icon', 'assets\app.ico',
        '--add-data', 'assets\rumeli_logo.png;assets', '--add-data', 'assets\app.ico;assets',
        '--collect-submodules', 'telethon', '--collect-submodules', 'keyring.backends',
        '--collect-data', 'certifi', 'main.py'
    )

    Write-Host "`nDerleme tamamlandı." -ForegroundColor Green
    Write-Host "Portable klasör: $ProjectRoot\dist\AkademikSohbetYoneticisi\AkademikSohbetYoneticisi.exe"
    Write-Host "Tek dosyalı EXE: $ProjectRoot\dist\AkademikSohbetYoneticisi-OneFile.exe"
    $BuildSucceeded = $true
}
catch {
    Write-Host "`nDERLEME BAŞARISIZ: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Ayrıntılar: $LogPath" -ForegroundColor Yellow
}
finally {
    if ($TranscriptStarted) {
        Stop-Transcript | Out-Null
    }
    if (-not $NoPause) {
        if ($BuildSucceeded) {
            Read-Host 'Pencereyi kapatmak için Enter tuşuna basın' | Out-Null
        }
        else {
            Read-Host 'Hata mesajını inceledikten sonra pencereyi kapatmak için Enter tuşuna basın' | Out-Null
        }
    }
}

if (-not $BuildSucceeded) {
    exit 1
}
