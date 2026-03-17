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
OutputDir=..\..\output\windows-installer
OutputBaseFilename=scrum-updates-bot-setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\..\dist\scrum-updates-bot\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function IsOllamaInstalled(): Boolean;
begin
  Result :=
    FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe')) or
    FileExists(ExpandConstant('{localappdata}\Programs\Ollama\Ollama.exe')) or
    FileExists(ExpandConstant('{autopf}\Ollama\ollama.exe')) or
    FileExists(ExpandConstant('{autopf}\Ollama\Ollama.exe'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    if IsOllamaInstalled() then
    begin
      SuppressibleMsgBox(
        'Ollama appears to be installed.' + #13#10#13#10 +
        'Start Ollama and pull a model such as llama3.2:3b before generating updates.' + #13#10#13#10 +
        'Example commands:' + #13#10 +
        '  ollama serve' + #13#10 +
        '  ollama pull llama3.2:3b',
        mbInformation,
        MB_OK,
        IDOK
      );
    end
    else if SuppressibleMsgBox(
      'Scrum Updates Bot requires Ollama to be installed separately on Windows.' + #13#10#13#10 +
      'Would you like to install Ollama now?' + #13#10#13#10 +
      'The installer will run this PowerShell command:' + #13#10 +
      '  irm https://ollama.com/install.ps1 | iex',
      mbConfirmation,
      MB_YESNO,
      IDYES
    ) = IDYES then
    begin
      if not ShellExec(
        'open',
        'powershell.exe',
        '-ExecutionPolicy Bypass -NoProfile -Command "irm https://ollama.com/install.ps1 | iex"',
        '',
        SW_SHOWNORMAL,
        ewNoWait,
        ResultCode
      ) then
      begin
        SuppressibleMsgBox(
          'Failed to launch the Ollama installer automatically.' + #13#10#13#10 +
          'Run this command manually in PowerShell:' + #13#10 +
          '  irm https://ollama.com/install.ps1 | iex',
          mbError,
          MB_OK,
          IDOK
        );
      end;
    end;
  end;
end;