@echo off

:: 使用 PyInstaller 创建多文件应用
pyinstaller -c --name="微信多开管理器" --windowed --icon=SunnyMultiWxMng.ico --add-data="SunnyMultiWxMng.ico;." --add-data="multiWeChat.exe;." Main.py

:: 创建目标文件夹（如果不存在）
if not exist "dist\微信多开管理器" mkdir "dist\微信多开管理器"

:: 移动生成的文件到新文件夹
xcopy /E /I /Y "dist\微信多开管理器" "dist\微信多开管理器"

:: 复制其他必要文件到新文件夹
copy "SunnyMultiWxMng.ico" "dist\微信多开管理器\"
copy "multiWeChat.exe" "dist\微信多开管理器\"
copy "path.ini" "dist\微信多开管理器\"
copy "点我创建快捷方式.bat" "dist\微信多开管理器\"

:: 清理中间文件
rmdir /S /Q "build"
del /Q "微信多开管理器.spec"

echo 打包完成！
pause