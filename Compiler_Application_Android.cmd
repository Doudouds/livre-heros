@echo off
setlocal
cd /d "%~dp0"
if exist "%ProgramFiles%\Android\Android Studio\jbr\bin\java.exe" set "JAVA_HOME=%ProgramFiles%\Android\Android Studio\jbr"
if not defined ANDROID_HOME set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
pushd "%~dp0android"
call gradlew.bat --no-daemon testDebugUnitTest lintDebug assembleDebug
set "STORY_BUILD_RESULT=%ERRORLEVEL%"
popd
if not "%STORY_BUILD_RESULT%"=="0" (
  echo La compilation Android a echoue.
  pause
  exit /b %STORY_BUILD_RESULT%
)
if not exist "%~dp0dist\android" mkdir "%~dp0dist\android"
copy /Y "%~dp0android\app\build\outputs\apk\debug\app-debug.apk" "%~dp0dist\android\LesPortesImaginaire.apk.partial"
if errorlevel 1 (
  pause
  exit /b 1
)
move /Y "%~dp0dist\android\LesPortesImaginaire.apk.partial" "%~dp0dist\android\LesPortesImaginaire.apk"
if errorlevel 1 (
  pause
  exit /b 1
)
echo APK prete : %~dp0dist\android\LesPortesImaginaire.apk
pause
