; Inno Setup script for RuLens — builds a single setup.exe installer.
#define AppName "RuLens"
#define AppFullName "RuLens — Переводчик экрана"
#define AppVersion "1.0.6"
#define ExeName "RuLens.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-47A8-9B0C-1234567890AB}
AppName={#AppFullName}
AppVersion={#AppVersion}
AppPublisher=RuLens
DefaultDirName={autopf}\RuLens
DefaultGroupName=RuLens
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=C:\Tools\RuLens\installer\out
OutputBaseFilename=RuLens-Setup
SetupIconFile=C:\Tools\RuLens\rulens.ico
UninstallDisplayIcon={app}\{#ExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startup"; Description: "Запускать RuLens при входе в Windows"; Flags: unchecked

[Files]
Source: "C:\Tools\RuLens\dist\RuLens\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppFullName}"; Filename: "{app}\{#ExeName}"
Name: "{group}\Удалить {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppFullName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "RuLens"; ValueData: """{app}\{#ExeName}"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#ExeName}"; Description: "Запустить RuLens"; Flags: nowait postinstall skipifsilent
