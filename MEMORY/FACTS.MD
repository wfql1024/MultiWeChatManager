# 事实

## 当前阶段
- Phase 1.10 — page-main 替代 page-manage，旧代码剥离至 .old/，侧栏精简
- Phase 1.11 — AvatarUtils 重构账号头像逻辑（2026-07-30）
- Phase 1.12 — 账号列表来源磁盘扫描 + 头像显示接入 + 日志修复与设置页"日志"子项（2026-07-31）
- Phase 1.13 — 展示名显示 + SwAccData 自动填充 + EventBus 事件机制（2026-08-01）
- Phase 1.14 — 账号列表列定制：7 列结构 + 列头右键菜单 + 列宽拖拽 + 快捷键编辑 + 悬浮交互（2026-08-16）
- Phase 1.15 — 四表架构：可复用 AccountTable 组件 + 原生程序/原生账号/共存账号/无效账号 + 快捷键 Scene 级捕获（2026-08-16 第二轮）
- Phase 1.16 — 账号列表交互打磨：自定义滚动条体系 + 高度链锁定 + 整行高亮 + 列宽规则定稿 + 分割线（2026-08-16 晚间）
- Phase 1.17 — 刷新入口与进度条 + 账号管理功能（就地编辑/批量操作/重置删除）+ 程序表快捷键与头像弹窗 + 版本号自动获取
  + 账号头像文字兜底 + 中文字体与三级色体系 + 三表名称列统一 + 原生程序名称链（`origin_exe`）+ 删除/重置清头像文件（2026-10-05 晚 ~ 10-06）
  → 细节见下文各专题小节与 [`DECISIONS.MD`](DECISIONS.MD) D-10~D-28、[`DEV_LOGS.MD`](DEV_LOGS.MD) 三十~三十七

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

## 共存账号数据接入（2026-10-04）

- **表数据**: `coexist_acc` 接 `getSwExistedAccounts(swId,'coexist')`；与原生账号共用 `buildAccountRows()` 合并 SwAccData 详情，头像按表路由更新
- **Java 修复（3 处）**: ①`SwInfoFuncCore` 读错键 `exe_wcs`（应为 `executable_wildcards`）→ 共存扫描恒 0；②`JsBridge.getSwExistedAccounts` 的 `SwInfoFuncCore` 第 4 参 accountOps 传 null → 共存分支 NPE；③`SwAccountOps` 一律取 `inst_path` 父目录，而 WeChat/DouYinIM 存的是目录 → 新增 `resolveInstDir()`
- **本机实测**: WeChat 2（WeCha1/WeCha2）、WXWork 1（WXWor1），其余平台目录内无匹配 exe
- **待用户修正**: TIM 的 `inst_path` 当前指向 QQNT（数据问题）
- **测试**: `SwAccountOpsTest`(3)

## 共存账号列 + 列配置持久化 + 侧栏展开（2026-10-04）

- **新增列**: 共存账号表增加「最后登录账号」= `linked_acc`（非必选、默认显示，`TABLE_COLUMNS.coexist`）
- **列显隐/列宽不持久化（bug 修复）**: `_saveColumnPrefs` 写扁平键 `account_columns.<表id>`，读取端用嵌套 `account_columns[表id]` → 勾选丢失；改为嵌套写 + 先读后合并（saveGlobalConfig 是顶层浅合并）+ 读取端兼容历史扁平键
- **最左栏展开**: `nav-sidebar.js` 改为「鼠标在区域内静止 2 秒」才展开（`EXPAND_DELAY=2000`，`MOVE_THRESHOLD=6px` 微动不重新计时），移出即收起

## 设置页配置三块独立保存（2026-10-04）

- **结构**: 代理 / 本地目录 / 远程配置源 三块 + 两个分割线，各块右下角独立"保存"；后端 `saveConfigData` 逐字段合并，天然支持部分提交（不再一处失败全盘阻塞）
- **代理**: 明细常驻显示；保存后能立即应用→"保存成功"，`requiresRestart=true`（运行期应用异常）→弹窗提示重启，地址非法（勾选但 applied=false）→红字并按直连
- **本地目录**: 保存按钮默认禁用，绿框（input-ok）才启用
- **远程配置源**: 测试全部/添加 移到列表标题右侧；保存按钮需 sw/global 至少一个地址本次会话测试通过；不再预置绿框
- **风格统一**: `.config-desc` 统一板块介绍；`.config-label`→font-h3；输入框 padding/字号/圆角/字体统一；次级按钮统一 6px 12px/--font-sm；提示统一 --font-xs；`.config-form .settings-section` margin 交给 `.config-divider`
- **清理**: 移除 `#cfg-btn-save`/`#cfg-save-msg`/`updateSaveButton`；`showMsg(id,msg,isErr)`

## 账号列表细节打磨 + 共存账号属性来源（2026-10-04）

