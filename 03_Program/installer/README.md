# 이벤트 플로우 Windows 설치파일

## 로컬 생성

```powershell
.\build_installer.ps1
```

`dist\EventFlow`를 먼저 다시 빌드한 뒤 `dist\installer\EventFlow-Setup-버전.exe`를 생성한다.
이미 앱 빌드가 끝났다면 `-SkipAppBuild`를 사용할 수 있다.

## 설치·업데이트 원칙

- 설치 마법사는 설치 폴더를 항상 표시하며 기본값은 `%LOCALAPPDATA%\Programs\EventFlow`이다.
- 관리자 권한 없이 자동 업데이트할 수 있도록 Program Files는 선택하지 못하게 한다.
- 사용자 데이터와 백업은 설치 폴더 밖의 `%LOCALAPPDATA%\EventCheckList`에 유지한다.
- 설치 위치의 `.eventflow-installed` 표시를 기준으로 사용자 지정 설치 위치를 인식한다.
- GitHub Release의 `EventFlow-Windows.zip`은 앱 내부 자동 업데이트에 사용하고 설치 EXE는 최초 설치에 사용한다.
