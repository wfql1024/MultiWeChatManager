# 事实

## 当前阶段
- Phase 1.10 — page-main 替代 page-manage，旧代码剥离至 .old/，侧栏精简
- Phase 1.11 — AvatarUtils 重构账号头像逻辑（2026-07-30）
- Phase 1.12 — 账号列表来源磁盘扫描 + 头像显示接入 + 日志修复与设置页"日志"子项（2026-07-31）
- Phase 1.13 — 展示名显示 + SwAccData 自动填充 + EventBus 事件机制（2026-08-01）
- Phase 1.14 — 账号列表列定制：7 列结构 + 列头右键菜单 + 列宽拖拽 + 快捷键编辑 + 悬浮交互（2026-08-16）
- Phase 1.15 — 四表架构：可复用 AccountTable 组件 + 原生程序/原生账号/共存账号/无效账号 + 快捷键 Scene 级捕获（2026-08-16 第二轮）
- Phase 1.16 — 账号列表交互打磨：自定义滚动条体系 + 高度链锁定 + 整行高亮 + 列宽规则定稿 + 分割线（2026-08-16 晚间）

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

## 包结构

- `acccore` — 账号信息核心（AccConfigAccessor/AccInfoFuncCore/AccOperatorCore/AccOpsProvider/AccCoreConstants）
- `appcore` — 应用信息核心（AppConfigAccessor/AppCore/AppCoreConstants）
- `bridge` — JS↔Java 桥接（JsBridge，含 EventBus 触发/推送）
- `config` — 配置管理（ConfigManager/JsonConfigStore/AppPaths/AppEnv/SwConfigProvider 等）
- `core` — 跨切面基础设施（EventBus + event/ 平台进入与账号数据变更事件）
- `model` — 数据模型（About/Reference/Sponsor）
- `setting` — 设置项抽象（AbsSetting/RemoteGlobalSetting）
- `swcore` — Windows 探测与补丁引擎核心
- `ui` — UI 窗口管理（MainWindow/FloatingSidebar/SampleWindow）
- `utils` — 工具类（AvatarUtils 等）

## swcore 包关键细节
### SwConfigAccessor.Provider 模式：通过 Provider 注入，BridgeConfigProvider 适配 ConfigManager
### 六级路径探测：内存映射正则 > 注册表 > 猜测 > 进程 > 其他SW > DLL遍历

### 运行命令速查
- 开发运行: gradle run --no-daemon --args="--dev"
- 仅编译: gradle compileJava --no-daemon

## 页面迁移
- **page-main**: 主内容区，基于 manage.js 完整复制后修正作用域隔离逻辑
- **main.js**: `getEl(id)` 使用 `querySelector('#page-main #' + id) || document.getElementById(id)` 进行作用域隔离
- **管理页已废弃**: `#page-manage` HTML 区块已删除，`manage.js` 移至 `.old/`

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
- **提交**: `e7e348c` 已入库（日志修复 + 设置页"日志"子项 + 文档，6 文件）
- **后台会话隔离**: `.claude/settings.json` 设 `"worktree": {"bgIsolation": "none"}`（本地、gitignored），后台会话可直接编辑主目录文件

## 新增模块（2026-08-01）
- **core 包** (`src/main/java/com/jfmultichat/core/`) — 跨切面基础设施
  - `EventBus.java` — 轻量事件总线单例（subscribe/publish 线程安全，单订阅者异常不拖垮其它）
  - `event/PlatformEnteredEvent.java` — 平台进入事件（流A 触发自动维护）
  - `event/AccountDataChangedEvent.java` — 账号数据变更事件（流B 触发定向 UI 刷新）
- **PlatformEventBootstrap** (`src/main/java/com/jfmultichat/PlatformEventBootstrap.java`) — 事件装配点，`install(bridge)` 注册订阅者，MainApp.start 调用

## 新增模块（2026-08-16 第二轮）
- **AccountTable 组件** (`src/main/resources/web/js/components/account-table.js`) — 可复用列表组件：列定义驱动（任意列组合/固定列/必选锁定）、标题行（标题 + 已选计数 + 批量按钮）、列头右键菜单、列宽拖拽/自适应、行右键菜单、快捷键列编辑、EventBus 流B 定向刷新；四个表实例共用
- **快捷键 Scene 级捕获** — `JsBridge.notifyHotkeyCapture(active)`（Scene KeyEvent EventFilter，capture 阶段）→ 组合键推送 `JFC.bridge._onHotkeyCapture` → JS 更新输入框；`MainWindow` 创建 Scene 后 `bridge.setScene(scene)`
- **getSwExistedAccounts only 参数** — `JsBridge.getSwExistedAccounts(swId, only)`："origin"=原生/"coexist"=共存/空=全部（对应 SwAccountOps only 过滤）
- **NPE 修复** — `AccInfoFuncCore.getSwAllAccountsExisted` 传 `new AccOpsProvider().toSwProvider()`（原 null 导致共存分支 NPE）

