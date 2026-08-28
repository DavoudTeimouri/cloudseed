@echo off
REM CloudSeed Sysprep: generalize VM -> new SID on next boot.
set "UNATTEND=%~dp0sysprep-unattend.xml"
if not exist "%UNATTEND%" (
  echo ERROR: sysprep-unattend.xml not found next to this script.
  exit /b 1
)
echo Running Sysprep (generalize + oobe, shutdown)...
C:\Windows\System32\sysprep\sysprep.exe /generalize /oobe /shutdown /unattend:"%UNATTEND%"
