@echo off
chcp 65001 >nul

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
set APP_NAME=JhiFengMultiChat
:: 设置变量简化路径
:: 项目根目录
set PROJ_ROOT=..
:: 打包路径
set DIST_PATH=%PROJ_ROOT%\dist\%APP_NAME%By%VERSION%
:: 额外资源路径
set EXTERNAL_RES=%PROJ_ROOT%\external_res
:: 元数据路径
set META=%PROJ_ROOT%\.meta
:: 虚拟环境路径
set VENV=%PROJ_ROOT%\.venv%VERSION%

:: 设置7z路径, 按需修改
set SEVEN_ZIP="D:\software\Tools\7-Zip\7z.exe"
:: 是否在打包成功后生成压缩包
:: 1 = 生成压缩包
:: 0 = 不生成
set ENABLE_PACKAGE_ARCHIVE=1

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
--distpath="%DIST_PATH%" --exclude-module numpy "%PROJ_ROOT%\update_program.py"

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
  --name="%APP_NAME%" ^
  --windowed ^
  --icon="%EXTERNAL_RES%\JFMC.ico" ^
  --add-data="%EXTERNAL_RES%;external_res" ^
  --distpath="%DIST_PATH%" ^
  --uac-admin ^
  --clean ^
  --version-file="%META%\version.txt" ^
  --noconfirm ^
  --hidden-import=comtypes.stream ^
  --hidden-import=curl_cffi ^
  --collect-all curl_cffi ^
  --exclude-module numpy ^
  "%PROJ_ROOT%\main.py"



:: 检查打包是否成功
if exist "%DIST_PATH%\%APP_NAME%\%APP_NAME%.exe" (
    echo 正式版打包成功
) else (
    echo 正式版打包失败
    goto end
)

:: 复制快捷方式创建脚本到打包文件夹
xcopy "click_me_to_create_lnk.bat" "%DIST_PATH%\%APP_NAME%\管理员身份创建快捷方式.bat*" /Y

echo 打包完成！

:: 生成时间戳
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format ""yyyy-MM-dd HHmmss"""') do set BUILD_TIME=%%i
echo BUILD_TIME=%BUILD_TIME%

if "%ENABLE_PACKAGE_ARCHIVE%"=="1" (
    :: zip 压缩（压整个 APP_NAME 文件夹）
    powershell -NoProfile -Command "Compress-Archive -Path '%DIST_PATH%\%APP_NAME%' -DestinationPath '%DIST_PATH%\%APP_NAME% %BUILD_TIME%.zip' -Force"


    :: 7z 压缩
    if exist %SEVEN_ZIP% (
        %SEVEN_ZIP% a -t7z "%DIST_PATH%\%APP_NAME% %BUILD_TIME%.7z" "%DIST_PATH%\%APP_NAME%" -mx=9
    ) else (
        echo 未找到 7z.exe，跳过 7z 压缩
    )
) else (
    echo 已关闭压缩包生成，跳过 zip / 7z
)

:end
:: 清理中间文件
if exist "build" rmdir /S /Q "build"
if exist "*.spec" del /Q "*.spec"
pause