- **共存账号**: 名称/昵称/平台内ID/头像一律取 `linked_acc` 指向的账号（自身只认 remark）；名称链 remark > 链接nickname > 链接alias > 链接id > 自身id；头像链 自身本地 > 链接本地 > 链接头像地址 > 默认（`AvatarUtils.getCoexistAvatarDataUrl`，`getAccAvatarAsync` 自动识别 linked_acc）
- **整行背景层**: 悬浮/选中色统一用 `z-index:-1` 的绝对定位层（容器 `z-index:0`+`isolation:isolate`），宽度 = max(表格宽, 容器可视宽)，不透明色 `--bg-row-hover`/`--bg-row-selected`；选中行不显示悬浮色；移除 `tr.selected` 背景
- **列宽热区**: `.col-resizer` 从 `right:-3px`（被 th overflow 裁剪）改为 `right:0; width:7px`，最右列也能拖
- **表头行**: `.acc-table-titlebar` `min-height:38px`，批量按钮出现不再撑高
- **最左栏**: 静止悬停 2s → 1s
- **远程配置源**: 保存条件改为 sw 与 global 都有绿框（AND）

## 账号表末尾占位列（2026-10-04）

- 表格末尾内部列 `_filler`（不在 columns，无 data-col，不参与排序/显隐/列菜单）；宽度 = 容器可视宽 - 可见列宽总和（>=0）
- 作用：所有真实列右侧都有邻居（拖拽热区不再压在表格边界）；占位单元格属于该行 → 行悬浮/选中感应覆盖整行
- 菜单文案：所有列/该列"调至合适宽度"；占位列不提供"该列"项
- 表头行 `.acc-table-titlebar` min-height 38px → 46px

## 列宽不生效根因：隐藏列 col 宽度（2026-10-04）

- 现象：隐藏部分列后最右可见列拖不动、自适应也无效；所有列都显示时正常
- 根因：table-layout:fixed 列宽取自 <col>，隐藏列时只给 th/td 加 display:none，<col> 宽度仍是原值 → 声明列宽总和 > 表格宽度 → 浏览器重新分配列宽，声明值被吃掉
- 修复：`_applyColumnLayout` 中隐藏列的 <col> 同时归零+隐藏（`hidden-col` + `width:0`，真实宽度留在 colWidth）；拖拽/总宽取整避免 1px 溢出
- 占位列宽度 = 容器 clientWidth - 可见列宽总和（≥0），右端恰在列表区域右边缘

## 名称列宽度 + 悬浮按钮占位 + 等宽字体（2026-10-04）

- 名称列"调至合适宽度" = 名称宽 + 悬浮按钮预留宽(QUICK_ACTIONS_WIDTH=96)；量取时只取 .dn-text/.manage-disabled-tag，排除按钮文字
- 悬浮按钮改 visibility 常驻占位（原 display 切换会在悬浮瞬间挤压 .dn-text → 文字截断/位移）
- 列表内容（td）统一等宽字体 var(--font-family-mono)，表头仍用界面字体

## 无效账号并入 + 原生程序表 + 名称清洗（2026-10-04）

- 名称列下划线 = 账号 ID 里的 `_`（无 remark/nickname/alias 时名称回退成 ID），非 CSS；新增 cleanDisplayName：名称等于 ID 时去下划线（仅显示层，ID 列不变）
- 无效账号 = SwAccData − 原生 − 共存，按类型并入两表：invalid=true → 灰字 + "失效"标签 + 永远置底；删除无效账号表/容器/列定义（四表→三表）
- 置底分组：_sortAccounts 稳定排序按 rank（invalid 2 / hidden 1 / 其他 0）分组
- 原生程序表：数据源 = inst_path 的 exe；列 名称(必选)/版本(必选)/路径(默认隐藏)，状态列删除；新增桥方法 getSwProgramData(swId) → {name,path,version}（版本取 exe 文件版本）
- 旧列配置作废：持久化配置含已不存在的列名时整份回默认（修复 origin_prog 沿用旧 path 显示/58px 列宽）
- 悬浮按钮文案 已隐藏/隐藏 → 显示/隐藏；名称右侧新增"隐藏"标签；切换后整表重渲染以落到次置底

## 名称列横线根因 + 程序表头像 + 标签前缀（2026-10-05）

- 名称列横线根因：td 自身 display:flex → 不再是 table-cell，浏览器插入匿名 cell，td 的 padding/border 画在内层盒子 → 名称格底边比同行其它列错位（JavaFX WebView 实测：旧 nameTd bottom=116.0 vs idTd bottom=126.5；新写法两格一致 239.5）
- 修法：td 保持 table-cell，flex 移到 .manage-nickname-inner
- 悬浮按钮改 position:absolute + 悬浮 display（不占位、不挤压）；自适应宽度仍额外加 QUICK_ACTIONS_WIDTH
- 状态标签改名称前缀 .manage-name-tag（失效→禁用→隐藏），排序仍按 display_name
- 原生程序表加头像列（程序图标，复用 iconCache/extractExeIcon）；行高与账号表一致
- 新技巧：用项目同款 JavaFX WebView 离屏渲染（stage 移到 -4000,-4000 + executeScript 读几何）验证 WebView 真实布局；javac 需 -encoding UTF-8，module-path 需含 javafx.media

## 高清图标 + 悬浮按钮边框 + 把手宽度 + 收起禁拖（2026-10-05）

