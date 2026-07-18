$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$NodeDirectory = "C:\Program Files\nodejs"
$NpmCommand = Join-Path $NodeDirectory "npm.cmd"
$PythonCommand = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $NpmCommand)) { throw "Node.js was not found: $NpmCommand" }
if (-not (Test-Path $PythonCommand)) { throw "Create the Python virtual environment at backend\.venv first." }

$env:Path = "$NodeDirectory;$env:Path"
Push-Location (Join-Path $ProjectRoot "frontend")
try {
    & $NpmCommand install
    & $NpmCommand run build
} finally { Pop-Location }

& $PythonCommand -m pip install -r (Join-Path $ProjectRoot "backend\requirements.txt") pyinstaller

Push-Location $ProjectRoot
try {
    & $PythonCommand -m PyInstaller --noconfirm --clean "MediaLinker.spec"
    New-Item -ItemType Directory -Path "release" -Force | Out-Null
    Compress-Archive -Path "dist\MediaLinker" -DestinationPath "release\MediaLinker-Windows-x64.zip" -Force

    $InnoCandidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $InnoCompiler = $InnoCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($InnoCompiler) {
        & $InnoCompiler "installer\MediaLinker.iss"
        Write-Host "Installer created: $ProjectRoot\release\MediaLinker-Setup-x64.exe"
    } else {
        Write-Host "Inno Setup is not installed. GitHub Actions will build the installer."
    }
} finally { Pop-Location }

Write-Host "Portable package created: $ProjectRoot\release\MediaLinker-Windows-x64.zip"
