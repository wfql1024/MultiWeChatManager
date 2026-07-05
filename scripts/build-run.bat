@echo off
set "JAVA_HOME=D:\SpaceDev\softwareDev\SDKs\Java\jdk-17.0.2"
set "PATH=D:\SpaceDev\softwareDev\SDKs\gradle-8.8\bin;%JAVA_HOME%\bin;%PATH%"
cd /d D:\SpaceDev\MyProj\JhiFengMultiChat
echo.
echo ========================================
echo   JhiFengMultiChat Build + Run
echo ========================================
echo.
gradle compileJava compileTestJava --no-daemon
if %errorlevel% neq 0 (
    echo.
    echo BUILD FAILED, aborting run.
    pause
    exit /b %errorlevel%
)
gradle run --no-daemon
pause