- 图标模糊根因：FileSystemView 只给 16x16；32x32 需 sun.awt.shell（未 add-exports + 惰性图片 getWidth=-1 双重拦截）。修复：extractIconFromFile 三方案取最大（pickBiggerIcon/iconSide 用 ImageIcon 触发加载），PNG 上限 64→256；build.gradle.kts 与 package-exe.bat 补 --add-exports java.desktop/sun.awt.shell；实测取到 32px
- 悬浮按钮上下边框消失：.manage-nickname-inner 的 overflow:hidden 裁掉了超出文字行高的绝对定位按钮 → 去掉 overflow + min-height:22px
- 把手被拉伸：SVG width:100% + preserveAspectRatio=none，viewBox 必须随窗口宽度同步；此前 resize 未调 initHandleSvg → 补 resize 监听 + 每次重算 path d
- 收起状态禁止拖动底部分割线（拖动会跳到最小高度与鼠标脱节）：onDown 判 collapsed 直接返回 + 光标 syncHandleDragCursor（收起 default / 展开 ns-resize）

## 平台图标 64x64 + PNG 缓存 + 侧栏/标签/记住平台（2026-10-05）

- FileSystemView.getSystemIcon(file,w,h) 支持任意尺寸（实测 48/64/128/256）→ 用它取 64x64，无需 add-exports
- 新增 JsBridge.getSwIcon(swId)：缓存 {userData}/{sw}/{sw}.png；有图且 inst_path 未变直接用；缺图或路径变（比对 LocalSwConfig.icon_src_path）才重提取 64x64 覆盖；失败保留原图
- 左栏与原生程序表共用该缓存；实测 64x64/300+颜色/PNG 2-3KB
- 悬浮按钮改回文档流内（挤压名称 + …截断），背景不透明（--bg-card / --qa-on-bg）
- 状态标签字号 13px（正文-1）+ padding 1px 8px + 圆角 6px + line-height 1.4
- 最左栏收不起兜底：文档级 mousemove + 400ms elementFromPoint 定时校验；统一 collapse()
- 移除左栏"统计"按钮（页面与图标资源保留）
- 记住最后平台：LocalGlobalConfig.last_sw_id，启动直接进入

## 设置区域高度/展开态全局统一 + 图标程序校验 + 光标 + 撤销下划线清洗（2026-10-05）

- 窗帘高度/展开态由 per-platform 改全局（LocalGlobalConfig.settings_height/settings_expanded）；未启用平台（三路径未填全）强制展开且不写全局记录；高度拖动始终全局；旧版按平台记录仅作一次性迁移
- 跨平台丝滑动画保留：animatePanelHeight(targetH, null, _prevHeight)，全局收起→切到未启用平台时从 0 平滑展开
- 改造前代码与经验结晶存档：MEMORY/ARCHIVE_settings_curtain_animation.md（AGENTS 第二十四节引用）
- getSwIcon 增加"必须是程序"校验（isFile && .exe；目录则拼远程 executable，拼不到跳过），避免把文件夹图标当程序图标
- 分割线光标改 CSS 驱动（body.curtain-collapsed）+ MutationObserver 同步（原内联 cursor + 改类前调用导致错位）
- 删除 cleanDisplayName（用户澄清是口误：要的是去分割线，不是去下划线）

## 单一职责修正 + 高度漂移根治（2026-10-05）

- getSwIcon 只判断"软件路径是不是程序"（isFile && .exe），删掉目录+executable 拼接（那是路径探测流程的活）
- 未启用判定改为只读绿框：validatePathInput 写 input-ok/warn/error 类 + swPathGreen[swId][key]；isSwSettingsComplete 只读三项是否都绿；检查结果晚到用 enforceCurtainForCompleteness() 补强制展开
- 高度漂移根因：拖动 content.maxHeight = 面板高-20、动画收尾却用 面板高（+手动展开清空 maxHeight）→ 两套算法；修复为唯一入口 applyPanelHeight(H)（成对设置），_prevHeight 改取语义高度

## 设置区域切换"闪一下"根因：写死的 20px（2026-10-05）

- 现象：跨平台切换 100->100 无动画却闪到 ~120 再回 100；100->300 动画到 ~320 再弹回 300
- 离屏 WebView 逐 25ms 采样四方案高度轨迹：V0(现状 -20)=100->80 闪 / V1(border-box 无内容上限)=滚动条失效 / V2(实测chrome=0)=不丝滑 / V3(面板与内容同值+动画期间内容解除上限)=精确稳定且滚动条正常
- 根因：内容区 max-height 写死 面板高-20，动画期间却 none → 动画到 H、停下回落 H-20，两套高度语义
- 修复：applyPanelHeight(h) 面板与内容区同值，去掉一切偏移数字；教训：父子同高度约束必须同值

## LocalGlobalConfig 冗余清理 + 账号区滚动自动收起（2026-10-05）

