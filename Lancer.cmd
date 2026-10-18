@echo off
cd /d "%~dp0"
set "STORY_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%~dp0.venv\Scripts\python.exe" set "STORY_PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%STORY_PYTHON%" (
  "%STORY_PYTHON%" main_pc.py %*
) else (
  py -3 main_pc.py %*
)
if errorlevel 1 pause
