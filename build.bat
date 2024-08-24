@echo off

:: 清空 dist 文件夹（如果存在）
if exist "dist" rmdir /S /Q "dist"

:: 使用 PyInstaller 创建多文件应用
pyinstaller --name="微信多开管理器" --windowed --icon=external_res\SunnyMultiWxMng.ico ^
--add-data="external_res;external_res" --manifest=app.manifest --exclude-module=PyQt5 --exclude-module=numpy ^
--noconfirm Main.py

:: 检查 PyInstaller 是否成功
if exist "dist\微信多开管理器" (
    :: 清理中间文件
    rmdir /S /Q "build"
    del /Q "微信多开管理器.spec"

    echo 打包完成！
) else (
    echo "打包失败，请检查 pyinstaller 输出的日志。"
)

pause
