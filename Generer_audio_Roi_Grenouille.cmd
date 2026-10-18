@echo off
cd /d "%~dp0"
"%~dp0.venv-tts\Scripts\python.exe" -u "%~dp0generer_audio_conte.py" %*
echo.
pause
