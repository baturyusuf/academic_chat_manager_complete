#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
[Setup]
AppId={{3B20E33B-496C-4C95-9A38-BAA3E39C6AB1}
AppName=Akademik Sohbet Yöneticisi
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\AcademicChatManager
DefaultGroupName=Akademik Sohbet Yöneticisi
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=AcademicChatManager-Setup
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\AkademikSohbetYoneticisi.exe
Compression=lzma2
SolidCompression=yes
CloseApplications=no
RestartApplications=no
AppMutex=Local\AcademicChatManagerRunning
[Files]
Source: "..\dist\AkademikSohbetYoneticisi\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\installer-helper\Updater.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{autoprograms}\Akademik Sohbet Yöneticisi"; Filename: "{app}\AkademikSohbetYoneticisi.exe"
[Run]
Filename: "{app}\AkademikSohbetYoneticisi.exe"; Description: "Akademik Sohbet Yöneticisi'ni başlat"; Flags: nowait postinstall skipifsilent
