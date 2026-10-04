@echo off
set "JAVA_HOME=D:\SpaceDev\Env\Infrastructure\runtime\Java\jdk-17.0.2"
set "PATH=D:\SpaceDev\Env\Infrastructure\runtime\gradle-9.8.0\bin;%JAVA_HOME%\bin;%PATH%"
cd /d E:\SpaceDev\Projects\Mine\JhiFengMultiChat
echo.
echo ========================================
echo           JhiFengMultiChat
echo ========================================
echo.
gradle run --no-daemon
pause
