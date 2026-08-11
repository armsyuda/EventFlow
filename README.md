# 이벤트 플로우(EventFlow, 이플)

Windows에서 행사 준비 체크리스트, 일정, 달력과 예산 정산을 한곳에서 관리하는 PySide6 데스크톱 프로그램입니다.

## 개발 실행

```powershell
cd 03_Program
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe run.py
```

## 테스트와 Windows 빌드

```powershell
cd 03_Program
.\.venv\Scripts\python.exe -m pytest -q
.\build_windows.ps1
```

실행 파일은 `03_Program/dist/EventFlow/EventFlow.exe`에 생성됩니다. 사용자 데이터는 앱 폴더가 아닌 `%LOCALAPPDATA%\EventCheckList`에 저장되므로 앱 업데이트 후에도 유지됩니다.

## 릴리스와 자동 업데이트

- `v0.3.2` 같은 버전 태그를 GitHub에 푸시하면 Windows 테스트·빌드 후 GitHub Release가 생성됩니다.
- Release에는 반드시 `EventFlow-Windows.zip`이 포함됩니다.
- 이플은 시작할 때 최신 공개 Release를 확인하고 새 버전이 있을 때만 상단의 업데이트 버튼을 활성화합니다.
- 토큰을 프로그램에 저장하지 않으므로 자동 업데이트를 사용하려면 저장소와 Release를 공개 상태로 운영해야 합니다.
