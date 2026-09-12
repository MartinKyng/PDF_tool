; Inno Setup script for the PDF Tool Windows installer.
;
; The Python build script (packaging/build_exe.py) compiles this with:
;     ISCC /DAppVersion=<version> /O<dist> packaging/installer.iss
; which produces dist\PDFTool-Setup-<version>.exe
;
; It expects the two single-file executables produced by PyInstaller to be in
; ..\dist relative to this file (i.e. <repo>\dist).

#ifndef AppVersion
  #error "AppVersion must be supplied by packaging/build_exe.py"
#endif

#define MyAppName "PDF Tool"
#define MyAppPublisher "PDF Tool"
#define MyAppExeName "pdf-join-gui.exe"

[Setup]
AppId={{8F3C7A21-5B2E-4C9D-9F10-2E6A7C4B9D31}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\PDFTool
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=PDFTool-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; The GUI and the console tool, exactly as PyInstaller produced them.
Source: "..\dist\pdf-join-gui.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\pdf-join.exe";     DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

; Put {app} on the user's PATH so `pdf-join` works from a command prompt.
[Code]
const
  EnvKey = 'Environment';

function AddToPath(const Dir: string): Boolean;
var
  Current: string;
begin
  Result := False;
  if RegQueryStringValue(HKEY_CURRENT_USER, EnvKey, 'Path', Current) then
  begin
    if Pos(';' + Dir + ';', ';' + Current + ';') = 0 then
      Result := RegWriteStringValue(HKEY_CURRENT_USER, EnvKey, 'Path', Current + ';' + Dir);
  end
  else
    Result := RegWriteStringValue(HKEY_CURRENT_USER, EnvKey, 'Path', Dir);
end;

function RemoveFromPath(const Dir: string): Boolean;
var
  Current: string;
begin
  Result := False;
  if RegQueryStringValue(HKEY_CURRENT_USER, EnvKey, 'Path', Current) then
  begin
    if Pos(';' + Dir + ';', ';' + Current + ';') <> 0 then
    begin
      Current := StringChange(Current, ';' + Dir, '');
      Current := StringChange(Current, Dir + ';', '');
      Current := StringChange(Current, Dir, '');
      Result := RegWriteStringValue(HKEY_CURRENT_USER, EnvKey, 'Path', Current);
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    AddToPath(ExpandConstant('{app}'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RemoveFromPath(ExpandConstant('{app}'));
end;