## 新增功能（2026-08-01 会话）
- **账号展示名**: "昵称"列头置空；`getSwDetailData` 注入 `display_name`（`getAccOriginDisplayName`: remark→nickname→alias→ID）；前端展示名/头像首字符/排序用之
- **SwAccData 自动填充**: `syncSwAccAccounts` 在 `getSwExistedAccounts` 取得磁盘扫描列表后补缺失账号节点
- **EventBus 事件机制**: 流A 进入平台页自动后台维护登录态数据（`resolvePidAccountMap`→`associateCoexistAccounts`→`updateAccLoginData`）；流B `saveAccount` 发布事件 → 定向推送 JS 只刷对应行/格
- **NPE 修复**: `Map.of(PID, pid)` 因 pid null 抛 NPE → HashMap；relay 读回判空
- **提交**: `c2561a4` 已入库（展示名 + 自动填充，4 文件）
- **提交**: 本次提交（EventBus 机制全套 + NPE 修复 + 文档），已通过进入平台页与隐藏切换实测、维护日志无报错

## 新增功能（2026-08-16 会话）
- **账号列表 7 列结构**: 勾选框（行悬浮才显示）/头像/展示名（右端悬浮操作按钮：隐藏选中态+删除）/快捷键（点击编辑，存 `hotkey`）/ID/平台内ID（`alias`）/昵称（`nickname`）；移除原"状态"/"操作"两列
- **列头右键菜单**: 勾选显示列（勾选框/头像/展示名/快捷键 4 列必选锁定；ID 默认显示；alias/nickname 默认隐藏）+ "所有列自适应大小"/"该列自适应大小"（临时 span 测量）
- **列间竖线拖拽调列宽**: `table-layout: fixed` + colgroup，`.col-resizer` 拖拽（最小 30px），最后可见列不加竖线
- **行右键菜单**: 隐藏/显示、删除（与悬浮按钮同走 `handleAccountAction`）
- **排序标识**: 去掉 " ↕" 字符，当前排序列 th 加 `.sorted` 高亮（主题色+加粗）
- **配置持久化**: `LocalGlobalConfig.json.account_columns = {visible, width}`（`getGlobalConfig`/`saveGlobalConfig`）
- **onAccountChanged 扩展**: 处理 `hotkey`/`alias`/`nickname` 字段定向更新；状态变化走 `updateRowQuickActions`（原 stateBadgeHtml 删除）
- **提交**: 625e33d（列定制）/ 9549c6c + 4059ccb（四表架构与文档）

## 新增功能（2026-08-16 晚间会话）
- **自定义 overlay 滚动条体系**（核心）: JavaFX WebView 原生滚动条不可靠（overlay/需触发/带箭头/不随主题）→ DOM 自定义滚动条 `attachCustomScrollbar`：不占位不撑高、5px 胶囊、无箭头、深浅色适配；显示条件 = 内容溢出 + 鼠标在内容区/滚动条上；挂在滚动容器父级（不随内容滚动）；rAF 驱动（JavaFX scroll 事件不可靠）；三处统一（表内横向/账号区域纵向/设置区域纵向）
- **高度链锁定**: `#page-main .manage-layout` flex column + `.manage-detail-area` `flex:1; min-height:0; min-width:0; overflow:hidden` + 表容器链 `min-width:0`——解决内容撑宽/撑高导致的无滚动条、列宽联动、设置区域被拉宽
- **设置区域滚动条根因**: `animatePanelHeight` 动画后未恢复 `content.maxHeight`（动画期间设 'none'）→ 修复为动画后恢复 `targetHeight`
- **列宽规则定稿**: 表格宽度恒 = 可见列宽总和（px，不填充容器）；固定列绝对固定（不读持久化）；自适应下限 = 列名宽+余量（展示名列 = 4字符+按钮占位），无上限
- **整行悬浮高亮**: JS 高亮层 `.acc-row-highlight`（mousemove 委托匹配任意 tr）；移除 `tr:hover` 避免叠加颜色不一致
- **分割线**: `--divider-solid`（背景+半透明混合的不透明等效色，深 `#2c2c2c`/浅 `#d4d4d4`）用于双区分界 + 窗帘把手
- **细节**: 空表行高 ≤ 数据行、"暂无数据"居左；头像列不显示列名、展示名列改"名称"；右键菜单覆盖空白区域
- **NPE 修复**: `AccOpsProvider.toSwProvider().updateSwAccData` 取 key（原取 value 写错账号）；`SwAccountOps` 的 `Map.of(..., null)` → HashMap
- **提交**: 4132a54 / 086197d / d4c7e1a / 37fdcf3 / 5aec864 / b32a3a6 / e4c82bd + 本次提交（晚间全部）