- 清理前 11 个顶层节点 → 后 5 个（theme/account_columns/last_sw_id/settings_height/settings_expanded）
- 删除：manage_settings_collapsed（连未引用常量一起删）、manage_settings_height、account_columns.<表id> 扁平键、account_columns.visible/width、account_columns.invalid_acc、account_columns.origin_prog（含已删列 status）
- 新增语义：JsBridge.saveGlobalConfig 中 JSON null = 删除该字段；main.js cleanLegacyGlobalConfig() 启动跑一次；account-table.js 去掉扁平键兼容读取 + 保存时剔除 visible/width
- 两份实际配置文件已就地清理并备份 .bak-20261005
- 账号区滚轮"有效滚动"（scrollTop 真变化）→ 自动收起设置区域；无滚动条/到边界算无效；收起统一走 toggleSettingsPanel(false)，未启用平台不记录

## "刚进平台从 0 涨上来"根因与修复（2026-10-05）

- 离屏采样三场景：A 首次(起点180)=16->180->200 / B 稳定=200 无动画 / C 起点0=0->20->65->...->200（与用户描述一致）
- 根因：未启用平台的本地收起不写全局记录，但面板 inline 高度已是 0；切平台时全局=展开→shouldExpand=true，动画起点取面板当前高度=0 → 走了 0→目标 的假动画
- 每个平台点开一遍后消失：首次访问自动探测路径→平台变启用→不再有本地收起残影
- 修复：首次进入直接落位；本地收起+全局展开直接落位；其余照常动画（全局收起→强制展开仍从 0 涨，保留 4.3 效果）；新增 _prevWasCollapsed/_panelShownOnce

## 设置区域单一渲染依据重构（2026-10-05）

- 现象：记录收起时重启 → 记录收起但渲染展开；切换平台时两套规则拉扯几天才统一（多条写入路径读不同状态）
- 重构：desiredCurtainState() 唯一推导（全局记录 + 未启用平台强制展开）；applyCurtainRender() 唯一 DOM 写入；setCurtainExpanded/setCurtainHeight 先改事实来源再渲染；enforceCurtainForCompleteness 只重调渲染；_lastRender 取代 _prevHeight/_prevWasCollapsed/_panelShownOnce
- 进平台先同步跑绿框检查（避免 200ms 后强制展开造成闪烁）；setPathGreen 在变启用时清 forcedLocalState
- 删除旧 applyCurtainState 与 toggleSettingsPanel 内的独立动画，统一走 animatePanelHeight

## 未启用平台改为"每次渲染强制展开"（2026-10-05）

- 回归问题：单一渲染依据重构后，未启用平台变成了"遵从上次本地状态"，不再强制展开
- 修正：desiredCurtainState 对未启用平台恒返回 expanded=true（每次渲染都无视记录强制展开）；用户本次访问里的临时收起只通过 applyCurtainRender(override) 生效一次，不写记录、不留本地状态（删除 forcedLocalState）
- setPathGreen 只在"启用↔未启用"真正变化时触发重渲染（swEnabledKnown），避免每次失焦检查都把面板重新撑开

## 去掉显示/隐藏的标题区通知 + 标题区写入点排查（2026-10-05）

- 移除 account-table.js 单行"显示/隐藏"操作后的 flashTitle('已隐藏/已显示')（行上已有"隐藏"标签 + 按钮文案变化）
- 标题区（#manage-detail-title）写入点排查：main.js setTitleDisplay（平台进入/备注保存/标题输入回车，唯一正当写入）、main.js flashTitle（仅用于"获取登录窗口尺寸"的成败提示）、account-table.js flashTitle（批量隐藏/显示、批量删除、单行删除 的反馈）

## 彻底移除"借标题当提示条"（flashTitle）（2026-10-05）

- 删除 main.js 与 account-table.js 各自的 flashTitle() 实现（两处独立实现），以及全部 8 个调用点：
  account-table.js（批量隐藏/显示、批量删除、单行删除成功/失败）、main.js（获取登录窗口尺寸的三种提示）
- 标题区 #manage-detail-title 现在只有正当写入：setTitleDisplay()（平台进入 / 保存备注 / 标题输入回车），以及标题输入框的 keydown/blur 绑定
- 副作用：删除失败、获取尺寸失败等错误路径不再有任何提示（行会消失/字段保持空白即为结果）；如需反馈应另建非标题的提示渠道

## 程序表快捷键 / 头像弹窗 / 版本号自动获取 / 自绘勾选框（2026-10-05）

- **快捷键列**：三张表的"快捷键"列改为**非必显**（列头菜单可隐藏）、默认显示；**原生程序表新增该列**（`TABLE_COLUMNS.program`，`initAccountTables` 里 `enableHotkey: true`）
  - 账号表：快捷键存 `SwAccData.<sw>.<acc>.hotkey`
  - **原生程序表 = 平台自身**（没有 SwAccData 节点）→ 快捷键存 `LocalSwConfig.<sw>.hotkey`（`SwCoreConstants.LocalSettingKey.HOTKEY`）；组件新增 `saveHotkey` 选项，`main.js savePlatformHotkey()` 注入。**不要**按 exe 路径往 SwAccData 建节点（会被判成"失效账号"）
