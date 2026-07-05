@echo off
set JAVA_HOME=D:\SpaceDev\softwareDev\SDKs\Java\jdk-17.0.2
set GRADLE_HOME=D:\SpaceDev\softwareDev\SDKs\gradle-8.8
set PATH=%JAVA_HOME%\bin;%GRADLE_HOME%\bin;%PATH%
set "WIXPATH=C:\Program Files (x86)\WiX Toolset v3.14\bin"
if exist "%WIXPATH%" set "PATH=%PATH%;%WIXPATH%"

set FX=C:\Users\25359\.gradle\caches\modules-2\files-2.1\org.openjfx
set FXV=17.0.2

set FX_BASE=%FX%\javafx-base\%FXV%\1bd6dc88b180a6239a5067320c2f0d7f3526e1d2\javafx-base-%FXV%-win.jar
set FX_CTRL=%FX%\javafx-controls\%FXV%\707f290bacde2738c0a7e1d0b4a8193002c29cf7\javafx-controls-%FXV%-win.jar
set FX_GFX=%FX%\javafx-graphics\%FXV%\6f95886c8fed3e1b21370a199c3937846ef6b3cc\javafx-graphics-%FXV%-win.jar
set FX_WEB=%FX%\javafx-web\%FXV%\9e60c27f0bdc39837bb128b223128fc385e443ee\javafx-web-%FXV%-win.jar
set FX_MEDIA=%FX%\javafx-media\%FXV%\5c6c84557bcd0016b5784d2b0cd8ae769e63d4ed\javafx-media-%FXV%-win.jar

set FX_PATH=%FX_BASE%;%FX_CTRL%;%FX_GFX%;%FX_WEB%;%FX_MEDIA%

echo === Build self-contained EXE ===

echo [0] Check deps report...
if not exist build\deps-jlink.txt (
    echo Run analyze.bat first to generate dependency report.
    pause & exit /b 1
)
set /p JLINKMODS=<build\deps-jlink.txt

echo [1/3] installDist...
call gradle installDist --no-daemon
if %ERRORLEVEL% neq 0 ( pause & exit /b 1 )

echo [2/3] jlink...
set RUNTIME=build\runtime
rmdir /s /q "%RUNTIME%" 2>nul

jlink --no-header-files --no-man-pages --strip-debug --compress 2 ^
    --module-path "%FX_PATH%" ^
    --add-modules %JLINKMODS% ^
    --output "%RUNTIME%"

if %ERRORLEVEL% neq 0 (
    echo jlink failed
    pause & exit /b 1
)

echo [3/3] jpackage...
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
    --dest build\portable

if %ERRORLEVEL% equ 0 (
    copy /y logo.ico build\portable\JhiFengMultiChat\JhiFengMultiChat.ico >nul
    echo Done: build\portable\JhiFengMultiChat\
) else (
    echo app-image failed
)
pause
