@echo off
setlocal

where adb >nul 2>nul
if errorlevel 1 (
    echo ERROR: adb was not found in PATH.
    exit /b 1
)

echo Waiting for device...
adb wait-for-device
if errorlevel 1 goto :failed

for /f %%i in ('adb shell "date +%%Y%%m%%d_%%H%%M%%S"') do set "TIMESTAMP=%%i"
if not defined TIMESTAMP (
    echo ERROR: Failed to generate timestamp.
    exit /b 1
)

set "FILE_NAME=output_%TIMESTAMP%.wav"
set "DEVICE_FILE=/tmp/%FILE_NAME%"
set "LOCAL_FILE=%~dp0%FILE_NAME%"

echo Recording 3 seconds to %DEVICE_FILE%...
adb shell "arecord -D default -f S16_LE -r 16000 -c 8 -d 10 %DEVICE_FILE%"
if errorlevel 1 goto :failed

echo Pulling recording to "%LOCAL_FILE%"...
adb pull "%DEVICE_FILE%" "%LOCAL_FILE%"
if errorlevel 1 goto :failed

echo Recording completed: "%LOCAL_FILE%"
exit /b 0

:failed
echo ERROR: Recording failed.
exit /b 1
