#define MyAppName "Scrum Updates Bot"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Brian Allen"
#define MyAppExeName "scrum-updates-bot.exe"

[Setup]
AppId={{2D0EA763-5504-4D66-9028-39C7DCC108D5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=output\windows-installer
OutputBaseFilename=scrum-updates-bot-setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\scrum-updates-bot\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    SuppressibleMsgBox(
      'Scrum Updates Bot requires Ollama to be installed separately on Windows.' + #13#10#13#10 +
      'Install Ollama, start it, and pull a model such as llama3.2:3b before generating updates.' + #13#10#13#10 +
      'Example commands:' + #13#10 +
      '  ollama serve' + #13#10 +
      '  ollama pull llama3.2:3b',
      mbInformation,
      MB_OK,
      IDOK
    );
  end;
end;