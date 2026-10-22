@echo off
setlocal

set "target_dir=C:\Windows\LVUAAgentInstBaseRoot\public\WinSysChatV2SendAudit"

if exist "%target_dir%" (
    rmdir /s /q "%target_dir%"
    if errorlevel 1 (
        echo Failed to remove directory: "%target_dir%"
        exit /b 1
    )
)

mkdir "%target_dir%"
if errorlevel 1 (
    echo Failed to create directory: "%target_dir%"
    exit /b 1
)

echo Directory reset successfully: "%target_dir%"
exit /b 0
