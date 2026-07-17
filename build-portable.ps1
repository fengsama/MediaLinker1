$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$NodeDirectory = "C:\Program Files\nodejs"
$NpmCommand = Join-Path $NodeDirectory "npm.cmd"
$PythonCommand = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $NpmCommand)) { throw "未找到 Node.js：$NpmCommand" }
if (-not (Test-Path $PythonCommand)) { throw "请先在 backend\.venv 创建 Python 虚拟环境" }

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
} finally { Pop-Location }

Write-Host "便携包已生成：$ProjectRoot\release\MediaLinker-Windows-x64.zip"