- **版本号自动获取**：`SwVersionHelper.getFileVersion` 原先**只从文件名抠版本**（`WeChat.exe` 这类抠不到 → 版本列常年为空）；
  现优先读 **Windows 文件版本资源**（JNA `VersionUtil.getFileVersionInfo` 的 fixed `FileVersionMS/LS`，与旧版 Python `win32api.GetFileVersionInfo` 同源），取不到再回退文件名解析
  - 实测 7 个真实 exe：Weixin `4.1.15.13` / WXWork `5.0.2.6022` / WeChat `3.9.12.55` / QQ `9.7.25.29415` / TIM `3.5.1.22172` / QQNT `9.9.23.42086` / 抖音聊天 `1.1.32.0`（其固定文件版本是垃圾值 `29622.0.0.0` → 自动改用产品版本）
- **头像弹窗**：点列表头像 → `JFC.modal.custom` 弹窗显示**原图**（180px）+「✎ 编辑」+「✕ 移除」
  - 编辑：`JsBridge.pickAccAvatar` → FileChooser → 转 JPEG 写入 `{userData}/{sw}/{acc}/{acc}.jpg` + 清 `avatar_url`，返回新 data URL 就地刷新
  - 移除：`JsBridge.removeAccAvatar` → 删本地头像文件 + 清 `avatar_url`，前端重新拉取（回退到链接账号/网络/文字头像）
- **勾选框自绘**：JavaFX WebView 里原生 `input[type=checkbox]` 会**先画一帧纯方形再套样式**（用户看到"先方后圆"闪烁）→ 改为 `<label class="acc-check">` + 透明 input + 自绘 `.acc-check-box`（4px 圆角 + 主题色勾）
- **顺带修掉 7 处 `Map.of(..., null)` 必然 NPE**（`Map.of` 不接受 null 值）：`AccOpsProvider.ensureCoexistAccFormatted`(3)、`AccOperatorCore`(清 pid + has_mutex)、`AccInfoFuncCore.unlinkHwndOfAccount`、`SwConfigAccessor.getSwSettingAsString`（`SwInfoFuncCore`/`SwOperatorCore` 两个调用方都受影响）、`SwHexUtils`(空结果占位)、`AccInfoFuncCore.deleteAvatarForAcc`

## 头像文字兜底 / 勾选框观感 / 中文字体对照（2026-10-05 第二轮）

- **账号头像文字兜底改为"名称末尾 4 个字符宽"**（中文/全角一个字算 2 宽）：Java 侧 `AvatarUtils.textAvatarLabel()` / `visualUnits()`，
  前端 `JFC.text.tailUnits()` / `visualUnits()`（同一规则两处实现，改一处要同步另一处）
  - 实测：「极峰多聊测试」→「测试」、「张三wx」→「三wx」、「wxid_ab12cd」→「12cd」、「WeCha1」→「Cha1」、空→「?」
  - 兜底用的**名称**：原生账号 = `getAccOriginDisplayName`（备注>昵称>平台内ID>ID）；共存账号 = 链接账号展示名
  - **只影响账号头像**；平台/程序图标兜底（`getDefaultPlatformIcon`、程序表占位）仍是首字符 ✓
  - 4 个字符宽时 SVG 字号自动从 10 缩到 8（`textAvatarFontSize`），保证放得进 18×18 方块
- **勾选框观感**：圆角 4px → **2px**（16px 方块上 4px 会吃掉 ~12% 面积，看起来"没填满"，实测填充 88.3% → 91.5%）；
  勾用 `translate(-50%,calc(-50% - 1.25px)) rotate(45deg)` —— 几何居中后墨迹仍偏下 1.25px，按**像素实测**补偿，实测偏移降到 -0.25px
  - 边框在选中时与填充同色（computed `border=1px rgb(74,158,255)` = `bg`），不存在"边框没填满"的问题
- **中文字体【对照实验区】**（等用户定完再统一，见 TODOS）：
  · 表格列头 `th` = **宋体 SimSun** ｜ 表格内容 `td` = 英文等宽 + **微软雅黑**（`--font-family-mono-yahei`）
  · 按钮 `.btn/.btn-sm/qa-btn` = **本机默认 sans-serif** ｜ 其余区域 = 现状基线（微软雅黑优先）
- **中文抗锯齿试验开关**：`build.gradle.kts` 的 `run` 任务加了 `-Dprism.lcdtext=false`（灰度 AA）。
  实测 JavaFX 默认 LCD（彩色边缘 97%），关掉后边缘对比度 51.3 → **53.5**、彩色边缘 0%（详见 LESSONS 十四第 7 条）

- **中文字体【已定】= 微软雅黑**（用户比对后选定"已选 x 项"所用的字体）：
  统一用于 **状态标签 / 悬浮按钮 / 批量按钮 / 表格列头 / 表内中文**（表内英文仍走等宽 `--font-family-mono`）。
  上一轮的"四处不同字体"对照已结束（宋体/本机默认 sans-serif 均未采用）
- **字号对照实验**（同一字体、五处不同字号，变量在 `theme.css`，挑完统一后要删掉实验注释）：
  | 位置 | 变量 | 当前 |
  |---|---|---|
  | 表格列头 | `--fs-th` | 14px |
  | 表内文字 | `--fs-td` | 15px |
  | 名称状态标签 | `--fs-tag` | 13px |
  | 悬浮按钮 | `--fs-qa` | 12px |
  | 批量按钮 | `--fs-batch` | 13px |
  | **基准：已选 x 项** | （`--font-xs`） | 13px |
  注：**ID 列**有独立规则（等宽 + 13px，`.manage-id-cell`），不参与这次统一
