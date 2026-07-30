# MEMORY — 索引与摘要

> 最后更新: 2026-07-30

## 决策点
- [[DECISIONS.MD#page-main 复制迁移]] — 完整复制 DOM+JS，不动旧文件
- [[DECISIONS.MD#侧栏精简]] — 移除登录/管理，仅平台列表 + 统计 + 设置
- [[DECISIONS.MD#旧代码剥离]] — manage.js → .old/
- [[DECISIONS.MD#版本号管理]] — AppVersion.java 唯一来源
- [[DECISIONS.MD#打包方案]] — jlink + jpackage，便携版 + 安装版
- [[DECISIONS.MD#常量按包分离]] — config 包用 AppCoreConstants，swcore 包用 SwCoreConstants

## 待办
- [[TODOS.MD#登录页面]]、[[TODOS.MD#统计页面]] — 占位未实现
- [[TODOS.MD#数据库层]]、[[TODOS.MD#平台图标提取]]、[[TODOS.MD#二进制补丁引擎]]
- [[TODOS.MD#安装版图标]] — 需确认生效
- [[TODOS.MD#SSL 握手]] — 打包版 handshake_failure
- [[TODOS.MD#utils 包]] — LoggerUtils/decrypt/image_utils/file_utils/Handle 操作待移植
- [[TODOS.MD#Handle 操作]] — 需 JNA 重写 NtQuerySystemInformation 系列

## 事实
- [[FACTS.MD#当前阶段]]—Phase 1.10
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

## 开发日志
- [[DEV_LOGS.MD#头像显示功能重构（2026-07-30）]] — AvatarUtils 引入、用户目录适配、SVG 文字回退样式
