@echo off
chcp 65001 >nul
cd /d "C:\Users\李仁建\Desktop\AI生活随笔\2026.5.5\项目测试文件夹\electron-app"
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
echo 正在打包阅卷无忧...
echo 首次需要下载Electron(~80MB)，请耐心等待...
echo.
call npx.cmd electron-builder --win
echo.
echo ================================
echo 打包完成！查看 dist 目录
echo ================================
pause
