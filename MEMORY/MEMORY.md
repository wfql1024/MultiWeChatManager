# MEMORY — 索引与摘要

> 最后更新: 2026-07-06

## 决策点
- [[决策点#page-main 复制迁移]] — 完整复制 DOM+JS，不动旧文件
- [[决策点#侧栏精简]] — 移除登录/管理，仅平台列表+统计+设置
- [[决策点#旧代码剥离]] — manage.js → .old/
- [[决策点#版本号管理]] — AppVersion.java 唯一来源
- [[决策点#打包方案]] — jlink + jpackage，便携版+安装版

## 待办
- [[待办#登录页面]]、[[待办#统计页面]] — 占位未实现
- [[待办#数据库层]]、[[待办#平台图标提取]]、[[待办#二进制补丁引擎]]
- [[待办#安装版图标]] — 需确认生效
- [[待办#SSL 握手]] — 打包版 handshake_failure

## 事实
- [[事实#当前阶段]]—Phase 1.10
- [[事实#打包路径]]—build/portable/, build/exe/
- [[事实#脚本位置]]—scripts/
- [[事实#版本号]]—4.0.0.7000 (AppVersion.java), 4.0.0 (Gradle/packaging)
- [[事实#JavaFX]]—Gradle cache, 17.0.2, 五个模块
- [[事实#WiX]]—C:\Program Files (x86)\WiX Toolset v3.14\bin