- **勾选框**：圆角 **0**（= 四角填满；实测 `dark=0.0%`、填充 93.1% + 白色勾 6.8%，勾中心偏移 -0.25px）。
  圆角与"四角无黑点"几何上不可兼得，用户选了填满
- **聚焦虚线框**：全局 `*:focus { outline: none; }`（用户要求"本项目不需要这种虚线"；代价是 Tab 切换看不到焦点位置）

- **中文字体【已定】= 微软雅黑**；**字号统一 14px，名称列 15px（比其他列大 1 号）**
- **"中文雅黑 + 英文等宽"怎么落地的（有实测结论，别再走弯路）**：
  本 WebKit **做不到**在一个元素内按字符集混排两种字体 ——
  ① `font-family` 列表里雅黑排在等宽**之后**不生效：缺字时走**系统 CJK 回退**（实测中文墨块 131，雅黑应为 175）；
  ② `@font-face + unicode-range` 在这个版本**不生效**：把中文专用字体放最前，英文也被它吃掉（英文墨块 124 = 雅黑，等宽应为 118）。
  → 采用**两条路并存**：
  · **列级指定**：名称列 / 昵称列 = 雅黑；ID / 版本 / 路径 / 平台内ID / 最后登录账号 = 等宽
  · **名称列再按段拆**：`account-table.js scriptSplitHtml()` 把中文段套 `.cjk-run`、非中文段套 `.lat-run`，
    各自 `font-family`（定义在 `theme.css`）→ 真正实现"名称列中文雅黑 + 英文等宽"
- **字体身份鉴定方法（可复用）**：离屏把同一个字渲染出来比"**墨块数**"。同字号同字重下差异足够大
  （雅黑 175 / 宋体 146 / 等宽回退 131）；像素指纹比对对字重、字号、亚像素位置太敏感，容易误判。
  探针：`build/_probe/FontIdProbe.java`（+ `fontid.html`）

- **勾选框**：**空框与填充态外沿完全相同** —— 16px（含 1px 边框，`box-sizing: border-box`）+ 4px 圆角。
  - 勾选态 = **一整块填充**：`background: primary` + `background-clip: border-box` + **`border-color: transparent`**
    （不能靠"同色的 border"凑 —— 那是"内填充 + 外边框"两层几何，圆角处会露缝，用户看到的镂空就是这个）
  - 实测：填充/空框均 16px、中心重合、**内部镂空 = 0**（形状内部既非填充色也非勾色的像素）、轮廓与空框一致（999 像素里仅 15 个抗锯齿差）
  - 勾：`translate(-50%, calc(-50% - 1.25px)) rotate(45deg)`，中心偏移 -0.25px
  - 圆角的四个角**必然**是背景色（圆角形状定义）；要彻底没有只能 `border-radius: 0`
- **表格字体策略（列级，两张表都对）**：
  | 表 | 名称列 | 其余列 |
  |---|---|---|
  | 账号/共存 | `td.manage-nickname-cell`：15px，中文雅黑 + 英文等宽（`.cjk-run`/`.lat-run`） | ID 列等宽 14px；昵称列雅黑；平台内ID/最后登录账号等宽 |
  | **原生程序** | `td[data-col="name"]`：**15px**，中文雅黑 + 英文等宽（JS `scriptSplitHtml`） | 版本/路径/快捷键 **等宽 14px** |
  - ⚠️ 坑：昵称列的雅黑**必须单独写选择器**。曾写在 `.manage-text-cell, .manage-alias-cell, .manage-nickname-data-cell` 共用组里，
    结果程序表的名称/版本/路径（也都是 `.manage-text-cell`）一起变雅黑了（用户发现："原生程序的内容字体你忘记改了"）
  - **编辑态**：`<input>` + 统一等宽（`contenteditable` 在 JavaFX WebView 里没法正常输入，已回退）

- **表格文字【三级色】**（用户 2026-10-05 定）：1 级最重 → 3 级最轻，**明暗两套是"反"的**。
  令牌 `--text-level1/2/3` 定义在 `theme.css` 的三处（dark `:root`、light、auto+light），**只用于表格内容**（其它 UI 的 `--text-primary/secondary/muted` 不动）：
  | | 1 级 | 2 级 | 3 级 |
  |---|---|---|---|
  | 深色 | `#ffffff` 纯白 | `#c0c0c0` 浅灰 | `#6c6c6c` 深灰 |
  | 浅色 | `#000000` 纯黑 | `#4a4a4a` 深灰 | `#999999` 浅灰 |
  应用规则（实测 computed 值）：**普通行** 名称列=1级、其它列=2级；**隐藏行**（`tr.hidden-row`）整行=2级；**失效行**（`tr.invalid-row`）整行=3级（CSS 里排在 hidden 之后 → 同时满足时失效优先）。
  名称列/头像兜底文字本身有独立 color，需在 invalid/hidden 规则里一并覆盖。
