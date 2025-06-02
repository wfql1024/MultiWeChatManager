@echo off

:: 清空 dist 文件夹（如果存在）
if exist "dist\极峰多聊By38" rmdir /S /Q "dist\极峰多聊By38"
if exist "build" rmdir /S /Q "build"
if exist "*.spec" del /Q "*.spec"

:: 请先修改使用的虚拟环境，使用 PyInstaller 创建升级程序（无窗口）
.venv38\Scripts\pyinstaller --name="Updater" --windowed --onefile --version-file=.meta\version.txt --noconfirm ^
update_program.py

:: 检查打包是否成功
if exist "dist\Updater.exe" (
    echo 升级程序打包成功
) else (
    echo 升级程序打包失败
    goto end
)

:: 移动新生成的打包程序到external_res
if exist "external_res\Updater.exe" del /Q "external_res\Updater.exe"
move /Y "dist\Updater.exe" "external_res\"


:: 请先修改使用的虚拟环境，使用 PyInstaller 创建正常版本（无窗口）
.venv38\Scripts\pyinstaller --name="极峰多聊" --windowed --icon=external_res\SunnyMultiWxMng.ico ^
--add-data="external_res;external_res" --distpath="dist\极峰多聊By38" ^
--version-file=.meta\version.txt --noconfirm Main.py

:: 检查打包是否成功
if exist "dist\极峰多聊By38\极峰多聊\极峰多聊.exe" (
    echo 正式版打包成功
) else (
    echo 正式版打包失败
    goto end
)

:: 复制快捷方式创建脚本到打包文件夹
xcopy "click_me_to_create_lnk.bat" "dist\极峰多聊By38\极峰多聊\管理员身份创建快捷方式.bat*" /Y

echo 打包完成！

:end
:: 清理中间文件
if exist "build" rmdir /S /Q "build"
if exist "*.spec" del /Q "*.spec"
pause
