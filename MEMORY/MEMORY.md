# MEMORY — 索引与摘要

> 最后更新: 2026-07-31

## 决策点
- [[DECISIONS.MD#page-main 复制迁移]] — 完整复制 DOM+JS，不动旧文件
- [[DECISIONS.MD#侧栏精简]] — 移除登录/管理，仅平台列表 + 统计 + 设置
- [[DECISIONS.MD#旧代码剥离]] — manage.js → .old/
- [[DECISIONS.MD#版本号管理]] — AppVersion.java 唯一来源
- [[DECISIONS.MD#打包方案]] — jlink + jpackage，便携版 + 安装版
- [[DECISIONS.MD#常量按包分离]] — config 包用 AppCoreConstants，swcore 包用 SwCoreConstants
- [[DECISIONS.MD#头像重构]] — AvatarUtils 统一头像获取逻辑（2026-07-30）
- [[DECISIONS.MD#账号列表来源 = 磁盘扫描]] — getSwExistedAccounts 接入磁盘扫描来源（2026-07-31）
- [[DECISIONS.MD#头像接入 acccore/AvatarUtils 管道]] — 异步逐行更新头像（2026-07-31）
- [[DECISIONS.MD#日志目录固定根配置位置]] — AppPaths.getLogsDir() 不随用户配置（2026-07-31）
- [[DECISIONS.MD#legacy_python 保持忽略]] — 不入版本管理（2026-07-31 确认）
- [[DECISIONS.MD#后台会话关闭 worktree 隔离]] — bgIsolation none（2026-07-31）

## 待办
- [[TODOS.MD#登录页面]]、[[TODOS.MD#统计页面]] — 占位未实现
- [[TODOS.MD#数据库层]]、[[TODOS.MD#平台图标提取]]、[[TODOS.MD#二进制补丁引擎]]
- [[TODOS.MD#安装版图标]] — 需确认生效
- [[TODOS.MD#SSL 握手]] — 打包版 handshake_failure
- [[TODOS.MD#utils 包]] — LoggerUtils/decrypt/image_utils/file_utils/Handle 操作待移植
- [[TODOS.MD#Handle 操作]] — 需 JNA 重写 NtQuerySystemInformation 系列
- [[TODOS.MD#上传日志功能]] — 设置页"日志"子项已预留按钮，需服务器后实现

## 事实
- [[FACTS.MD#当前阶段]]—Phase 1.12
- [[FACTS.MD#打包路径]]—build/portable/, build/exe/
- [[FACTS.MD#脚本位置]]—scripts/
- [[FACTS.MD#版本号]]—4.0.0.7000 (AppVersion.java), 4.0.0 (Gradle/packaging)
- [[FACTS.MD#JavaFX]]—Gradle cache, 17.0.2, 五个模块
- [[FACTS.MD#WiX]]—C:\Program Files (x86)\WiX Toolset v3.14\bin
- [[FACTS.MD#包结构]]—config/bridge/acccore/swcore/utils/setting/model/ui/docs
- [[FACTS.MD#远程配置]]—RemoteConfigFetcher 默认 URL + AES-CBC 加密格式
- [[FACTS.MD#物理地图]]—docs/physical_map.md 完整文件树
- [[FACTS.MD#Handle 操作]]—Java 无原生 Handle 操作，需 JNA 仿照 pywinhandle.py
- [[FACTS.MD#解密实现]]—decrypt/ 包（DecryptInterface, WeChatDecrypt, WeixinDecrypt）
- [[FACTS.MD#Handle 操作]]—SwNativeOps.NtDllExt 已扩展 4 个 NT API 声明
- [[FACTS.MD#全局 CLAUDE.md]]—SDK 路径/打包流程/项目文档架构/时间标注规则已归档
- [[FACTS.MD#settings.json]]—showMessageTimestamps=true, claude-time 插件安装失败（hooks 冲突）
- [[FACTS.MD#AvatarUtils]]—头像获取工具类，本地/URL/SVG 三路回退（2026-07-30）
- [[FACTS.MD#page-main]]—主页面从 page-manage 复制迁移，作用域隔离修复
- [[FACTS.MD#新增功能（2026-07-31 会话）]]—账号列表来源/头像显示/日志修复与设置项/提交 5216773/未提交 6 文件

## 开发日志
- [[DEV_LOGS.MD#page-main 复制迁移（2026-07-04~05）]] — 完整复制 DOM+JS，侧栏精简，旧代码剥离
- [[DEV_LOGS.MD#头像显示功能重构（2026-07-30）]] — AvatarUtils 引入、用户目录适配、SVG 文字回退样式
- [[DEV_LOGS.MD#账号列表来源 + 头像显示 + 日志设置页（2026-07-31）]] — 磁盘扫描来源/头像异步接入/日志修复/_handleAsync 双编码坑

## 迁移工程（2026-07-31）
- [[FACTS.MD#新增模块（2026-07-31）]] — appcore/acccore 包 + SwConfigProvider
- [[DECISIONS.MD#appcore/acccore 架构]] — Python func_core 迁移为 Java 包
