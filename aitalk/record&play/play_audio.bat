@echo off
setlocal

if "%~1"=="" (
    set "LOCAL_FILE=%~dp0output.wav"
) else (
    set "LOCAL_FILE=%~f1"
)
set "DEVICE_DIR=/mnt/UDISK"
set "DEVICE_FILE=%DEVICE_DIR%/output.wav"

where adb >nul 2>nul
if errorlevel 1 (
    echo ERROR: adb was not found in PATH.
    exit /b 1
)

if not exist "%LOCAL_FILE%" (
    echo ERROR: Audio file not found: "%LOCAL_FILE%"
    exit /b 1
)

echo Waiting for device...
adb wait-for-device
if errorlevel 1 goto :failed

echo Pushing "%LOCAL_FILE%" to %DEVICE_FILE%...
adb push "%LOCAL_FILE%" "%DEVICE_FILE%"
if errorlevel 1 goto :failed

echo Playing %DEVICE_FILE%...
adb shell "cd %DEVICE_DIR% && aplay -D default output.wav"
if errorlevel 1 goto :failed

echo Playback completed.
exit /b 0

:failed
echo ERROR: Playback failed.
exit /b 1
