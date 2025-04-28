@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

:: 获取当前目录
set "currentDir=%~dp0"

:: 设置目标文件名
set "targetFile1=微信多开管理器.exe"

:: 检查目标文件是否存在
if not exist "%currentDir%%targetFile1%" (
    echo 错误：未找到目标文件 "%targetFile1%"
    goto :error
)

:: 获取桌面路径
for /f "tokens=2*" %%a in ('reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Desktop') do set "desktopPath=%%b"

if not defined desktopPath (
    echo 错误：无法获取桌面路径
    goto :error
)

:: 创建常规版快捷方式
powershell -ExecutionPolicy Bypass -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%desktopPath%\微信多开管理器.lnk'); $Shortcut.TargetPath = '%currentDir%%targetFile1%'; $Shortcut.WorkingDirectory = '%currentDir%'; $Shortcut.Save(); if ($?) { exit 0 } else { exit 1 }"

if %errorlevel% neq 0 (
    echo 创建常规版快捷方式失败
    goto :error
)

:: 创建调试版快捷方式，添加 --debug 参数
powershell -ExecutionPolicy Bypass -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%desktopPath%\微信多开管理器_调试版.lnk'); $Shortcut.TargetPath = '%currentDir%%targetFile1%'; $Shortcut.Arguments = '--debug'; $Shortcut.WorkingDirectory = '%currentDir%'; $Shortcut.Save(); if ($?) { exit 0 } else { exit 1 }"

if %errorlevel% neq 0 (
    echo 创建调试版快捷方式失败
    goto :error
)

:: 创建新版快捷方式，添加 --new 参数
powershell -ExecutionPolicy Bypass -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%desktopPath%\微信多开管理器_新版.lnk'); $Shortcut.TargetPath = '%currentDir%%targetFile1%'; $Shortcut.Arguments = '--new'; $Shortcut.WorkingDirectory = '%currentDir%'; $Shortcut.Save(); if ($?) { exit 0 } else { exit 1 }"

if %errorlevel% neq 0 (
    echo 创建新版快捷方式失败
    goto :error
)

:: 如果成功，直接退出
exit

:error
:: 在错误情况下显示窗口并等待用户输入
echo.
echo 创建快捷方式过程中遇到错误。
echo 请将以上错误信息截图或复制给开发者。
echo.
echo 按任意键退出...
pause > nul
