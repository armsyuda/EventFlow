$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $Python)) {
    throw '먼저 .venv를 만들고 requirements-dev.txt를 설치하세요.'
}

Push-Location $ProjectRoot
try {
    & $Python -m PyInstaller --noconfirm --clean --windowed --onedir `
        --name EventFlow `
        --icon (Join-Path $ProjectRoot 'src\event_checklist\resources\assets\event_flow.ico') `
        --add-data "$(Join-Path $ProjectRoot 'src\event_checklist\resources\assets');event_checklist/resources/assets" `
        --paths (Join-Path $ProjectRoot 'src') `
        --collect-data event_checklist `
        (Join-Path $ProjectRoot 'run.py')
    if ($LASTEXITCODE -ne 0) { throw 'Windows 패키징에 실패했습니다.' }
    Write-Output "BUILT $(Join-Path $ProjectRoot 'dist\EventFlow\EventFlow.exe')"
}
finally {
    Pop-Location
}
