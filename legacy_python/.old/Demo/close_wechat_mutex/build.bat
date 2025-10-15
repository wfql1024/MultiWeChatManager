@echo off

:: 清空 dist 文件夹（如果存在）
if exist "dist" rmdir /S /Q "dist"
if exist "build" rmdir /S /Q "build"
if exist "*.spec" del /Q "*.spec"

:: 使用 PyInstaller 创建正常版本（无窗口）
pyinstaller --name="WeChatMultiple_wfql" --windowed --icon=double_sun.ico ^
 --noconfirm --onefile close_wechat_mutex.py

:: 检查打包是否成功
if exist "dist\WeChatMultiple_wfql.exe" (
    echo 正式版打包成功
) else (
    echo 正式版打包失败
    goto end
)

:: 清理中间文件
if exist "build" rmdir /S /Q "build"
if exist "*.spec" del /Q "*.spec"

echo 打包完成！

:end
pause
