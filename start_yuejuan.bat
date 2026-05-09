@echo off
cd /d "%~dp0electron-app"
set PATH=C:\Program Files\nodejs;%PATH%
echo Checking Node...
node -e "console.log(' Node version: ' + process.version)"
echo.
echo Checking renderer files...
dir renderer\*.html renderer\*.js renderer\*.css 2>&1
echo.
echo Checking Electron install...
node -e "try{console.log(' Electron: ' + require('electron/package.json').version)}catch(e){console.log(' Electron not found: ' + e.message)}"
echo.
echo Starting YueJuanWuYou...
start "" /B cmd /c "cd /d %cd% && npm start"
pause
