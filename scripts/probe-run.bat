@echo off
REM ============================================================================
REM  probe-run.bat — 编译并运行离线探针：tmp\probe\<类名>.java
REM
REM  用法:
REM    scripts\probe-run.bat AllWndProbe
REM    scripts\probe-run.bat UiaProbe 12345        (类名之后的参数原样传给探针)
REM
REM  说明: classpath 自动从 Gradle 缓存里找 JNA / SLF4J，不用手拼路径。
REM        探针源码放 tmp/probe/（tmp 已 gitignore，且不在 build/ —— gradle clean 不会清掉）。
REM ============================================================================
setlocal enabledelayedexpansion
if "%~1"=="" (
    echo 用法: scripts\probe-run.bat ^<探针类名^> [参数...]
    exit /b 1
)
set "ROOT=%~dp0.."
set "NAME=%~1"
set "ARGS="
for /f "tokens=1,* delims= " %%A in ("%*") do set "ARGS=%%B"

set "JAVA_HOME=D:\SpaceDev\Env\Infrastructure\runtime\Java\jdk-17.0.2"
set "CACHE=%USERPROFILE%\.gradle\caches\modules-2\files-2.1"
set "OUT=%ROOT%\tmp\probe\out"
set "CP=%ROOT%\build\classes\java\main;%OUT%"

for %%J in (jna-5.14.0.jar jna-platform-5.14.0.jar slf4j-api-2.0.9.jar) do (
    for /f "delims=" %%P in ('dir /s /b "%CACHE%\%%J" 2^>nul') do set "CP=!CP!;%%P"
)

if not exist "%OUT%" mkdir "%OUT%"
if not exist "%ROOT%\tmp\probe\%NAME%.java" (
    echo 找不到探针源码: %ROOT%\tmp\probe\%NAME%.java
    exit /b 1
)

echo === 编译 %NAME%.java ===
"%JAVA_HOME%\bin\javac.exe" -encoding UTF-8 -cp "%CP%" -d "%OUT%" "%ROOT%\tmp\probe\%NAME%.java" || exit /b 1

echo === 运行 %NAME% ===
"%JAVA_HOME%\bin\java.exe" -Dfile.encoding=UTF-8 -cp "%CP%" %NAME% %ARGS%
exit /b %ERRORLEVEL%
