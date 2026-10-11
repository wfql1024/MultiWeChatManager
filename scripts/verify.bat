@echo off
REM ============================================================================
REM  verify.bat — 一键验证：编译 + 单元测试 + 前端 JS 语法检查
REM
REM  用法:
REM    scripts\verify.bat            全部（编译 + 测试 + JS 检查）
REM    scripts\verify.bat --quick    只编译
REM
REM  注意: 按项目约定，**简单改动不需要跑这个** —— 列清单给用户亲验即可；
REM        只有用户明确要求"循环修改+验证"时才用。
REM ============================================================================
setlocal
set "ROOT=%~dp0.."
set "JAVA_HOME=D:\SpaceDev\Env\Infrastructure\runtime\Java\jdk-17.0.2"
set "GRADLE=D:\SpaceDev\Env\Infrastructure\runtime\gradle-9.8.0\bin\gradle.bat"
set "NODE=D:\SpaceDev\Env\Infrastructure\runtime\nodejs\node.exe"
set "WEBDIR=%ROOT%\src\main\resources\web\js"

echo === 1/3 编译 ===
call "%GRADLE%" -p "%ROOT%" --no-daemon --console=plain compileJava || goto :fail
if /I "%~1"=="--quick" goto :ok

echo.
echo === 2/3 单元测试 ===
call "%GRADLE%" -p "%ROOT%" --no-daemon --console=plain test || goto :fail

echo.
echo === 3/3 前端 JS 语法检查 ===
for %%F in ("%WEBDIR%\*.js" "%WEBDIR%\pages\*.js" "%WEBDIR%\components\*.js") do (
    "%NODE%" --check "%%~fF" || goto :fail
)

:ok
echo.
echo === 全部通过 ===
exit /b 0

:fail
echo.
echo === 失败（见上方输出）===
exit /b 1