- **行状态类**：`selected` / `hidden-row`（本次新增）/ `invalid-row`（`main.js` 按"是否在 `getSwExistedAccounts` 列表里"判定失效并置底）

- **三张表的名称列完全统一**（用户 2026-10-05 定）：都是 `key='display_name'` → 复用同一个 `.manage-nickname-cell`
  （可点击就地编辑 / **1 级色** / 字号 **15px**（比其它列 +1）/ 字重 600 / 中文雅黑 + 英文等宽分段）。
  程序表通过 `showRowActions:false` 关掉"隐藏/重置/删除"按钮（那是账号语义），其余完全一致。
  ⚠️ 程序表原来的 `key='name'`（普通文本列、不可编辑、2 级色）已废弃 → 列定义改成 `display_name`，`defaultSortField` 同步
- **原生程序名称链**：`SwAccData.<swId>.origin_exe.remark`（原生账号 remark）**>** 平台名称。
  平台名称自身 = 本地 `remark` > 远程 `alias` > `swId`（`getPlatformDisplayName`）。
  - `origin_exe` 是 `AccCoreConstants.ORIGIN_EXE_ID` 定义的**固定 id**，只是"程序自己的备注"节点，**不是账号**：
    `JsBridge.getSwDetailData` / `getAccountList`、`AccConfigAccessor.getAllAccounts`、以及 `JsBridge`/`SwConfigProvider`
    里两处"取第一个账号"的退化路径**都必须排除它**，否则会在账号表里冒出"失效账号 origin_exe"或把备注写错节点
  - 程序表**行 id 从 exe 路径改成 `origin_exe`**（探针里的 `row('origin_prog','origin_exe')`）
  - 程序表名称列编辑 → `saveAccount(swId,'origin_exe',{remark})`（与账号表同一条保存链路）；快捷键仍存 LocalSwConfig
- **`_alias` 已清理**：它是"远程别称"的**内存缓存**，早期被 `swConfigData[sw]._alias = …` 一起**写进了 LocalSwConfig.json**
  （用户在看本地配置时发现）。远程别称随时能取（`getRemotePlatformInfo`），不需要持久化 →
  现在改为按需取，并在加载配置时 `delete config._alias`（下次保存本地文件里那条就没了）。

- **删除 / 重置的语义与副作用**（用户 2026-10-05 明确）：
  | 操作 | 配置层 | 数据目录 |
  |---|---|---|
  | **重置** | 清空该账号节点内容（**保留空节点** → 列表仍能正常加载，初始化流程会重新填属性） | 清除头像文件 |
  | **删除** | **整个节点移除** | 清除头像文件 |
  - 头像文件位置：`{userData}/{sw}/{acc}/{acc}.jpg`（读取端只认这个 jpg；平台图标是 `{userData}/{sw}/{sw}.png`，**不受影响**）
  - 实现：`AccInfoFuncCore.deleteAccountAvatarFiles(sw, acc)` —— 清掉目录里**所有图片**（jpg/jpeg/png/bmp/gif），
    **非图片文件保留**，目录空了才删目录（**绝不递归删其它文件**）；`deleteAvatarForAcc` 改为复用它；
    `JsBridge.resetAccount` / `deleteAccount` 各接一次（探针 `AccFilesProbe` 8 条断言）
- **批量删除只对失效账号生效**（用户定）：**确认框照常弹**（关键：静默不响应会让用户疑惑"为啥点不了"），
  文案按选中情况分三种：全正常 → "…都是正常账号…无法删除；点击删除不会有任何改动"；
  混合 → "…有 N 个是正常账号…**将被跳过**；实际只会删除其中 M 条失效账号记录…"；全失效 → 常规文案。
  用户仍可点确认；**真正删除时只对失效账号动手**，正常账号的配置与文件一律不动。
- **行右键菜单三项齐全**：**隐藏 / 重置 / 删除**；不能做的**显示为禁用（不隐藏）**。
  规则：删除只对失效账号可用（正常账号禁用 + 悬停提示）；隐藏/重置对所有账号可用。
  ⚠️ 实现细节：禁用项**仍要带 `data-row-action`**（否则查不到、也绑不上事件），并在点击处理里 `if (classList.contains('disabled')) return;`。
  （行的悬浮按钮里"删除"仍只对失效行**显示**—— 那块地方窄，用户此前裁定如此；要统一成"显示但禁用"说一声。）
  **重置**则对选中的全部账号生效（有效账号也重置 ✓）

---

