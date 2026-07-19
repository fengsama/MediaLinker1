#define MyAppName "MediaLinker"
#define MyAppVersion "0.7.0"
#define MyAppPublisher "fengsama"
#define MyAppURL "https://github.com/fengsama/MediaLinker1"
#define MyAppExeName "MediaLinker.exe"

[Setup]
AppId={{D8ACBFCF-7A8F-4B37-B24A-5F95AD638D6E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=MediaLinker-Setup-x64
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\MediaLinker-v{#MyAppVersion}.ico
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
SetupIconFile=..\assets\MediaLinker.ico

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："; Flags: unchecked

[Files]
Source: "..\dist\MediaLinker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "installed.marker"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\MediaLinker.ico"; DestDir: "{app}"; DestName: "MediaLinker-v{#MyAppVersion}.ico"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\MediaLinker-v{#MyAppVersion}.ico"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\MediaLinker-v{#MyAppVersion}.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Flags: nowait runascurrentuser

[UninstallRun]
; The desktop build has no visible window, so close its background process before
; Inno Setup starts removing files.  A non-zero taskkill result (already stopped)
; is harmless and must not prevent uninstalling.
Filename: "{sys}\taskkill.exe"; Parameters: "/F /T /IM {#MyAppExeName}"; Flags: runhidden waituntilterminated; RunOnceId: "StopMediaLinker"

[UninstallDelete]
; Runtime configuration, update state and logs are user-created and therefore are
; not part of Inno Setup's installed-file manifest.
Type: filesandordirs; Name: "{app}\config"
Type: filesandordirs; Name: "{localappdata}\Temp\medialinker-update-*"
Type: filesandordirs; Name: "{localappdata}\Temp\medialinker-installer-*"
; Remove any obsolete files left by an older portable/update build, then allow the
; uninstaller to remove itself and the now-empty application directory.
Type: filesandordirs; Name: "{app}\*"
Type: dirifempty; Name: "{app}"
