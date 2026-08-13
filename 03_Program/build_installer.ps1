param([switch]$SkipAppBuild)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$InnoCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
)
$Inno = $InnoCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1

if (-not (Test-Path -LiteralPath $Python)) {
    throw '프로젝트 Python 환경을 찾을 수 없습니다.'
}
if (-not $Inno) {
    throw 'Inno Setup 6을 찾을 수 없습니다. 먼저 Inno Setup을 설치해 주세요.'
}

Push-Location $ProjectRoot
try {
    if (-not $SkipAppBuild) {
        & (Join-Path $ProjectRoot 'build_windows.ps1')
        if ($LASTEXITCODE -ne 0) { throw '이벤트 플로우 빌드에 실패했습니다.' }
    }
    $Version = & $Python -c "from event_checklist import __version__; print(__version__)"
    if (-not $Version) { throw '앱 버전을 확인하지 못했습니다.' }
    $SourceDir = Join-Path $ProjectRoot 'dist\EventFlow'
    & $Inno "/DAppVersion=$Version" "/DSourceDir=$SourceDir" (Join-Path $ProjectRoot 'installer\EventFlow.iss')
    if ($LASTEXITCODE -ne 0) { throw '설치 프로그램 생성에 실패했습니다.' }
    Write-Output "BUILT $(Join-Path $ProjectRoot "dist\installer\EventFlow-Setup-$Version.exe")"
}
finally {
    Pop-Location
}
