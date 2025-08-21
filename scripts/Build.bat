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
:: 项目根目录
set PROJ_ROOT=..
:: 打包路径
set DIST_PATH=%PROJ_ROOT%\dist\极峰多聊By%VERSION%
:: 额外资源路径
set EXTERNAL_RES=%PROJ_ROOT%\external_res
:: 元数据路径
set META=%PROJ_ROOT%\.meta
:: 虚拟环境路径
set VENV=%PROJ_ROOT%\.venv%VERSION%

:: 在脚本开头添加当前目录检查
if not exist "%PROJ_ROOT%\main.py" (
    echo 错误：找不到主程序源码
    goto end
)
if not exist "%PROJ_ROOT%\update_program.py" (
    echo 错误：找不到升级程序源码
    goto end
)

:: 清空 dist 文件夹及产生的文件
if exist "%DIST_PATH%" rmdir /S /Q "%DIST_PATH%"
if exist "build" rmdir /S /Q "build"
if exist "*.spec" del /Q "*.spec"

:: 使用 PyInstaller 创建升级程序（无窗口）
"%VENV%\Scripts\pyinstaller" --name="Updater" --windowed --onefile --version-file="%META%\version.txt" --noconfirm ^
--distpath="%DIST_PATH%" "%PROJ_ROOT%\update_program.py"

:: 检查打包是否成功
if exist "%DIST_PATH%\Updater.exe" (
    echo 升级程序打包成功
) else (
    echo 升级程序打包失败
    goto end
)

:: 移动新生成的打包程序到external_res
if exist "%EXTERNAL_RES%\Updater.exe" del /Q "%EXTERNAL_RES%\Updater.exe"
move /Y "%DIST_PATH%\Updater.exe" "%EXTERNAL_RES%\"

:: 使用 PyInstaller 创建正常版本（无窗口）
"%VENV%\Scripts\pyinstaller" ^
  --name="极峰多聊" ^
  --windowed ^
  --icon="%EXTERNAL_RES%\JFMC.ico" ^
  --add-data="%EXTERNAL_RES%;external_res" ^
  --distpath="%DIST_PATH%" ^
  --uac-admin ^
  --clean ^
  --version-file="%META%\version.txt" ^
  --noconfirm ^
  --hidden-import=comtypes.stream ^
  "%PROJ_ROOT%\main.py"



:: 检查打包是否成功
if exist "%DIST_PATH%\极峰多聊\极峰多聊.exe" (
    echo 正式版打包成功
) else (
    echo 正式版打包失败
    goto end
)

:: 复制快捷方式创建脚本到打包文件夹
xcopy "click_me_to_create_lnk.bat" "%DIST_PATH%\极峰多聊\管理员身份创建快捷方式.bat*" /Y

echo 打包完成！

:end
:: 清理中间文件
if exist "build" rmdir /S /Q "build"
if exist "*.spec" del /Q "*.spec"
pause