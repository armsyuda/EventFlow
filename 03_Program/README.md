# 이벤트 플로우(이플)

Windows에서 행사별 체크리스트, 자동 일정, 진행률과 달력을 관리하는 로컬 데스크톱 프로그램입니다.

## 개발 실행

```powershell
cd C:\Work\02_EventCheckList\03_Program
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe run.py
```

사용자 데이터는 `%LOCALAPPDATA%\EventCheckList`에 저장됩니다. 테스트 데이터와 분리하려면 다음처럼 실행합니다.

```powershell
$env:EVENT_CHECKLIST_DATA_DIR = "$PWD\.local-data"
.\.venv\Scripts\python.exe run.py
```

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest -q
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe run.py --smoke-test --data-dir .\.smoke-data
```

## Windows 배포

```powershell
.\build_windows.ps1
```

결과는 `dist\EventFlow\EventFlow.exe`에 생성됩니다. 배포본을 처음 실행하면 앱 전체가
`%LOCALAPPDATA%\Programs\EventFlow`에 고정 설치되고 바탕 화면과 시작 메뉴에 `이벤트 플로우`
바로가기를 만듭니다. DB와 백업은 실행 파일 폴더가 아닌 기존 `%LOCALAPPDATA%\EventCheckList`에 보존됩니다.

## 업데이트 배포

- 앱은 공개 GitHub Release의 `EventFlow-Windows.zip`을 확인합니다.
- `v0.3.10`처럼 앱 버전과 같은 태그를 push하면 GitHub Actions가 테스트, Windows 빌드와 Release 파일 생성을 자동 수행합니다.
- 사용자는 새 EXE를 직접 내려받거나 교체하지 않습니다. 앱 상단의 `업데이트` 버튼을 누르면 고정 설치 폴더가 자동 교체됩니다.
- 새 버전이 정상적으로 시작되지 않으면 이전 설치본으로 자동 복구합니다.
- 소스 수정은 실행 중인 EXE에 직접 반영될 수 없으므로, 수정된 프로그램 파일 생성 자체는 GitHub Actions가 담당합니다.
