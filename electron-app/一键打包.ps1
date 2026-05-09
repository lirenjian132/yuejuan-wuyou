cd "C:\Users\李仁建\Desktop\AI生活随笔\2026.5.5\项目测试文件夹\electron-app"
$env:ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
$env:CSC_IDENTITY_AUTO_DISCOVERY="false"
Write-Host "正在打包安装版..."
npx electron-builder --win
Write-Host "完成！查看 dist 目录"
Read-Host "按 Enter 关闭"
