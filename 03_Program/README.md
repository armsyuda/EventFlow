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

결과는 `dist\EventFlow\EventFlow.exe`에 생성됩니다. DB와 백업은 실행 파일 폴더가 아닌 기존 `%LOCALAPPDATA%\EventCheckList`에 보존됩니다.
