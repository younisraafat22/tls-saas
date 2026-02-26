; TLS Appointment Checker - Professional Installer Script
; Inno Setup Configuration

#define MyAppName "TLS Appointment Checker"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "TLS Appointment Checker"
#define MyAppURL "https://tls-saas.vercel.app"
#define MyAppExeName "TLSAppointmentChecker.exe"
#define MyAppSupportEmail "tlsappointmentchecker@gmail.com"

[Setup]
; Application Information
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppContact={#MyAppSupportEmail}

; Installation Directories
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output Configuration
OutputDir=installer_output
OutputBaseFilename=TLS_Appointment_Checker_v{#MyAppVersion}_Setup
SetupIconFile=Logos\icon_BLACK.ico
Compression=lzma2/max
SolidCompression=yes

; Windows Version
WizardStyle=modern
MinVersion=10.0.17763
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; License and Info Files
LicenseFile=LICENSE.txt
InfoBeforeFile=TERMS_AND_DISCLAIMER.md

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main Application (from PyInstaller onedir output)
Source: "dist\TLSAppointmentChecker\TLSAppointmentChecker.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\TLSAppointmentChecker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Environment configuration (backend URL, website URL, etc.)
Source: ".env"; DestDir: "{app}"; Flags: ignoreversion

; Documentation
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\Logos\icon_BLACK.ico"; WorkingDir: "{app}"
Name: "{group}\License"; Filename: "{app}\LICENSE.txt"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Desktop Icon
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\Logos\icon_BLACK.ico"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; Launch app after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function IsChromeInstalled: Boolean;
var
  ChromePath: String;
begin
  // Check common Chrome installation paths
  ChromePath := 'C:\Program Files\Google\Chrome\Application\chrome.exe';
  Result := FileExists(ChromePath);
  
  if not Result then
  begin
    ChromePath := 'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe';
    Result := FileExists(ChromePath);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Check if Chrome is installed (required for the app)
    if not IsChromeInstalled then
    begin
      MsgBox('Google Chrome is not installed on your system.' + #13#10 + #13#10 +
             'This application requires Chrome to monitor appointments.' + #13#10 + #13#10 +
             'Please download and install Chrome from:' + #13#10 +
             'https://www.google.com/chrome/', 
             mbInformation, MB_OK);
    end;
  end;
end;