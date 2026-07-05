@echo off
set JAVA_HOME=D:\SpaceDev\softwareDev\SDKs\Java\jdk-17.0.2
set GRADLE_HOME=D:\SpaceDev\softwareDev\SDKs\gradle-8.8
set PATH=%JAVA_HOME%\bin;%GRADLE_HOME%\bin;%PATH%

echo === JhiFengMultiChat Build ===

echo [1/2] Compile + Test...
call gradle build --no-daemon
if %ERRORLEVEL% neq 0 (
    echo BUILD FAILED
    pause
    exit /b 1
)

echo.
echo [2/2] Package...
call gradle distZip --no-daemon
echo Done: build\distributions\

echo.
echo === BUILD SUCCESS ===
echo Run: unzip build\distributions\JhiFengMultiChat-*.zip
echo Then: bin\JhiFengMultiChat.bat
pause
