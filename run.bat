@echo off
set "JAVA_HOME=D:\SpaceDev\softwareDev\SDKs\Java\jdk-17.0.2"
set "PATH=D:\SpaceDev\softwareDev\SDKs\gradle-8.8\bin;%JAVA_HOME%\bin;%PATH%"
cd /d D:\SpaceDev\MyProj\JhiFengMultiChat
echo.
echo ========================================
echo           JhiFengMultiChat
echo ========================================
echo.
gradle run --no-daemon --args="--dev"
pause