## 规则文件（2026-08-16）
- **项目级**: `AGENTS.md`（由 `CLAUDE.md` git mv 重命名；DSH 与 Claude Code 通用约定，DSH 默认候选 `["AGENTS.md","CLAUDE.md"]`）
- **全局级**: `~/.dsh/AGENTS.md`（DSH 全局仅认 AGENTS.md，不读 `~/.claude/CLAUDE.md`；已从全局 CLAUDE.md 拷贝）
- DSH 规则文件机制: 项目级候选 `AGENTS.md`/`CLAUDE.md`、本地级 `AGENTS.local.md`/`CLAUDE.local.md`、全局 `$DSH_HOME/AGENTS.md`；由 `dsh-agent-instructions` 插件实时 watch 注入（改文件即时生效）

## 远程配置发布工具（2026-10-04）

- **新增源集 `src/tools/java`**（`com.jfmultichat.tools.EncryptRemoteConfigs`）— 发布辅助工具，复用 `config.CryptoUtils`，**不进入应用产物**（`gradle jar` 无 `com/jfmultichat/tools` 条目）
- **Gradle 任务**: `gradle encryptRemoteConfigs`（`scripts\encrypt-configs.bat` 为包装）；输入 `scripts/original_remote_<global|sw>_<vN>.json` → 输出 `remote_configs/remote_<global|sw>_<vN>`
- **加密单一实现**: `CryptoUtils` 新增 `encryptAndAppendKey`（与 `decryptResponse` 同源，key 规则 `ljust(16)[:16]` 共用 `normalizeKey`）
- **内置 URL 版本常量**: `RemoteConfigFetcher.BUILTIN_REMOTE_SW_VERSION = "v10"` / `BUILTIN_REMOTE_GLOBAL_VERSION = "v2"`（4 条 URL 由常量拼接；设置页默认 URL 列表来自同一 getter，前端无硬编码 URL）
- **测试 `CryptoUtilsTest`**（6 例全绿）: 往返、已知向量（格式冻结）、key 补齐/截断、**历史 Python 产物兼容**、**当前发布产物自校验**
- **兼容性实测**: Java 解密直接读出 Python 产出的 `remote_global_v1` / `remote_sw_v9`，LF 归一化后逐字符一致；Java 加密产物字节数与 Python 版相同（48,657 / 170,429）
- **内容现状**: `original_remote_global_v2.json` ≡ `legacy_python/.../original_remote_global_v1.json` ≡ `resources/data/remote_global_v1.json`（MD5 `0902DC1C…`）；`original_remote_sw_v10.json` ≡ 旧 `original_remote_sw_v9.json`（MD5 `102713C0…`）——v2/v10 为纯版本号提升
- **换行处理**: 加密前按通用换行读取（CRLF → LF），与历史 Python 版一致；发布产物解密后与源 JSON 是「LF 归一化后相等」

## 代理设置（2026-10-04）

- **设计原则**: 代理**只由界面"使用代理"复选框控制**（用户要求：不要默认开、不要自动探测）；未勾选一律直连
- **`AppCore.applyProxySetting()`** → 返回 `ProxyState(applied, host, port, message)`；设置/清除 `http(s).proxyHost/Port` 与 `http.nonProxyHosts`；**运行期修改立即生效**（HttpClient 默认 ProxySelector 每次请求读取系统属性）
- **地址归一化** `AppCore.splitHostPort()` / `isValidPort()` — 兼容 `http://127.0.0.1:7890`、`127.0.0.1:7890`、`127.0.0.1`+端口分开填、`[::1]:7890`；端口非法则按直连并提示
- **立即生效链路**: `settings.js` 勾选/change → `JFC.bridge.applyProxyConfig` → `JsBridge.applyProxyConfig`（只持久化代理 3 字段 + 应用 + 回传归一化结果回填）；`saveConfigData()` 保存时、`Launcher` 启动时各调用一次
- **修复的报错**: `URISyntaxException: Expected closing bracket for IPv6 address ... proxy.https://[http://127.0.0.1]:7890/`（用户把 `http://127.0.0.1` 填进地址框；界面 placeholder 已改为 `127.0.0.1`）
- **测试**: `AppCoreProxyTest`（3 例：协议/端口拆分、IPv6、端口校验）
- **备注**: 曾短暂实现"未勾选时跟随系统代理"（`config/SystemProxy`），按用户要求已移除
- **远程配置候选 URL 兜底**: `JsBridge.mergeUrls()`（用户 URL 优先 + 内置追加 + 去重）—— 修复「用户清空远程配置源后候选 0 个、远程配置永远下载失败」；测试 `JsBridgeUrlTest`（4 例）
- **代理地址归一化**: `AppCore.splitHostPort()` 剥协议前缀/拆端口（用户填 `http://127.0.0.1` + 端口 `7890` 曾导致 `URISyntaxException: ... proxy.https://[http://127.0.0.1]:7890/`）；界面 placeholder 已改为 `127.0.0.1`；勾选/修改后立即生效
