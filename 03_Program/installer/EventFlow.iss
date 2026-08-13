#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\EventFlow"
#endif

[Setup]
AppId={{DA1FBD8D-5EA0-4F2A-B9E7-59E82DF258E9}
AppName=이벤트 플로우
AppVerName=이벤트 플로우 {#AppVersion}
AppVersion={#AppVersion}
AppPublisher=EventFlow
AppPublisherURL=https://github.com/armsyuda/EventFlow
AppSupportURL=https://github.com/armsyuda/EventFlow/issues
AppUpdatesURL=https://github.com/armsyuda/EventFlow/releases
DefaultDirName={localappdata}\Programs\EventFlow
DefaultGroupName=이벤트 플로우
DisableDirPage=no
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=EventFlow-Setup-{#AppVersion}
SetupIconFile=..\src\event_checklist\resources\assets\event_flow.ico
UninstallDisplayIcon={app}\EventFlow.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ChangesAssociations=no
ChangesEnvironment=no
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName=이벤트 플로우
VersionInfoDescription=이벤트 플로우 설치 프로그램
VersionInfoCompany=EventFlow

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕 화면에 바로가기 만들기"; GroupDescription: "추가 바로가기:"; Flags: checkedonce

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "eventflow-installed.marker"; DestDir: "{app}"; DestName: ".eventflow-installed"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\이벤트 플로우"; Filename: "{app}\EventFlow.exe"; WorkingDir: "{app}"; IconFilename: "{app}\EventFlow.exe"
Name: "{autodesktop}\이벤트 플로우"; Filename: "{app}\EventFlow.exe"; WorkingDir: "{app}"; IconFilename: "{app}\EventFlow.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\EventFlow.exe"; Description: "이벤트 플로우 실행"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\.eventflow-installed"

[Code]
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    if Pos(Uppercase(ExpandConstant('{pf}')), Uppercase(WizardDirValue)) = 1 then
    begin
      MsgBox('관리자 권한 없이 자동 업데이트할 수 있도록 사용자 폴더를 선택해 주세요.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;
