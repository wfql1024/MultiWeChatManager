@echo off
rem 远程配置一键发布：
rem   1) 加密本工程 v2/v10 -> remote_configs\
rem   2) 版本适配同步 v2->v1、v10->v9 -> Python 工程 scripts\
rem   3) 加密 Python 工程 v1/v9 -> Python 工程 remote_configs\
rem Python 工程默认取同级 ..\MultiWeChatManager，可用 gradle -PpythonRepo=... 覆盖
set "JAVA_HOME=D:\SpaceDev\Env\Infrastructure\runtime\Java\jdk-17.0.2"
set "GRADLE_HOME=D:\SpaceDev\Env\Infrastructure\runtime\gradle-9.8.0"
set "PATH=%JAVA_HOME%\bin;%GRADLE_HOME%\bin;%PATH%"
cd /d "%~dp0.."
echo ========================================
echo     远程配置一键发布 (main + python)
echo ========================================
echo.
call gradle publishRemoteConfigs --no-daemon
pause
