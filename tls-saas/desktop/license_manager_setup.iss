[Setup]
AppName=TLS License Manager
AppVersion=1.0.0
AppPublisher=TLS Appointment Checker
DefaultDirName={autopf}\TLS License Manager
DefaultGroupName=TLS License Manager
UninstallDisplayIcon={app}\LicenseManager.exe
Compression=lzma2/fast
SolidCompression=no
OutputDir=installer_output
OutputBaseFilename=TLS_License_Manager_v1.0.0_Setup
ArchitecturesInstallIn64BitMode=x64os
PrivilegesRequired=admin
SetupIconFile=Logos\icon_BLACK.ico

[Files]
Source: "dist\LicenseManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\TLS License Manager"; Filename: "{app}\LicenseManager.exe"
Name: "{group}\Uninstall TLS License Manager"; Filename: "{uninstallexe}"
Name: "{autodesktop}\TLS License Manager"; Filename: "{app}\LicenseManager.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\LicenseManager.exe"; Description: "Launch TLS License Manager"; Flags: nowait postinstall skipifsilent
