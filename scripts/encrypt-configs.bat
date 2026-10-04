@echo off
rem 加密远程配置：scripts\original_remote_<global|sw>_<vN>.json  ->  remote_configs\
rem 工具链路径见全局 ~/.dsh/AGENTS.md；实际加密由 Gradle 任务复用 CryptoUtils 完成
set "JAVA_HOME=D:\SpaceDev\Env\Infrastructure\runtime\Java\jdk-17.0.2"
set "GRADLE_HOME=D:\SpaceDev\Env\Infrastructure\runtime\gradle-9.8.0"
set "PATH=%JAVA_HOME%\bin;%GRADLE_HOME%\bin;%PATH%"
cd /d "%~dp0.."
echo ========================================
echo     加密远程配置 -^> remote_configs\
echo ========================================
echo.
call gradle encryptRemoteConfigs --no-daemon
pause
