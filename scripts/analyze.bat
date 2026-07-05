@echo off
set JAVA_HOME=D:\SpaceDev\softwareDev\SDKs\Java\jdk-17.0.2
set GRADLE_HOME=D:\SpaceDev\softwareDev\SDKs\gradle-8.8
set PATH=%JAVA_HOME%\bin;%GRADLE_HOME%\bin;%PATH%

echo === Dependency Analysis ===

echo [1/2] installDist...
call gradle installDist --no-daemon
if %ERRORLEVEL% neq 0 ( pause & exit /b 1 )

echo [2/2] jdeps...
set JDEPOUT=build\deps-modules.txt
"%JAVA_HOME%\bin\jdeps" --multi-release 17 --print-module-deps --ignore-missing-deps build\install\JhiFengMultiChat\lib\*.jar > "%JDEPOUT%" 2>nul

if %ERRORLEVEL% neq 0 (
    echo jdeps failed
    pause & exit /b 1
)

set /p DEPS=<"%JDEPOUT%"
set FULLDEPS=%DEPS%,javafx.base,javafx.controls,javafx.graphics,javafx.web,javafx.media,jdk.crypto.ec
echo %FULLDEPS% > build\deps-jlink.txt

echo === Report ===
echo JDK modules   : %DEPS%
echo Full jlink    : %FULLDEPS%
echo Report saved  : build\deps-jlink.txt
pause
