@echo off
setlocal EnableDelayedExpansion
set JAVA_HOME=D:\SpaceDev\Env\Infrastructure\runtime\Java\jdk-17.0.2
set GRADLE_HOME=D:\SpaceDev\Env\Infrastructure\runtime\gradle-9.8.0
set PATH=%JAVA_HOME%\bin;%GRADLE_HOME%\bin;%PATH%
set "WIXPATH=C:\Program Files (x86)\WiX Toolset v3.14\bin"
if exist "%WIXPATH%" set "PATH=%PATH%;%WIXPATH%"


echo === Build self-contained EXE ===

echo [1/4] installDist...
call gradle installDist --no-daemon
if %ERRORLEVEL% neq 0 ( pause & exit /b 1 )

set LIB=build\install\JhiFengMultiChat\lib

echo [2/4] jlink inputs (JavaFX jars come from installDist, no Gradle cache paths)...
if not exist build\jlink-inputs mkdir build\jlink-inputs
set FX_PATH=
for %%f in ("%LIB%\javafx-*-win.jar") do set "FX_PATH=!FX_PATH!;%%~ff"
if "!FX_PATH!"=="" (
    echo JavaFX platform jars missing in %LIB% ^(installDist should produce javafx-*-win.jar^)
    pause & exit /b 1
)
set "FX_PATH=!FX_PATH:~1!"
set JDEPOUT=build\jlink-inputs\modules.txt
"%JAVA_HOME%\bin\jdeps" --multi-release 17 --print-module-deps --ignore-missing-deps %LIB%\*.jar > "%JDEPOUT%" 2>nul
if %ERRORLEVEL% neq 0 (
    echo jdeps failed
    pause & exit /b 1
)
set /p DEPS=<"%JDEPOUT%"
set JLINKMODS=%DEPS%,javafx.base,javafx.controls,javafx.graphics,javafx.web,javafx.media,jdk.crypto.ec
echo jdeps modules: %DEPS%
echo jlink roots : %JLINKMODS%

echo [3/4] jlink...
set RUNTIME=build\runtime
rmdir /s /q "%RUNTIME%" 2>nul
jlink --no-header-files --no-man-pages --strip-debug --compress 2 ^
    --module-path "!FX_PATH!" ^
    --add-modules %JLINKMODS% ^
    --output "%RUNTIME%"
if %ERRORLEVEL% neq 0 (
    echo jlink failed
    pause & exit /b 1
)

echo [4/4] jpackage...
set INPUT=build\install\JhiFengMultiChat\lib
set APPDIR=build\app-input
rmdir /s /q "%APPDIR%" 2>nul
mkdir "%APPDIR%"
for %%f in ("%INPUT%\*.jar") do (
    echo %%~nxf | findstr /b "javafx-" >nul
    if errorlevel 1 copy "%%f" "%APPDIR%\" >nul
)
for %%f in ("%APPDIR%\JhiFengMultiChat-*.jar") do set JAR=%%~nxf
set INPUT=%APPDIR%
for /f tokens^=2^ delims^=^" %%v in ('findstr /c:"String VERSION" src\main\java\com\jfmultichat\config\AppVersion.java') do set APPVER=%%v
for /f "tokens=1-3 delims=." %%a in ("%APPVER%") do set APPV3=%%a.%%b.%%c
echo App version: %APPVER% (packaging as %APPV3%)

jpackage --name JhiFengMultiChat --app-version %APPV3% ^
    --input "%INPUT%" --main-jar "%JAR%" --main-class com.jfmultichat.Launcher ^
    --runtime-image "%RUNTIME%" --type exe ^
    --java-options "--add-exports javafx.web/com.sun.javafx.webkit=ALL-UNNAMED" ^
--java-options "--add-exports java.desktop/sun.awt.shell=ALL-UNNAMED" ^
    --icon logo.ico --win-dir-chooser --dest build\exe

if %ERRORLEVEL% equ 0 (
    echo Done: build\exe\JhiFengMultiChat-%APPV3%.exe
) else (
    echo jpackage installer failed
)

echo.
echo [bonus] Portable...
rmdir /s /q build\portable 2>nul
jpackage --name JhiFengMultiChat --app-version %APPVER% ^
    --input "%INPUT%" --main-jar "%JAR%" --main-class com.jfmultichat.Launcher ^
    --runtime-image "%RUNTIME%" --type app-image ^
    --icon logo.ico ^
    --java-options "--add-exports javafx.web/com.sun.javafx.webkit=ALL-UNNAMED" ^
--java-options "--add-exports java.desktop/sun.awt.shell=ALL-UNNAMED" ^
    --dest build\portable

if %ERRORLEVEL% equ 0 (
    copy /y logo.ico build\portable\JhiFengMultiChat\JhiFengMultiChat.ico >nul
    echo Done: build\portable\JhiFengMultiChat\
) else (
    echo app-image failed
)
pause
