@echo off

:: 清空 dist 文件夹（如果存在）
if exist "dist" rmdir /S /Q "dist"

:: 使用 PyInstaller 创建多文件应用
pyinstaller --name="微信多开管理器" --windowed --icon=external_res\SunnyMultiWxMng.ico ^
--add-data="external_res;external_res" Main.py

:: 创建目标文件夹（如果不存在）
if not exist "dist\微信多开管理器" mkdir "dist\微信多开管理器"

:: 清理中间文件
rmdir /S /Q "build"
del /Q "微信多开管理器.spec"

echo 打包完成！
pause
