@echo off
:: 强制切换到脚本所在目录
cd /d "%~dp0"

:: 检查参数
if "%~1"=="" (
    echo 错误：必须指定版本参数（37或38）
    echo 用法：%~nx0 37|38
    exit /b 1
)

set VERSION=%~1
:: 设置变量简化路径
set PROJ_ROOT=..
set DIST_PATH=%PROJ_ROOT%\dist\JhiFengMultiChatBy%VERSION%
set EXTERNAL_RES=%PROJ_ROOT%\external_res
set META=%PROJ_ROOT%\.meta
set VENV=%PROJ_ROOT%\.venv%VERSION%

:: 在脚本开头检查主程序
if not exist "%PROJ_ROOT%\main.py" (
    echo 错误：找不到主程序源码
    goto end
)
if not exist "%PROJ_ROOT%\update_program.py" (
    echo 错误：找不到升级程序源码
    goto end
)

:: 清理 dist 文件夹及中间文件
if exist "%DIST_PATH%" rmdir /S /Q "%DIST_PATH%"
if exist "*.build" rmdir /S /Q "*.build"
if exist "*.dist" rmdir /S /Q "*.dist"
if exist "*.spec" del /Q "*.spec"

:: ===================== 升级程序打包 =====================
"%VENV%\Scripts\python.exe" -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-console-mode=disable ^
    --output-dir="%DIST_PATH%" ^
    --remove-output ^
    --file-version=3.9.9.3999 ^
    --product-version=3.9.9.3999 ^
    --company-name="极峰创科 JhiFeng Chan Tech Studio" ^
    --product-name="极峰多聊" ^
    --file-description="升级程序，用于极峰多聊自动更新" ^
    --copyright="吾峰起浪 © 版权所有" ^
    --trademark="MultiWeChatManager" ^
    --enable-plugin=tk-inter ^
    "%PROJ_ROOT%\update_program.py"

if exist "%DIST_PATH%\update_program.exe" (
    echo 升级程序打包成功
    if exist "%EXTERNAL_RES%\Updater.exe" del /Q "%EXTERNAL_RES%\Updater.exe"
    move /Y "%DIST_PATH%\update_program.exe" "%EXTERNAL_RES%\"
) else (
    echo 升级程序打包失败
    goto end
)

:: ===================== 主程序打包 =====================
"%VENV%\Scripts\python.exe" -m nuitka ^
    --standalone ^
    --windows-console-mode=disable ^
    --windows-uac-admin ^
    --windows-icon-from-ico="%EXTERNAL_RES%\JFMC.ico" ^
    --output-dir="%DIST_PATH%" ^
    --remove-output ^
    --file-version=3.9.9.3999 ^
    --product-version=3.9.9.3999 ^
    --company-name="极峰创科 JhiFeng Chan Tech Studio" ^
    --product-name="极峰多聊" ^
    --file-description="极峰多聊，旨在提升聊天平台多开使用体验。" ^
    --copyright="吾峰起浪 © 版权所有" ^
    --trademark="MultiWeChatManager" ^
    --include-module=comtypes.stream ^
    --include-data-dir="%EXTERNAL_RES%=external_res" ^
    --enable-plugin=tk-inter ^
    "%PROJ_ROOT%\main.py"

if exist "%DIST_PATH%\main.exe" (
    echo 主程序打包成功
) else (
    echo 主程序打包失败
    goto end
)

:: ===================== 复制快捷方式创建脚本 =====================
xcopy "click_me_to_create_lnk.bat" "%DIST_PATH%\管理员身份创建快捷方式.bat*" /Y

echo 打包完成！

:end
pause
