@echo off
setlocal enabledelayedexpansion

:: 获取当前目录
set "currentDir=%~dp0"

:: 设置目标文件名
set "targetFile=微信多开管理器.exe"

:: 检查目标文件是否存在
if not exist "%currentDir%%targetFile%" (
    exit /b
)

:: 获取桌面路径
for /f "tokens=2*" %%a in ('reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Desktop') do set "desktopPath=%%b"

:: 创建快捷方式
powershell -WindowStyle Hidden -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%desktopPath%\微信多开管理器.lnk'); $Shortcut.TargetPath = '%currentDir%%targetFile%'; $Shortcut.WorkingDirectory = '%currentDir%'; $Shortcut.Save()"