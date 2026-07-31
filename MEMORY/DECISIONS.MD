# 决策点

## page-main 复制迁移
- **决定**: 从 page-manage/manage.js 完整复制 DOM+JS 到 page-main/main.js，先不动旧代码
- **原因**: 用户发现逐段理解和改写容易出错，完整复制再逐步调试更可靠，且不会破坏已实现的页面
- **日期**: 2026-07-04

## 侧栏精简
- **决定**: 移除"登录"和"管理"按钮，仅保留平台列表 + 统计 + 设置
- **原因**: page-main 已成为默认主页，原导航按钮不再需要
- **日期**: 2026-07-05

## 旧代码剥离
- **决定**: manage.js → .old/，page-manage HTML 块从 index.html 删除
- **原因**: main.js + page-main 已完全替代原管理页功能
- **日期**: 2026-07-05

## 版本号管理
- **决定**: AppVersion.java (`4.0.0.7000`) 为版本号唯一来源，build.gradle.kts 和打包脚本从此读取
- **原因**: 用户要求"一个地方决定版本号"
- **日期**: 2026-07-05

## 打包方案
- **决定**: 使用 jlink (精简 JRE) + jpackage (生成 .exe)，提供安装版和便携版
- **原因**: 用户需要自包含 EXE，用户无需安装 Java
- **日期**: 2026-07-05
- **关键配置**: 
  - jlink: `--compress 2 --strip-debug --no-header-files --no-man-pages`
  - jpackage: `--type exe --win-dir-chooser` (安装版), `--type app-image` (便携版)
  - JavaFX jars 从 Gradle 缓存引用，运行时由 jlink 嵌入

## 头像重构（2026-07-30）
- **决定**: 新增 `AvatarUtils.java` 统一头像获取逻辑，整合本地文件读取、URL 下载和 SVG 文字回退
- **原因**: 账号列表头像不显示，需与旧版 Python 行为一致，同时支持用户自定义数据目录
- **日期**: 2026-07-30

## appcore/acccore 架构（2026-07-31）

**决策**: 将 legacy_python 的 func_core + functions 包迁移为 Java appcore/acccore 两个包，参考 swcore 架构模式。

**结构**:
- `appcore` — 对应 `app_func_core.py` + `app_func.py`（AppConfigAccessor + AppCore + AppCoreConstants）
- `acccore` — 对应 `acc_func_core.py` + `acc_func.py`（AccConfigAccessor + AccInfoFuncCore + AccOperatorCore + AccOpsProvider + AccCoreConstants）

**关键设计**:
- appcore/acccore 直接用 `ConfigManager.getInstance()` 读写，不依赖 JsBridge 的 private `BridgeConfigProvider`
- 新增公开的 `SwConfigProvider`（实现 `SwConfigAccessor.Provider`），供所有包通过 `SwConfigProvider.newAccessor()` 获取配置访问器
- `AccOpsProvider` 提供 `toSwProvider()` 转换为 swcore 的 `AccountOpsProvider`，避免循环依赖

**原因**: 减少对 JsBridge 私有类的耦合，让核心包可独立编译和测试。

**注意**: 编译时遇到 BridgeConfigProvider 私有访问问题，已通过 SwConfigProvider 解决。
