@echo off

:: 清空 dist 文件夹（如果存在）
if exist "dist" rmdir /S /Q "dist"

:: 使用 PyInstaller 创建正常版本（无窗口）
pyinstaller --name="微信多开管理器" --windowed --icon=external_res\SunnyMultiWxMng.ico ^
--add-data="external_res;external_res" --manifest=app.manifest --exclude-module=PyQt5 --exclude-module=numpy ^
--noconfirm Main.py

:: 重命名生成的 EXE 文件
ren "dist\微信多开管理器\微信多开管理器.exe" "微信多开管理器_正式版.exe"

:: 使用 PyInstaller 创建调试版本（有窗口）
pyinstaller --name="微信多开管理器_调试版" --icon=external_res\SunnyMultiWxMng.ico ^
--add-data="external_res;external_res" --manifest=app.manifest --exclude-module=PyQt5 --exclude-module=numpy ^
--distpath="dist\微信多开管理器" --workpath="build\调试版" ^
--noconfirm Main.py

:: 检查 PyInstaller 是否成功
if exist "dist\微信多开管理器\微信多开管理器_正式版.exe" (
    if exist "dist\微信多开管理器\微信多开管理器_调试版.exe" (
        :: 清理中间文件
        rmdir /S /Q "build"
        del /Q "微信多开管理器.spec"
        del /Q "微信多开管理器_调试版.spec"

        echo 打包完成！正式版和调试版都已生成，共用同一个 _internal 文件夹。
    ) else (
        echo 调试版打包失败，请检查 pyinstaller 输出的日志。
    )
) else (
    echo 正式版打包失败，请检查 pyinstaller 输出的日志。
)

pause