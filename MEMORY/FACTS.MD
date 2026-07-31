# 事实

## 当前阶段
- Phase 1.10 — page-main 替代 page-manage，旧代码剥离至 .old/，侧栏精简
- Phase 1.11 — AvatarUtils 重构账号头像逻辑（2026-07-30）
- Phase 1.12 — 账号列表来源磁盘扫描 + 头像显示接入 + 日志修复与设置页"日志"子项（2026-07-31）

## 打包路径
- 免安装版: `build/portable/JhiFengMultiChat/JhiFengMultiChat.exe`
- 安装版: `build/exe/JhiFengMultiChat-{version}.exe`
- 总大小: ~154MB（含 JRE + JavaFX WebView）

## 脚本位置
- `scripts/run.bat` — 开发运行
- `scripts/analyze.bat` — 依赖分析
- `scripts/package.bat` — 基础打包 (distZip)
- `scripts/package-exe.bat` — EXE 打包 (jlink + jpackage)

## 旧代码位置
- `.old/manage.js` — 原管理页 JS
- `src/main/resources/web/js/manage.js` — 已移除（页面删除）
- HTML 中 `#page-manage` 区块已删除

## 版本号
- `AppVersion.java`: `"4.0.0.7000"` — 唯一来源
- `build.gradle.kts`: `"4.0.0"` — 同步
- 打包安装版用 `4.0.0`（WiX 限制 3 段），便携版用 `4.0.0.7000`

## JavaFX 依赖路径
- Gradle 缓存: `C:\Users\25359\.gradle\caches\modules-2\files-2.1\org.openjfx\`
- 版本: 17.0.2
- 模块: base, controls, graphics, web, media

## WiX Toolset
- 路径: `C:\Program Files (x86)\WiX Toolset v3.14\bin`
- 版本: 3.14.1.8722

## 新增模块（2026-07-30）
- **AvatarUtils** (`src/main/java/com/jfmultichat/utils/AvatarUtils.java`) — 头像获取工具类，支持本地文件读取、URL下载、SVG文字回退三路逻辑；异步下载支持 `downloadAvatarAsync()`


## Python旧版参考（迁移工程资料）
- **认知审计报告** (`legacy_python/docs/cognitive_audit_report.md`) — 旧版Python代码架构文档，当前Java迁移工程的重要参考资料




## 数据存储规范（骨架事实）

### 用户数据目录格式
%APPDATA%/JhiFengMultiChat/{version}/
├── RootConfig.json               # 锚点文件，永不移动
├── UserFiles/
│   ├── LocalGlobalConfig.json    # 软件偏好
│   ├── LocalSwConfig.json        # 各平台设置
│   ├── SwAccData.json            # 账号数据
│   ├── SwCache.json              # 适配缓存
│   ├── RemoteGlobalConfig.json   # 远程全局配置缓存
│   └── RemoteSwConfig.json       # 远程平台配置缓存
└── DevUserFiles/                 # 开发版（--dev）

### RootConfig.json 字段示例
{ "user_data_path": "...", ... }

## 配置层架构

接口层次：IConfigStore → JsonConfigStore → ConfigManager

未来扩展：如需更换存储格式，只需实现新的 `IConfigStore`

## swcore 包关键细节
### SwConfigAccessor.Provider 模式：通过 Provider 注入，BridgeConfigProvider 适配 ConfigManager
### 六级路径探测：内存映射正则 > 注册表 > 猜测 > 进程 > 其他SW > DLL遍历

### 运行命令速查
- 开发运行: gradle run --no-daemon --args="--dev"
- 仅编译: gradle compileJava --no-daemon

## 页面迁移
- **page-main**: 主内容区，基于 manage.js 完整复制后修正作用域隔离逻辑
- **main.js**: `getEl(id)` 使用 `querySelector('#page-main #' + id) || document.getElementById(id)` 进行作用域隔离
- **管理页已废弃**: `#page-manage` HTML 区块已删除，`manage.js` 移至 `.old/`test

## 新增模块（2026-07-31）
- **appcore 包** (`src/main/java/com/jfmultichat/appcore/`) — 对应 Python `func_core/app_func_core.py` + `functions/app_func.py`
  - `AppCoreConstants.java` — 常量定义（RootConfig/GlobalSetting/RemoteGlobal/RemoteSw/AccKey 键名）
  - `AppConfigAccessor.java` — 配置访问器，直接读写 ConfigManager
  - `AppCore.java` — 远程配置获取、版本检查、平台列表、数据迁移、代理设置
- **acccore 包** (`src/main/java/com/jfmultichat/acccore/`) — 对应 Python `func_core/acc_func_core.py` + `functions/acc_func.py`
  - `AccCoreConstants.java` — 账号数据键 + 状态枚举
  - `AccConfigAccessor.java` — 账号数据访问器（读写 SwAccData.json）
  - `AccInfoFuncCore.java` — 头像/展示名/登录状态/共存判断/窗口绑定
  - `AccOperatorCore.java` — 登录配置读写/进程管理/互斥体查杀
  - `AccOpsProvider.java` — 账号操作提供器（转 swcore 接口）
- **SwConfigProvider** (`src/main/java/com/jfmultichat/config/SwConfigProvider.java`) — 公开的 `SwConfigAccessor.Provider` 实现，独立于 JsBridge 的 private BridgeConfigProvider

### 设计决策
- appcore/acccore 直接用 `ConfigManager.getInstance()` 读写，不依赖 JsBridge 的 private `BridgeConfigProvider`
- 新增 `SwConfigProvider.newAccessor()` 便捷方法返回 `SwConfigAccessor`

## 新增功能（2026-07-31 会话）
- **账号列表来源**: `JsBridge.getSwExistedAccounts` → `SwInfoFuncCore.getSwAllAccountsExisted`（磁盘扫描）；main.js `loadAccountData` 以磁盘结果为来源，与 `getSwDetailData` 详情按 ID 合并
- **头像显示**: `JsBridge.getAccAvatarAsync` → `AccInfoFuncCore.getAvatarFromCache` + `getAccAvatarFromFile`（AvatarUtils 三路）；前端 `requestAccountAvatar`/`updateAccountAvatarCell` 逐行异步更新
- **日志修复**: logback.xml `${jfmultichat.logdir:-logs}` 默认回退；`Launcher.main` 首行设属性；不再产生 `jfmultichat.logdir_IS_UNDEFINED/`
- **设置页"日志"子项**: 打开日志目录 + 预留"上传日志"按钮；日志目录固定 `AppPaths.getLogsDir()` = `%APPDATA%\JhiFengMultiChat\{ver}\{Dev?}UserFiles\logs`（`AppEnv.isDev()` 决定 DevUserFiles/UserFiles，不随用户配置）
- **提交**: `5216773` 已入库（acccore/appcore/SwConfigProvider + docs/project_structure.md + 账号列表/头像两功能）
- **未提交（6 文件）**: logback.xml, Launcher.java, JsBridge.java, bridge.js, index.html, settings.js
- **后台会话隔离**: `.claude/settings.json` 设 `"worktree": {"bgIsolation": "none"}`（本地、gitignored），后台会话可直接编辑主目录文件
