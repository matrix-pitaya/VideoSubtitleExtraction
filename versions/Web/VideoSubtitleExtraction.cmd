@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0VideoSubtitleExtraction.Launch.ps1"
if errorlevel 1 pause
