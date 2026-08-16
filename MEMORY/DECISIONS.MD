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

## 账号列表来源 = 磁盘扫描（2026-07-31）
- **决定**: 平台页账号列表以 `SwInfoFuncCore.getSwAllAccountsExisted`（磁盘扫描：数据目录子目录 − 排除目录 + 共存 exe）为来源，SwAccData.json 仅作详情补充
- **原因**: 让磁盘真实存在的账号（新增目录/共存 exe）自动出现，移除已删除残留记录
- **实现**: `JsBridge.getSwExistedAccounts` → `SwConfigProvider.newAccessor()` + `SwInfoFuncCore` facade；main.js 按 ID 合并详情

## 头像接入 acccore/AvatarUtils 管道（2026-07-31）
- **决定**: 账号列表头像走 `AccInfoFuncCore.getAvatarFromCache` + `getAccAvatarFromFile`（→ `AvatarUtils.getAvatarDataUrl`），异步逐行更新
- **原因**: 之前直接渲染 avatar_url 不显示；需统一"本地文件 → URL 下载 → SVG 回退"且不阻塞 UI

## 日志目录固定根配置位置（2026-07-31）
- **决定**: 日志目录固定 `AppPaths.getLogsDir()`（`%APPDATA%\JhiFengMultiChat\{ver}\{Dev?}UserFiles\logs`），不跟随用户自定义数据目录
- **原因**: 根配置确定日志位置；与 logback 实际写入一致（Launcher 先用该路径设属性）

## legacy_python 保持忽略（2026-07-31 确认）
- **决定**: `legacy_python/` 继续在 .gitignore 忽略，不纳入版本管理
- **原因**: 仅供迁移参考，体积大且不支撑项目运行

## 后台会话关闭 worktree 隔离（2026-07-31）
- **决定**: `.claude/settings.json` 设 `"worktree": {"bgIsolation": "none"}`，后台会话可直接编辑主目录文件
- **原因**: 用户偏好直接改主目录文件，不接受强制 worktree；该文件被 gitignore，仅本地生效

## EventBus 事件机制（2026-08-01）
- **决定**: 自建轻量 EventBus（`core` 包，观察者模式）解耦「数据更新」与「UI 刷新」
- **原因**: 痛点——之前任何数据更新只能在每个更新方法里触发整表重渲染（`renderAccountTable`），刷新又带动头像重拉等系列加载；且 `getSwAccountsLoginStatus` 为 god-method（配置/pid/写库/状态计算耦合）。EventBus 使新增数据需求 = 新增订阅者，不改既有代码
- **流A 进入自动维护**: 进入平台页发布 `PlatformEnteredEvent` → 后台自动维护登录态数据（PID/共存/互斥体回写 SwAccData）
- **流B 定向刷新**: 账号数据写库后发布 `AccountDataChangedEvent` → 定向推送 JS 仅刷新受影响行/格（toggle-hidden 已迁移，删除/批量等后续增量迁移）
- **选型比较**: ① EventBus 订阅方零依赖、最解耦、可扩展（选定）；② JsBridge 多槽 Consumer 订阅方须持 JsBridge 引用；③ JavaFX Property 有 FX 线程约束（耗时维护须甩后台）。三者中 EventBus 最契合「appcore/acccore 解耦 JsBridge」的既有方向
- **关键文件**: `core/EventBus.java`、`core/event/*.java`、`PlatformEventBootstrap.java`、`AccInfoFuncCore` 拆分三步

## 账号列表列定制（2026-08-16）
- **决定**: 账号列表重构为 7 列（勾选框/头像/展示名/快捷键/ID/平台内ID/昵称），参考 Windows 资源管理器交互
- **状态/操作列移除**: 用户决策——不保留独立"状态"/"操作"列；操作改为展示名列右端悬浮小按钮（隐藏按钮选中态 = 已隐藏），行右键菜单提供隐藏/删除；禁用保留展示名旁小标签
- **列头右键菜单**: 勾选显示列，勾选框/头像/展示名/快捷键 4 列必选锁定；默认显示 + ID，alias/nickname 默认隐藏；"所有列自适应大小"/"该列自适应大小"
- **列宽拖拽**: `table-layout: fixed` + colgroup + `.col-resizer` 竖线，拖拽调宽，最后可见列不加竖线
- **快捷键列**: 点击激活输入框，keydown 捕获组合键，保存 SwAccData.hotkey（走 saveAccount → 流B 定向刷新）
- **排序**: 去掉 " ↕" 字符，保留点击排序，当前列用 `.sorted` 高亮（主题色+加粗）
- **持久化**: 列显示/宽度存 `LocalGlobalConfig.json.account_columns`（全局偏好，不随平台）
- **原因**: 数据字段（alias/nickname/hotkey）SwAccData 已具备、getSwDetailData 已全量返回，纯前端即可完成；交互贴近 Windows 资源管理器习惯
