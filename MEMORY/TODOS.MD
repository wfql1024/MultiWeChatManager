# 待办

## 登录页面
- 占位状态，未实现

## 统计页面
- 占位状态，未实现

## 数据库层
- SQLite + DAO，未开始

## 平台图标提取
- ExtractIconExW 完善

## 二进制补丁引擎
- 从 Python 迁移，待评估合法性

## 安装版图标
- logo.ico 已生成，需确认 jpackage --icon 生效

## SSL 握手
- [x] 2026-10-04 定位并修复开发版根因：**Java 默认不使用 Windows 系统代理**，直连 GitHub raw 被 RST（`SSLHandshakeException: Remote host terminated the handshake`）→ 界面勾选"使用代理"即可（勾选/修改立即生效，见 AGENTS.md 十二）
- [ ] 待验证：打包版（jlink 精简运行时）是否同样只需勾选代理；若仍失败再检查 jlink 模块是否含 `java.net.http` / `jdk.crypto.ec`
