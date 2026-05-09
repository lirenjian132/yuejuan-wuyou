@echo off
cd /d "%~dp0..\electron-app"
echo Installing Electron dependencies...
echo This may take 2-5 minutes (downloading ~100MB)...
echo.

set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
set PATH=C:\Program Files\nodejs;%PATH%

call npm install

if %errorlevel% equ 0 (
    echo.
    echo ==========================================
    echo   INSTALL SUCCESS!
    echo   Starting YueJuanWuYou...
    echo ==========================================
    call npm start
) else (
    echo.
    echo INSTALL FAILED (error code: %errorlevel%)
    echo.
    echo Try running these commands manually:
    echo   cd electron-app
    echo   set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
    echo   npm install
)
pause
