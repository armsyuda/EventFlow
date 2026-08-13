# 이벤트 플로우 0.3.24 작업 연속성

## 변경

- `EventFlow-Setup-0.3.24.exe` 단일 설치파일을 추가했다. 설치 마법사에서 설치 폴더를 선택하며 기본값은 `%LOCALAPPDATA%\Programs\EventFlow`이다.
- 사용자 지정 설치 폴더에는 `.eventflow-installed` 표시를 두어 이후 업데이트가 선택한 폴더에 그대로 적용된다. 사용자 데이터는 기존 `%LOCALAPPDATA%\EventCheckList`에 분리 보존한다.
- 앱 시작 시 새 GitHub Release가 있으면 확인창 없이 자동 다운로드한다. 다운로드·설치·재시작 동안 별도 인디케이터를 유지하고, 새 버전 기동 확인 실패 시 이전 설치본으로 자동 복구한다.
- 폴더 교체 업데이트에서도 Inno Setup 제거 프로그램을 보존한다. GitHub 태그 릴리스에는 ZIP 업데이트 파일과 설치 EXE를 함께 생성하도록 Windows workflow를 확장했다.

## 검증

- pytest 72개 통과.
- 사용자 지정 경로 설치, 실행, 설치 표시 파일과 제거 프로그램 생성을 확인했다.
- 폴더 교체, 자동 재실행, health 확인, 이전 설치 폴더 정리를 통합 검증했다.
- 기본 설치 위치에 0.3.24를 재설치하고 smoke test 종료 코드 0을 확인했다.

## 배포

- 설치파일: `03_Program/dist/installer/EventFlow-Setup-0.3.24.exe`
- 설치된 실행파일: `%LOCALAPPDATA%\Programs\EventFlow\EventFlow.exe`
- 사용자가 요청하기 전까지 GitHub에는 올리지 않는다.
