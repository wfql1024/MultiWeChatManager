@echo off

:: 清空 dist 文件夹（如果存在）
if exist "dist" rmdir /S /Q "dist"
if exist "build" rmdir /S /Q "build"
if exist "*.spec" del /Q "*.spec"

:: 使用 PyInstaller 创建正常版本（无窗口）
pyinstaller --name="微信多开管理器" --windowed --icon=external_res\SunnyMultiWxMng.ico ^
--add-data="external_res;external_res" --manifest=app.manifest --exclude-module=PyQt5 ^
--exclude-module=numpy --exclude-module=future --noconfirm Main.py

:: 检查打包是否成功
if exist "dist\微信多开管理器\微信多开管理器.exe" (
    echo 正式版打包成功
) else (
    echo 正式版打包失败，请检查 build_log_正式版.txt
    goto end
)

:: 清理中间文件
if exist "build" rmdir /S /Q "build"
if exist "*.spec" del /Q "*.spec"

:: 复制快捷方式创建脚本到打包文件夹
copy "点我创建快捷方式.bat" "dist\微信多开管理器\"

echo 打包完成！正式版和调试版都已生成，共用同一个 _internal 文件夹。

:end
pause
