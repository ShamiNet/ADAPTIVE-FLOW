@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0
"%~dp0.venv\Scripts\python.exe" -m adaptive_flow.gui
if errorlevel 1 pause