# 当前事实速查（2026-10-07 快照）
- **平台页形态**：`pageMode = 'login'`（**默认**）/ `'manage'` —— 右上角二元滑块按钮切换；**会话内变量**（不写配置、不按平台记忆、切平台不改）；未设置完备平台会被强制管理态并写进该变量；登录态下设置区隐藏但**记录不动**、失效/隐藏账号不显示、按钮只剩"登录/批量登录"
- **表顺序**：程序 / **共存** / 原生（共存是主推）；**空表整表不显示**
- **列定义属性**：`key/label/mandatory/pinned/sortable/sortType/loginOnly/defVisible/defWidth/fixed/cellClass`；**`sortable` 默认 true**（勾选框/头像显式 false）；`pinned`（勾选框/头像/名称）= 固定最左且不可拖、但可排序；`loginOnly`（pid/hwnd）= 只在登录态出现
- **三表差异收口**：`rowKind`（`'acc'` / `'prog'`）+ `rowActionsOf(kind, mode, ctx)` 一处来源（名称列按钮 / 右键菜单 / 批量按钮）；`'prog'` 管理态无行操作、登录态给"登录"
- **列交互**：短按列头 = 排序（▲/▼ 紧贴列名、与列名同色）；按下后移动 >4px = 拖动换序（**两阶段**：只动列头 → 松手重建列头 + 整表重刷；落点只认**初始槽位**）；右边缘 = 调宽
- **全选框**：统一在**表格标题行、表名左侧**（列头可整行隐藏）
- **PID / HWND**：**只存内存**（Java `AccRuntimeStore` + 前端 `accRuntimeMap`），不落配置文件；进平台时取一次 + 维护完成后推送
- **表结构**：3 张表 —— 原生程序（勾选框/图标/名称/版本/路径）、原生账号（7 列）、共存账号（7 列 + 最后登录账号）；无效账号已并入后两张（置底 + 3 级灰 + "失效"标签）
- **名称列三表统一**：都用 `key='display_name'` → `.manage-nickname-cell`（可编辑 remark / 1 级色 / 15px / 字重 600 / 中英分段）；行内按钮由 `rowActionsOf(rowKind, mode)` 决定（程序表管理态无按钮）
- **字体**：中文微软雅黑 + 英文等宽（JS 拆段 `.cjk-run`/`.lat-run`）；字号 表内 14px、名称列 15px；编辑框统一等宽（`<input>` 限制）
- **文字三级色**：`--text-level1/2/3`（深色 纯白/浅灰/深灰；浅色 纯黑/深灰/浅灰）；普通行 名称 1 级+其它 2 级、隐藏行整行 2 级、失效行整行 3 级
- **勾选框自绘**：`.acc-check`（透明 input）+ `.acc-check-box`；勾选态 = 一整块填充（`border-color: transparent`）+ 4px 圆角，与空框同外沿
- **列个性化**：`LocalGlobalConfig.json` → `account_columns.<表id>` = `visible` / `width` / **`order`**（列顺序）/ **`hideColNamesInLogin`**（登录模式下隐藏列名 = 整行列头隐藏）
- **设置区窗帘**：`settings_height` / `settings_expanded`（全局一份）；未启用平台（三路径非全绿）每次渲染强制展开且不写记录；唯一渲染入口 `applyCurtainRender()`
- **路径绿框**：由 `validatePathInput` → `JFC.bridge.checkPath` 判定，写 `input-ok/warn/error` 类 + `swPathGreen[swId][key]`；窗帘只读
- **平台图标**：缓存 `{用户数据目录}/{swId}/{swId}.png`（64×64），来源路径记在 `LocalSwConfig.<sw>.icon_src_path`；**账号头像**在 `{用户数据目录}/{swId}/{accId}/{accId}.jpg`
- **启动行为**：读 `last_sw_id` 直接进入上次的平台页；`manage_settings_*` 等历史节点已清理（现只有 theme / account_columns / last_sw_id / settings_height / settings_expanded）
- **账号区交互**：滚轮**有效滚动**（`scrollTop` 真的变化）→ 自动收起设置区（未启用平台只收起不记录）
- **行/列观感**：行高统一（32px 头像列 + `tr[data-acc-id]` 兜底 44px）；悬浮/选中为不透明色块层；表格末尾有占位列
- **标题区**：只显示平台名称（`setTitleDisplay`），无任何"借标题当通知"的写入；`LocalSwConfig` 里**不再有 `_alias`**（历史遗留字段加载时清除）
- **刷新入口**：标题栏 SVG 刷新按钮 → `JFC.router.refresh()`（2s 冷却在路由层）+ 页面顶部进度条（最小显示 400ms）
- **程序表（平台自身）**：快捷键存 `LocalSwConfig.<sw>.hotkey`；名称 = `origin_exe.remark` > 平台名称；版本号读文件版本资源（退化值用 productVersion）
- **删除/重置**：删除 = 节点整体移除；重置 = 清空内容保留空节点；**两者都清该账号的头像文件**（只清图片、保留非图片、只删空目录）；批量删除只对失效账号生效（确认框照常弹）
- **弹窗**：一律 `JFC.modal.confirm/custom`（`window.confirm` 在 WebView 里恒 false、`alert` 空操作）；头像弹窗为居中版式
- **抗锯齿（试验）**：`run` 任务带 `-Dprism.lcdtext=false`（灰度 AA），保留与否待定 → 见 [`TODOS.MD`](TODOS.MD)
- **文档**：`AGENTS.md`（全局视图）｜`MEMORY/{DEV_LOGS,LESSONS,FACTS,DECISIONS,TODOS,MEMORY}.MD`｜`docs/project_structure.md`｜离线探针原先在 `build/_probe/`（**未纳入版本控制，已被 `gradle clean` 清空**）
