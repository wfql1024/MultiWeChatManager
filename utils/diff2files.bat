@echo off
setlocal

REM 获取 bat 所在目录
set SCRIPT_DIR=%~dp0

REM 检查是否拖了两个文件
if "%~2"=="" (
    echo 请拖入两个文件
    pause
    exit /b 1
)

REM 调用同级的 diff2files.py
python "%SCRIPT_DIR%diff2files.py" "%~1" "%~2"

pause
