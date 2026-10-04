# AGENTS.md — JhiFengMultiChat（极峰多聊）

> 最后更新: 2026-10-04
> 当前阶段: 见 MEMORY/FACTS.MD
> 记忆系统: MEMORY/（MEMORY.md + DECISIONS.MD/TODOS.MD/FACTS.MD/DEV_LOGS.MD）
> 本文件只写**本项目自身**的事实；机器环境、SDK/工具链路径与版本见全局 `~/.dsh/AGENTS.md`，此处不重复记录。

---

## 一、项目身份

- **项目名**: JhiFengMultiChat（极峰多聊）
- **定位**: Windows 桌面端多平台聊天软件管理器（Java 17 重写版）
- **功能**: 微信/企业微信/QQ/TIM/钉钉/飞书多账号管理 — 多开、防撤回、一键登录、窗口切换
- **Python 旧版参考**: `legacy_python/`（不在版本控制中，仅供数据结构/业务逻辑参考）
- **远端**: `origin` = GitHub `wfql1024/MultiWeChatManager`（SSH 443）+ `gitee` 镜像；默认分支 `main`

---

## 二、技术栈

| 层面 | 选型 |
|------|------|
| JDK | 17 LTS |
| 构建 | Gradle (Kotlin DSL) |
| UI | JavaFX 17, `StageStyle.TRANSPARENT` |
| 渲染 | WebView 内嵌 HTML/CSS/JS |
| JSON | Jackson 2.16 |
| 日志 | SLF4J 2.0.9 + Logback 1.4.14 + jul-to-slf4j 桥 |
| HTTP | `java.net.http.HttpClient`（JDK 内置） |
| 加密 | `javax.crypto.Cipher`（AES/CBC/PKCS5Padding） |
| 异步 | `ExecutorService` → `Platform.runLater` → `executeScript` |
| 事件 | 自建 EventBus（`core` 包，观察者模式，数据更新↔UI刷新解耦） |
| 图标 | MCP 服务器 `mcp-universal-icons` + `icons-mcp`（`.mcp.json`） |
| JNA | 5.14.0 (`jna` + `jna-platform`)，用于 Windows API 调用 |
| 测试 | JUnit 5.10.2 + Mockito 5.10.0 |

---

## 三、项目结构、数据存储与配置架构

详见 [`docs/project_structure.md`](docs/project_structure.md)。

---

## 六、页面架构

### 全局侧栏 (`#nav-sidebar`)
平台列表（动态渲染）+ 底部统计/设置入口。由 `main.js` 渲染，`MainWindow.injectJsBridge()` 触发加载。

### 主页面 (`#page-main`)
唯一主内容区，无内嵌左栏。元素查询使用作用域隔离：`querySelector('#page-main #' + id) || document.getElementById(id)`。

### 已废弃
`#page-manage` → `.old/`，`manage.js` → `.old/manage.js`。迁移详情见 `MEMORY/DECISIONS.MD`。

---

## 七、运行命令

```bash
gradle run --no-daemon --args="--dev"      # 开发运行
gradle compileJava --no-daemon             # 仅编译
gradle build --no-daemon                   # 完整构建
gradle test --no-daemon                    # 单元测试
gradle encryptRemoteConfigs --no-daemon    # 加密远程配置 -> remote_configs/（发布工具）
.\scripts\analyze.bat                      # 依赖分析
.\scripts\package-exe.bat                  # EXE 打包 (jlink + jpackage)
.\scripts\encrypt-configs.bat              # 远程配置加密（encryptRemoteConfigs 的包装）
```

### 远程配置维护（日常两大工作之一）

- **源文件**：`scripts/original_remote_global_<vN>.json`、`scripts/original_remote_sw_<vN>.json`
- **流程**：改源 JSON → `gradle encryptRemoteConfigs`（写 `remote_configs/remote_<global|sw>_<vN>`）→ 若版本号变了同步 `RemoteConfigFetcher.BUILTIN_REMOTE_*_VERSION` → 提交推送（客户端按仓库 raw URL 下载）
- **加密实现**：`config.CryptoUtils.encryptAndAppendKey`（与解密同源，工具在 `src/tools` 源集，不进应用产物），测试见 `CryptoUtilsTest`
- 详见 [`docs/project_structure.md`](docs/project_structure.md) 的"开发者工具源集"一节。

---

## 八、待推进

见 `MEMORY/TODOS.MD`：

- 登录页面、统计页面 — 占位未实现
- 数据库层（SQLite + DAO）— 未开始
- 平台图标提取 — ExtractIconExW 完善
- 二进制补丁引擎 — 从 Python 迁移，待评估合法性
- SSL 握手 — 打包版 handshake_failure
- LoggerUtils.java — 待移植
- Handle 操作 — JNA 仿照 pywinhandle.py 重写约 300-500 行
- 登录状态 UI 接入 — 数据已自动维护落库（EventBus 流A），界面未展示
- 其余账号操作的事件驱动迁移 — 删除/批量/头像/快捷键等按 EventBus 流B 增量迁移

---

## 九、近期重大变更

### page-main 复制迁移（2026-07-04~05）

- **决策**: 从 page-manage 完整复制 DOM+JS 到 page-main 页面，`main.js` 复制自 `manage.js` 后做少量作用域修正
- **原因**: 逐段理解和改写容易出错，完整复制再逐步调试更可靠；且保持功能一致性
- **关键修改**:
  - `getEl(id)` 函数改为优先在 `#page-main` 内查找，后备到全局 `document.getElementById`
  - 移除了原管理页的"登录"和"管理"按钮，侧栏精简为平台列表 + 统计 + 设置入口
  - `manage.js` → `.old/manage.js` 归档保留历史
  - HTML 中删除了旧 `#page-manage` 区块

### 头像显示功能重构（2026-07-30）

- **背景**: 账号列表头像不显示，需将 Java 版本调整至与旧版 Python 一致的行为，同时适配用户可设置的自定义数据目录
- **新增**: `AvatarUtils.java` — 核心逻辑封装，获取顺序：本地文件 `{userDir}/{sw}/{acc}/{acc}.jpg` → URL 下载（以 `/0` 结尾）→ SVG 文字头像回退
- **路径使用**: `ConfigManager.getInstance().getUserDataPath()` 支持用户设置的数据目录
- **JsBridge** 中 `getAccountGroupData()` 改单行调用 `AvatarUtils.getAvatarDataUrl()`
- **CSS 调整**: `.manage-account-avatar` `border-radius` 从 `50%` → `6px`（圆角矩形）
- **SVG 文字头像**: 深灰背景 `#555` + 白色首字母，圆角矩形 `rx=6`

详细迁移过程及经验教训见 `MEMORY/DEV_LOGS.MD`。

### 账号列表来源接入磁盘扫描（2026-07-31）

- **背景**: 账号列表仅读 `SwAccData.json` 持久化记录，磁盘真实存在的账号目录/共存 exe 未记录时不显示
- **新增**: `JsBridge.getSwExistedAccounts(swId)` — 用 `SwConfigProvider.newAccessor()` 构建 `SwInfoFuncCore`，调用 `getSwAllAccountsExisted(swId, null)`（磁盘扫描：数据目录子目录 − 排除目录 + 共存 exe）
- **main.js** `loadAccountData` 改为：以磁盘扫描结果为账号来源，按账号 ID 与 `getSwDetailData`（SwAccData.json）详情合并；磁盘已删的残留记录不再显示
- **bridge.js** 新增 `getSwExistedAccounts` 包装

### 头像显示接入（2026-07-31）

- **背景**: 账户列表直接渲染原始 `avatar_url`，未走 AvatarUtils 管道，头像常不显示
- **新增**: `JsBridge.getAccAvatarAsync(swId, accountId, cbId)` — 后台线程先调 `AccInfoFuncCore.getAvatarFromCache`（截图缓存恢复），再用 `getAccAvatarFromFile`（→ `AvatarUtils.getAvatarDataUrl`：本地文件 → URL 下载(`/0` 结尾) → SVG 回退）
- **main.js**: 头像优先级 `avatar_data > avatar_url > 占位符`；`requestAccountAvatar` 异步加载 + `updateAccountAvatarCell` 逐行更新（SVG 回退不降级替换已有真实图片）
- **坑**: `_handleAsync` 第三参必须为字符串，推送 JSON 需双编码（见教训 #45）

### 日志目录修复与"日志"设置项（2026-07-31）

- **logback.xml**: `${jfmultichat.logdir:-logs}` 加默认回退，消除 `jfmultichat.logdir_IS_UNDEFINED` 目录
- **Launcher.java**: `jfmultichat.logdir` 设为 main 首行语句（任何 Logger 前）
- **设置页新增"日志"子项**: 打开日志目录 + 预留"上传日志"按钮；日志目录固定 `AppPaths.getLogsDir()`（`%APPDATA%\JhiFengMultiChat\{ver}\{Dev?}UserFiles\logs`，按 Dev/Prod 模式自动切换，不随用户配置）

### 账号展示名显示（2026-08-01，commit `c2561a4`）

- 账号列表"昵称"列头改为空白（讨论中用"展示名"列代表），`data-sort` 改 `display_name`
- `JsBridge.getSwDetailData` 每账号注入 `display_name` = `AccInfoFuncCore.getAccOriginDisplayName`（remark → nickname → alias → 账号 ID）
- `main.js`：展示名列/头像首字符/排序均改用展示名（前端兜底 `nickname`/`id`）

### SwAccData 账号自动填充（2026-08-01，commit `c2561a4`）

- `AccInfoFuncCore.syncSwAccAccounts(sw, accountIds)` — 遍历磁盘扫描账号列表，SwAccData 缺失节点自动补空
- `JsBridge.getSwExistedAccounts` 取得列表后调用（进入平台页即触发）

### EventBus 事件机制（2026-08-01）

- **新增 `core` 包**: `EventBus` 单例（subscribe/publish）+ `event/PlatformEnteredEvent`、`event/AccountDataChangedEvent`
- **流A 平台进入自动维护**: `selectPlatformInternal` 顶部 → `notifyPlatformEntered(swId)` → `PlatformEnteredEvent` → 后台执行登录态维护（`AccInfoFuncCore.resolvePidAccountMap` → `associateCoexistAccounts` → `updateAccLoginData`，拆分自原 god-method `getSwAccountsLoginStatus`，原方法保留为门面）
- **流B 数据更新定向刷新**: `saveAccount` 更新 SwAccData 后发布 `AccountDataChangedEvent` → UI 订阅者 `pushAccountDataChanged` → `JFC.bridge._onAccChanged` → `main.js onAccountChanged` 仅更新对应行/格（隐藏/禁用→徽章、展示名、头像），不再整表重渲染；`toggle-hidden` 已迁移为事件驱动
- **装配**: `PlatformEventBootstrap.install(bridge)`（MainApp.start 调用）
- **NPE 修复**: `updateAccLoginData` 的 `Map.of(PID, pid, ...)` 因 pid 为 null 抛 NPE → 改 `HashMap`（`updateAccount` 对 null 移除键）；relay 读回 `pidMutexNode.get(pid)` 判空

### 账号列表列定制与交互升级（2026-08-16）

- **7 列结构**: 勾选框（行悬浮才短暂显示，`opacity:0`+`pointer-events:none`）/头像/展示名（右端悬浮操作按钮：隐藏选中态+删除，禁用小标签）/快捷键（点击激活输入框，keydown 捕获组合键，存 SwAccData.hotkey）/ID/平台内ID（`alias`）/昵称（`nickname`）；移除原"状态"/"操作"两列
- **列头右键菜单**（Windows 资源管理器风格）: 勾选显示列（勾选框/头像/展示名/快捷键 4 列必选锁定；ID 默认显示；alias/nickname 默认隐藏）+ "所有列自适应大小"/"该列自适应大小"（临时 span 测量文本宽度）
- **列间竖线拖拽**: `table-layout: fixed` + colgroup，每个可见列 th 右侧注入 `.col-resizer`（7px 热区 + ::after 竖线），拖拽调宽最小 30px，最后可见列不加
- **行右键菜单**: 隐藏/显示、删除（与悬浮按钮同走 `handleAccountAction`）
- **排序标识**: 去掉 " ↕" 字符，当前排序列 th 加 `.sorted`（主题色+加粗）
- **持久化**: 列显示/宽度存 `LocalGlobalConfig.json.account_columns = {visible, width}`（`getGlobalConfig`/`saveGlobalConfig`）
- **onAccountChanged 扩展**: 新增 `hotkey`/`alias`/`nickname` 字段定向更新；状态变化走 `updateRowQuickActions`（按钮选中态/禁用标签，原 stateBadgeHtml 删除）
- **事件委托防重复绑定**: thead/tbody 的 contextmenu、tbody click（快捷键激活）绑在 `bindManageEvents`（一次性），不在每次 render 的 `bindAccountEvents` 里重复 addEventListener

### 四表架构与可复用组件（2026-08-16 第二轮）

- **可复用组件 `JFC.AccountTable`**（`js/components/account-table.js`）: 列定义驱动渲染（任意列组合），含标题行/批量操作/列头右键菜单/列宽拖拽/自适应/行右键菜单/快捷键列编辑/流B 定向刷新；构造参数 `{id, title, container, columns, enableHotkey, defaultSortField, getSwId}`；列配置按表独立持久化 `account_columns.<tableId>`
- **四个表**: 原生程序（勾选框/名称/路径/状态，空）/原生账号（7 列，`getSwExistedAccounts(swId,'origin')`）/共存账号（7 列，空）/无效账号（勾选框/展示名/ID/无效原因，空）
- **标题行**: 常显，标题左端 + "已选 N 项"/批量按钮右侧（未选中隐藏）
- **固定列**: 勾选框/头像 `fixed: true`（不可拖拽/自适应），其间与右侧竖线移除；头像圆角矩形 6px
- **快捷键录入修复**: `document mousedown` 提交替代 blur 同步提交（消除 DOM 竞态假死）；**Java Scene 级 EventFilter 兜底**（`JsBridge.notifyHotkeyCapture` → `JFC.bridge._onHotkeyCapture`，WebView 收不到的带修饰组合键由 Java 捕获；OS 级全局热键占用仍无法拦截）
- **NPE 修复**: `AccInfoFuncCore.getSwAllAccountsExisted` 传 `AccOpsProvider.toSwProvider()`（原 null 导致流A 共存分支 NPE）
- **列宽自适应**: 下限 = 列名宽 + 余量（展示名列 = 4 字符 + 按钮占位），无上限；表格宽度恒 = 可见列宽总和（列宽独立、超宽横向滚动）；固定列（勾选框/头像）绝对固定

### 账号列表交互打磨与滚动条体系（2026-08-16 晚间）

- **滚动条体系（核心难点）**: JavaFX WebView 原生滚动条不可靠——overlay 风格（鼠标悬停才显示）、纵向需手动触发才出现、带上下箭头、不随深浅主题 → 统一改用**自定义 overlay 滚动条**（DOM 元素 `attachCustomScrollbar`）：
  - 不占位不撑高（absolute 定位）、5px 胶囊圆角、无箭头、深浅色适配（`--divider-solid` 同源半透明灰）
  - 显示条件 = **内容溢出** + 鼠标在内容区或滚动条上；移出 600ms 隐藏；在滚动条上不隐藏；滚动/拖拽时显示
  - **挂在滚动容器父级**（absolute 子元素是滚动内容的一部分，挂容器内会被内容带着滚走）；rAF 逐帧检测位置（JavaFX scroll 事件不可靠）+ 拖拽即时刷新
  - 三处统一：表内横向 / 账号区域纵向 / 设置区域纵向
- **高度链锁定（关键）**: 内容撑宽/撑高导致无滚动条、列宽联动、设置区域被拉宽——根因是 flex/grid 交叉轴 `min-width:auto` 与主轴 `min-height:auto`。最终方案：`#page-main .manage-layout` 用 **flex column** + `.manage-detail-area` `flex:1; min-height:0; min-width:0; overflow:hidden` + 表容器链 `min-width:0`；走过弯路：grid `1fr` 被 `#page-main` 高特异性规则覆盖、block 布局破坏纵向
- **设置区域滚动条根因**: `animatePanelHeight` 动画期间 `content.style.maxHeight='none'`（让面板能撑高）但动画后未恢复 → content 高度=内容高永不溢出。修复：动画结束（setTimeout 400ms 兜底，JavaFX transitionend 不可靠）恢复 `content.maxHeight = targetHeight`
- **列宽**: 表格宽度 = 可见列宽总和（px，绝不填充容器，否则 fixed layout 按比例拉伸列）；固定列 `_loadColumnPrefs` 强制 defWidth（不读持久化）；"该列自适应"只改本列
- **整行悬浮高亮**: JS 高亮层 `.acc-row-highlight`（mousemove 委托匹配任意 tr，含空表空行）；**移除 `tr:hover` 背景**避免与高亮层叠加导致列区域/剩余区域颜色不一致
- **分割线**: 设置/账号区域分界线 + 窗帘把手统一用 `--divider-solid`（背景+半透明混合的**不透明等效色**，深 `#2c2c2c`/浅 `#d4d4d4`），避免半透明叠加区两次变深
- **细节**: 空表行高 ≤ 数据行（删旧 `.manage-empty-row td` padding 覆盖）、"暂无数据"居左（不同表合并列宽不同，居中位置不一致）；头像列不显示列名、展示名列改名"名称"；右键菜单扩展覆盖滚动容器空白区域（无"该列自适应"项）
- **NPE 修复**: `AccOpsProvider.toSwProvider().updateSwAccData` 误取 map value（空串）→ 改取 key（共存分支写错账号）；`SwAccountOps.ensureCoexistAccFormatted` 的 `Map.of("linked_acc", null)`（Map.of 禁 null）→ HashMap
- **规则文件**: 项目 `CLAUDE.md` → `AGENTS.md`（DSH/CC 通用约定，DSH 默认候选 `["AGENTS.md","CLAUDE.md"]`）；全局规则在 `~/.dsh/AGENTS.md`（DSH 全局仅认 AGENTS.md，不读 `~/.claude/CLAUDE.md`）

---

## 十、关键技术参考

### Avatar 头像获取流程（自 2026-07-30）
顺序：本地文件 `{userDir}/{sw}/{acc}/{acc}.jpg` → URL 下载（以 `/0` 结尾）→ SVG 文字回退。支持用户自定义数据目录，通过 `ConfigManager.getInstance().getUserDataPath()` 获取。2026-07-31 起账号列表由 `JsBridge.getAccAvatarAsync` 异步接入（先 `getAvatarFromCache` 恢复缓存）。详见 `MEMORY/DEV_LOGS.MD` 和 `MEMORY/FACTS.MD`。

### 账号列表来源（自 2026-07-31）
磁盘扫描：`SwInfoFuncCore.getSwAllAccountsExisted(sw, null)`（数据目录子目录 − 排除目录 + 共存 exe）。由 `JsBridge.getSwExistedAccounts(swId)` 暴露，main.js `loadAccountData` 以它为来源并与 SwAccData 详情合并。

### 日志目录（自 2026-07-31）
固定 `AppPaths.getLogsDir()` = `%APPDATA%\JhiFengMultiChat\{ver}\{Dev?}UserFiles\logs`（`AppEnv.isDev()` 决定 Dev/Prod，不随用户配置）。logback 属性 `${jfmultichat.logdir:-logs}` 有默认回退。

### JS↔Java 异步架构
所有网络操作必须后台线程执行，避免阻塞 UI 线程。调用栈：JS void Java 方法 → 立刻返回 → ExecutorService 后台任务 → Platform.runLater → executeScript → JS 回调更新 DOM。详见 `MEMORY/DEV_LOGS.MD`。

### 六级路径探测策略
内存映射正则 > 注册表 > 猜测 > 进程 > 其他SW > DLL遍历。由 `SwPathDetective.detectAll()` 并发执行，支持超时保护。`swcore` 包内部详细说明。

### 账号展示名（自 2026-08-01）
`AccInfoFuncCore.getAccOriginDisplayName(sw, acc)` — remark → nickname → alias → 账号 ID。`JsBridge.getSwDetailData` 每账号注入 `display_name`，前端展示名列/头像首字符/排序均用之。

### EventBus 事件机制（自 2026-08-01）— 新增数据操作逻辑的标准路径

**核心**: 数据更新与 UI 刷新解耦。账号/平台数据更新操作写库后发布事件，UI 订阅者自动定向刷新对应 UI 块，**不再整表重渲染**。

**新增一条「账号字段更新」操作的标准步骤**:
1. **Java 写库后发布事件**: 更新方法中 `ConfigManager.getInstance().updateAccount(...)` 之后加 `EventBus.getInstance().publish(new AccountDataChangedEvent(swId, accountId, changedMap))`（changedMap = 本次更新的字段 map）
2. **前端定向更新**: 在 `main.js` 的 `onAccountChanged(payload)` 中按 `payload.changed` 字段处理对应单元格——`hidden`/`disabled` → `updateRowStateBadge`、`display_name` → `.manage-nickname-cell`、`avatar_url` → `updateAccountAvatarCell`；未知字段忽略（幂等）
3. **无需改装配**: `PlatformEventBootstrap` 已注册流B订阅，自动推送

**新增一条独立数据需求（如登录态 UI、HWND 等）**:
1. 在 `core/event/` 包定义新事件（record）
2. 发布点发布；`PlatformEventBootstrap.install` 中 `EventBus.getInstance().subscribe(事件类, 处理器)` 注册
3. 耗时处理放 `JsBridge.runInBackground()`（共享 THREAD_POOL），UI 推送用 `pushToJs`（内部 Platform.runLater）

**关键实现**:
- `com.jfmultichat.core.EventBus` — 单例，`ConcurrentHashMap<Class, CopyOnWriteArrayList<Consumer>>`，单个订阅者异常不拖垮其它；publish 在调用方线程同步分发
- 事件: `PlatformEnteredEvent(swId)` / `AccountDataChangedEvent(swId, accountId, changed)`
- Java→JS 主动推送: `JsBridge.pushAccountDataChanged` → `JFC.bridge._onAccChanged(json)`（**双编码**，见教训 #45）→ `JFC.pages.main.onAccountChanged`
- JS→Java 触发: `JFC.bridge.notifyPlatformEntered(swId)` → `JsBridge.notifyPlatformEntered` → 发布 `PlatformEnteredEvent`
- 登录态维护管线（流A）: `AccInfoFuncCore.resolvePidAccountMap` → `associateCoexistAccounts` → `updateAccLoginData`（原 `getSwAccountsLoginStatus` god-method 拆分）

---

## 十一、关键技术教训

1. **WebView 拦截鼠标** → 透明 Region 覆盖层绕过
2. **location listener 二次触发** → suppressLinkIntercept 标志
3. **maximized 拖拽** → DRAG_THRESHOLD=4 阈值
4. **UTF-8 BOM** → `.bat` 用 Bash `cat >` 写
5. **Logback 属性时序** → `jfmultichat.logdir` 必须在首次 `LoggerFactory.getLogger()` 之前
6. **HTTP 重定向** → `HttpClient` 默认不跟随，必须 `.followRedirects(NORMAL)`
7. **WebView JS bridge 返回值** → boolean 可能被序列化为字符串，JS 端用 `=== true` 严格比较
8. **配置拆分** → 代理/URL 存 RootConfig.json（不随数据迁移移动），软件偏好存 LocalGlobalConfig.json
9. **URL 保存 bug** → `saveConfigData()` 中 `updateGlobalConfig` 必须在所有字段收集完毕后调用，不能提前
10. **配置文件名** → 双驼峰 PascalCase：`RootConfig.json`, `LocalGlobalConfig.json`, `RemoteSwConfig.json` 等
11. **配置实时读取** → `JsonConfigStore.getData()` 每次自动 `reload()` 从磁盘解析；读写锁保证并发安全；`reloadInternal()` 不持锁供 `getData()` 调用
12. **内存映射查询** → 用 `VirtualQueryEx` + `GetMappedFileNameW`（通过 `Kernel32Ext` 扩展接口）遍历进程所有物理内存区域，等价于 Python `psutil.Process(pid).memory_maps()`；`GetMappedFileNameW` 返回 NT 路径需经 `convertNtPathToWin()` 转盘符路径
13. **SwNativeOps 日志标签** → 模块列表用 `[路径内存映射-MEMMAP]`，匹配用 `[路径内存映射-MATCHED]`，DEBUG 级别不输出
14. **构建脚本** → `run.bat` 仅运行（不触发编译）；`build-run.bat` 先 `compileJava compileTestJava` 再 `run`，适合开发快速迭代
15. **Java varargs 与 JS bridge 不兼容** → JavaFX WebView 的 Netscape JSObject 桥无法将 JS 参数映射到 Java `String...` varargs（JVM 方法描述符多一个 `[String` 槽位导致反射匹配失败）。必须用固定参数，pathKeys 用 JSON 字符串传递
16. **路径中的反斜杠导致 JS JSON.parse 静默失败** → Windows `File.getParent()` 返回 `\` 路径 → Jackson 序列化为 `\\` → 嵌入 JS 单引号字符串时 `\\` 被解析为 `\` → JSON 中出现非法转义 → `JSON.parse` 抛 SyntaxError 被空 catch 吞掉。修复：所有路径在存入 PathEntry 前统一经 `normalizePath()` 处理
17. **路径规范化统一** → `SwPathDetective.normalizePath()` 统一处理：去引号、`\`→`/`、盘符大写、去末尾分隔符。所有 PathEntry 构造点必须调用
18. **ConcurrentHashMap 不允许 null 值** → 多线程合并结果时用 `Collections.synchronizedMap(new LinkedHashMap<>())`
19. **overflow:hidden 裁剪绝对定位子元素** → 下拉面板在 `position:absolute` 时被父容器 `overflow:hidden` 裁剪。解决方案：面板用 `position:fixed` 挂在 body 层，通过 `getBoundingClientRect()` 定位
20. **CSS 伪元素与 HTML 内容冲突** → `::after { content:'▼' }` 与 HTML 中的 `▼` 文字同时存在导致双图标。只用一种方式（HTML 文字 + `::before` 背景方块）
21. **用户数据目录命名** → 字符串常量必须用 PascalCase：`UserFiles`/`DevUserFiles`（非 `user_files`/`dev_user_files`）
22. **fixed 定位子元素的 z-index 受父容器层叠上下文限制** → `position:fixed` 元素的父容器若也设了 `z-index`（创建独立 stacking context），子元素 z-index 只在父容器内部有效，无法与父容器外元素比较。下拉面板的 `#mg-dropdown-layer` 设为 `z-index:40` 后子面板的 `z-index:80` 无效，必须将 layer 也调到 `40`
23. **侧栏 z-index 体系** → 主左栏 `100` > 次级左栏 `50` > 下拉面板 `40` > 默认 `0`。侧栏有 `position:relative` 创建层叠上下文
24. **overflow:hidden 裁剪 absolute 子元素** → 父容器 `overflow:hidden` 会裁剪 `position:absolute` 的子元素（即使设了 `z-index`）。下拉面板不能放在有 `overflow:hidden/auto` 的容器内，必须挂到 body 层；窗帘把手在面板内部时，展开态用 `overflow:visible`、收起态用 `overflow:hidden`
25. **CSS 路径规范化贯穿全链路** → 前端 `replace(/\\/g, '/')` + 后端 `Path.toString().replace('\\','/')` 双保险；设置页 `getActualDirVal()`、`getDefaultUserDir`、`saveConfigData` 返回值全链路规范化
26. **窗帘把手设计** → `position:absolute; bottom:0; transform:translate(-50%,50%)` 锚定面板底边半露出；`width:36px; border-radius:10px` 圆角胶囊流线型；仅方向符号 `∧`/`∨`；hover 变主题色
27. **路径检查必须先判存在** → `checkPath` 中 `Files.exists()` 为 false 时直接返回「路径不存在」（红色），不进入 `isValidSwPath` 详细检查逻辑（r_concat/l_concat/r_contain/l_contain）
28. **下拉面板缓存合并策略** → 每次打开面板重新探测，但新结果与旧缓存合并（同路径覆盖更新、新路径追加、旧独有保留），避免 DLL 路径依赖软件路径时因缓存清空丢失旧结果
29. **inline style 残留污染状态恢复** → 收起动画设置 `panel.style.maxHeight='0px'`（inline），完成后未清除。切换平台时 `classList.remove('collapsed')` 无法覆盖 inline style → 面板卡在高度 0。修复：`applyCurtainState` 展开时 `panel.style.maxHeight=''`，收起时显式设 `'0px'`
30. **collapsed 时 scrollHeight=0 导致展开动画无效** → 面板 `max-height:0` 时 `scrollHeight` 返回 0，过渡目标为 0 无动画。修复：先 `remove('collapsed')` 读真实 `scrollHeight`，快照到 0，再 rAF 过渡到真实高度
31. **SVG pointer-events:none 阻止 click 事件** → SVG 设 `pointer-events:none` 后 click handler 无法触发，需绑在内部 `pointer-events:auto` 的子元素（如热区 rect）上
32. **平台状态持久化** → 设置面板展开/收起状态按平台独立存储在 `LocalSwConfig.json.{swId}.settings_expanded`（boolean），用 `updateSwField` 写入、`getSwConfig` 读取；切换平台时先读后应用
33. **AppEnv 运行环境判断** → `AppEnv.java`：先读 JVM 系统属性 `run.mode`（支持 DEV/TEST/PROD），再自动检测 code source 路径是否以 `.jar` 结尾 → PROD:DEV；`Launcher` 中 `--dev` 参数改为设 `run.mode=DEV` 系统属性
34. **路径检查详细提示** → `SwAdapterChecker.checkSwPathDetail()` 返回 `{valid, reason}` 含中文提示：r_concat→"缺少关键文件「{file}」", l_concat→"应在「{text}」文件夹内", r_contain→"未找到含「{text}」的文件", l_contain→"上级目录应包含「{text}」"
35. **跨平台动画复用原则** → 不同平台之间切换时的高度过渡，视觉效果上完全可以转化为"同一页面内的高度变化动画"。先记录 A 平台当前高度 `_prevHeight`，切换到 B 后直接调用已验证的单页面动画函数 `animatePanelHeight(savedH, null, _prevHeight)`，从 `_prevHeight` 平滑过渡到 `savedH`。不引入新条件分支、不手动控制 transition、不复刻展开/收回逻辑。**已验证可复用的动画函数，就直接复用，不要重写。**
36. **把手与面板容器一体化** → 将面板和 SVG 把手包裹在 `#manage-curtain-container`（`position:relative`）中，把手 `position:absolute; bottom:-20px` 自动跟随容器底部，移除所有 JS 手动定位代码（`getBoundingClientRect`、`style.top`、`startFollow/stopFollow` RAF 循环）
37. **内容区 max-height 是高度上限的隐形锁** → CSS `.manage-settings-content { max-height: 180px }` 会限制面板实际高度。自由高度动画前必须将内容区设为 `max-height: none`，否则面板涨不上去
38. **transition: none 快照与 transition 恢复必须在不同帧** → 单 `requestAnimationFrame` 保证快照帧与过渡帧分离；双 RAF 不一定更好（可能引入额外延迟）
39. **`getBoundingClientRect().height` 比 `parseInt(style.maxHeight)` 更可靠** → 前者返回实际渲染高度（含 padding/border），后者可能为空字符串或受 CSS 覆盖
40. **纯复制迁移法** → 从旧代码中完整复制 DOM + JS 到新位置，保持 ID/逻辑完全相同，再通过实际效果逐步调试。不会破坏原本已实现的页面和逻辑，远比"理解后重写"更可靠。例如 page-main 复制自 page-manage，main.js 复制自 manage.js
41. **`getEl` 作用域隔离** → 复制出的页面与原始页面存在相同 DOM ID，`document.getElementById` 始终返回 DOM 中第一个匹配。修复：`getEl` 改为 `querySelector('#page-main #' + id) || document.getElementById(id)`，优先在目标页面内查找
42. **`bind()` 也要走 `getEl`** → `bind(id, evt, fn)` 内部必须用 `getEl(id)` 而非 `document.getElementById(id)`，否则事件绑定到原始页面元素而非副本页面
43. **JS Bridge 注入时序** → `DOMContentLoaded` 时 JS Bridge 尚未注入（Java 端 `injectJsBridge()` 在页面加载完成后才执行）。页面初始化如需调用桥方法，应由 `MainWindow.injectJsBridge()` 末尾主动 `executeScript` 触发，而非依赖 `DOMContentLoaded`
44. **跨页面联动使用 `document.getElementById`** → 主侧栏 `#nav-platform-list` 不在 `#page-main` 内，不能走 scoped `getEl`。跨页面的元素查询直接用 `document.getElementById`
45. **`_handleAsync` 第三参必须是字符串** → `bridge.js` 的 `_handleAsync(type, cbId, jsonStr)` 仅当 `typeof jsonStr === 'string'` 才 `JSON.parse`。Java 端 `pushToJs` 若直接嵌入 JSON 对象字面量，JS 侧 `data` 为 null（回调拿到 null）。修复：`pushToJs("..._handleAsync('avatar',"+cbId+","+ MAPPER.writeValueAsString(payload) +")")` — 把 JSON 字符串再编码为 JS 字符串字面量（对 SVG data URL 内单引号也安全）
46. **Logback 未定义属性 → `${name}_IS_UNDEFINED` 目录** → `${jfmultichat.logdir}` 必须加默认值回退 `${jfmultichat.logdir:-logs}`（`<file>` 与 `<fileNamePattern>` 两处）；否则任何绕过 Launcher 的入口（IDE 直接跑 MainApp、测试、回归）都会在 cwd 生成 `jfmultichat.logdir_IS_UNDEFINED/`
47. **logdir 属性需在首次 `LoggerFactory.getLogger()` 前设置** → Launcher 将 `System.setProperty("jfmultichat.logdir", AppPaths.getLogsDir().toString())` 放在 main 首行；`AppPaths`/`AppEnv`/`AppVersion` 均无 Logger，可在 pre-init 安全读取路径
48. **后台会话 worktree 隔离可关闭** → `.claude/settings.json` 设 `"worktree": {"bgIsolation": "none"}` 后后台会话可直接编辑主目录文件（需用户授权；该文件被 gitignore，仅本地）
49. **日志目录固定根配置位置** → 设置页打开/显示日志目录用 `AppPaths.getLogsDir()`（`%APPDATA%\JhiFengMultiChat\{ver}\{Dev?}UserFiles\logs`），不随用户自定义数据目录；与 logback 实际写入位置一致
50. **`Map.of` 不允许 null 键/值** → 写账号数据回写时 `Map.of(PID, pid, ...)` 因未运行账号 pid 为 null 直接 NPE（`ImmutableCollections$MapN` 构造器 `Objects.requireNonNull`）。必须用 `HashMap`；`ConfigManager.updateAccount` 对 null 值会移除该键（未运行账号不存 pid，语义正确）。同理对 `JsonNode.get(key)` 结果先判空再 `.asBoolean`

---

## 十二、代理与网络（2026-10-04）

- **原则**: 代理**只由界面"使用代理"复选框控制**，不做任何自动探测、不默认开启；未勾选一律直连
- **历史现象**: 直连 `raw.githubusercontent.com` 报 `javax.net.ssl.SSLHandshakeException: Remote host terminated the handshake` —— 根因是 Java **默认不使用 Windows 系统代理**（`java.net.useSystemProxies` 默认 false）；在界面勾选"使用代理"并填好地址端口即可
- **立即生效**: `AppCore.applyProxySetting()` 设置 JVM 属性 `http(s).proxyHost/Port`（+ `http.nonProxyHosts=localhost|127.*|[::1]`）；`HttpClient` 的默认 `ProxySelector` 每次请求都读这些属性，所以**运行期修改立即生效，无需重启**
  - 界面勾选 / 改地址端口 → `JFC.bridge.applyProxyConfig(json)`：只持久化代理三个字段 + 立即应用，并回传归一化结果回填输入框（`settings.js` 的 `commitProxyConfig()`）
  - 点"保存配置" → `saveConfigData()` 内同样调用一次 `applyProxySetting()`
  - `Launcher.main` 启动时调用一次（覆盖"上次已勾选"的情况）
- **地址归一化**（`AppCore.splitHostPort` / `isValidPort`）: 允许 `http://127.0.0.1:7890`、`127.0.0.1:7890`、`127.0.0.1` + 端口分开填、`[::1]:7890`；端口必须 1..65535，非法则按直连并提示
- **教训**: 代理地址不能原样塞进 `https.proxyHost` —— 含 `:` 的"主机"会被 JDK 当成 IPv6 加方括号，报 `java.net.URISyntaxException: Expected closing bracket for IPv6 address at index 20: proxy.https://[http://127.0.0.1]:7890/`。必须剥掉协议前缀并拆出端口
- **远程配置下载**: `JsBridge.downloadRemoteConfigs()` 的候选 URL = **用户配置 + 内置兜底**（`JsBridge.mergeUrls()`）。此前只取用户列表，用户把「远程配置源」清空后日志出现 `候选URL: 0个`、远程配置永远下载失败 —— 已修复
- **gitee 现状**: gitee 对 `remote_configs/remote_*` 判定违规返回 451（与网络无关）；候选列表里 gitee 失败会自动继续尝试 GitHub
---

## 十三、共存账号数据接入（2026-10-04）

- **前端**: `main.js` 的 `loadAccountData(swId)` 现在同时拉取原生与共存两路数据，抽公共的 `buildAccountRows(ids, detailMap)` 生成行；`origin_acc` / `coexist_acc` 各自 `setData`；头像按表路由（`requestAccountAvatar(swId, acc, table)`，此前写死更新原生表）
- **共存账号来源**: `JsBridge.getSwExistedAccounts(swId, 'coexist')` → `SwAccountOps.getSwAllAccountsExisted(..., only='coexist')` → 安装目录中匹配 `executable_wildcards` 的 exe（排除原生 exe），并 `ensureCoexistAccFormatted` 写入 SwAccData
- **本次修掉三个 Java 缺陷**（否则共存表永远是空的）:
  1. **取错配置键**: `SwInfoFuncCore.getSwAllAccountsExisted` 读的是 `exe_wcs`（该键在远程配置中根本不存在，Python 里 `RemoteSwKey.EXE_WCS = "executable_wildcards"`）→ 通配符列表恒空 → 共存扫描恒 0。改为常量 `SwCoreConstants.RemoteSwKey.EXECUTABLE_WILDCARDS`
  2. **accountOps 传 null**: `JsBridge.getSwExistedAccounts` 构造 `SwInfoFuncCore` 时第 4 参为 null，共存分支调用 `ensureCoexistAccFormatted` 直接 NPE（WXWork 实测）→ 改传 `new AccOpsProvider().toSwProvider()`
  3. **inst_path 可能是目录**: `SwAccountOps` 原来一律 `new File(instPath).getParent()`；WeChat/DouYinIM 的 inst_path 存的是**安装目录本身** → 扫到上一级目录、共存 exe 全漏。抽出 `resolveInstDir()`：是目录就用它，是 exe 才取父目录
- **实测结果**（2026-10-04 本机）: WeChat 2 个（`WeCha1.exe`/`WeCha2.exe`）、WXWork 1 个（`WXWor1.exe`）；Weixin/QQNT/QQ/TIM/DouYinIM 无（该目录下确无匹配 exe）
- **已知数据问题（非代码）**: `LocalSwConfig.json` 里 TIM 的 `inst_path` 指向 `D:/software/Tencent/QQNT/QQ.exe`（应为 TIM 自己的 Bin 目录），导致 TIM 共存扫描找不到东西——需要重新探测/修正路径
- **测试**: 新增 `SwAccountOpsTest`（3 例，覆盖 exe 路径/目录/null 三种 inst_path）
---

## 十四、共存账号列 + 列配置持久化 + 侧栏展开（2026-10-04）

- **共存账号新增列「最后登录账号」**: `TABLE_COLUMNS.coexist = TABLE_COLUMNS.account.concat([{key:'linked_acc', ...}])`（非必选、默认显示、宽 170）；值来自 SwAccData 的 `linked_acc`（该共存 exe 当前关联/最后登录的原生账号），行数据在 `buildAccountRows()` 里已带出
- **列显隐/列宽不持久化（已修）**: `AccountTable._saveColumnPrefs` 写的是**扁平键** `"account_columns.<表id>"`，而 `_loadColumnPrefs` 读的是**嵌套** `account_columns[表id]` → 右键勾选的显示列下次启动就丢
  - 修复：写嵌套结构；因 `saveGlobalConfig` 是**顶层浅合并**，必须先 `getGlobalConfig()` 读出 `account_columns` 再合并本表，否则会清掉其它表的列配置
  - 兼容：`_loadColumnPrefs` 增加历史扁平键回退读取（迁移一次，下次保存写回嵌套），用户此前勾选的列不会丢
- **最左栏（`#nav-sidebar`）展开改为「静止 2 秒」**: `nav-sidebar.js` 的 `EXPAND_DELAY` 300ms → **2000ms**，并新增 `MOVE_THRESHOLD = 6px`：鼠标在区域内移动超过阈值就**重新计时**，微动（<6px）不重置，真正停下 2 秒才展开；移出立即收起
  - 注：页面内的次级左栏 `#manage-platform-sidebar` 被 CSS `display:none` 隐藏，其 `main.js#initManageSidebar` 的 300ms 逻辑实际不生效，未改动
- **测试**: JS 侧 `node --check` 通过（无 JS 单测框架）；Java 侧未改动逻辑
---

## 十五、设置页"配置"三块独立保存（2026-10-04）

- **背景**: 原来只有一个"保存配置"按钮，同时校验本地目录 + 要求"平台/全局各自至少一个地址测试通过"，于是"只想改本地目录"也会被"远程配置源测试失败"挡住
- **结构**: 代理 / 本地目录 / 远程配置源 三块，用两个 `.config-divider` 分隔，每块右下角一个"保存"（`.config-actions config-actions-block`：靠右、无上边框）
  - 每块只提交**自己的字段**：Java `JsBridge.saveConfigData` 本来就是 `if (data.has("x"))` 逐字段合并 → 天然支持部分提交，未提交字段保持原值
  - JS 侧：`saveBlock(payload, msgId, onSuccess)` 共用；`saveProxyConfig` / `saveDirConfig` / `saveUrlConfig` 各自独立
- **代理块**: 地址/端口**常驻显示**（不再随"使用代理"勾选显隐）；点"保存"才持久化 + 立即应用
  - `applyProxyConfig` 新增 **`requiresRestart`**：持久化成功但运行期应用抛异常时为 `true` → 前端 `alert` 提示需重启；正常应用 → "保存成功"；勾选了但地址非法（`applied=false`）→ 红字说明并按直连
- **本地目录块**: 保存按钮默认禁用，仅 `#cfg-user-dir` 带 `input-ok`（绿框）时启用；目标目录已有文件时仍弹迁移确认
- **远程配置源块**: "测试全部/添加"移到各自列表头部右侧（`.url-block` + `.url-block-head`，原 `.url-list-footer` 删除）；保存按钮仅在 `sw`/`global` 中**至少一个**地址测试通过时启用；加载时**不再预置绿框**（`lastValidSet` 不再用于标记），必须本次会话实际测试成功
- **风格统一**（跨板块一致）: 新增 `.config-desc`（板块介绍，替换各板块行内样式：主题/配置三块/日志/更新）；`.config-label` 字号 `--font-h2`→`--font-h3`（与 `.config-subtitle` 一致）；输入框（`.config-input` 与 `.url-input-line input`）统一 `padding:7px 10px` + `var(--font-sm)` + `var(--border-radius)` + `font-family:inherit`（URL 输入框不再用等宽字体）；次级按钮（`.config-preset-btn`/`.config-presets .btn`/`.url-input-line .btn-sm`）统一 `6px 12px` + `var(--font-sm)`；提示文字统一 `var(--font-xs)`；`.config-form .settings-section` 的 margin-bottom 归零，间距交给 `.config-divider`
- **清理**: 删除旧的全局 `#cfg-btn-save`/`#cfg-save-msg`；`showMsg` 签名改为 `showMsg(元素id, msg, isErr)`；`updateSaveButton` → `updateBlockButtons`（按块判定）
---

## 十六、账号列表细节打磨 + 共存账号属性来源（2026-10-04）

- **共存账号属性一律参考 linked_acc**（自身只认 remark）: `main.js` 的 `buildAccountRows(ids, detailMap, followLinkedAcc)` —— 共存表传 `true`
  - 名称链：自身 `remark` > 链接账号 `nickname` > 链接账号 `alias` > 链接账号 id（`linked_acc`）> 共存账号自身 id
  - `nickname`/`alias`/`avatar_url` 三列直接取链接账号的值（共存 exe 一般没有这三个属性）；原生账号走原逻辑（Java `getAccOriginDisplayName`）
- **共存账号头像链**: `AvatarUtils.getCoexistAvatarDataUrl(sw, coexistAcc, linkedAcc, linkedAvatarUrl)` = 自身本地文件 > 链接账号本地文件 > 链接账号头像地址（下载）> 默认文字头像
  - 接线在 `JsBridge.getAccAvatarAsync`：SwAccData 里该账号带非空 `linked_acc` 就走共存链（原生账号没有这个字段），**无需新增桥方法**，前端调用不变
  - 新增 `AvatarUtils.getLocalAvatarDataUrl(sw, acc)`（仅本地判定，不联网）供链路前两步使用
- **列宽拖拽热区修复**: `.col-resizer` 原来 `right: -3px; width: 7px`，被 `th { overflow: hidden }` 裁掉一半（实际可点约 4px，且落在最右列的表格边界上很难命中）→ 改为 `right: 0; width: 7px`（热区完全在列内），竖线用 `::after { right: 0 }` 画在列右边界。`linked_acc` 等新列由此与其它列一样可拖拽、可"所有列/该列自适应"
- **整行背景层（悬浮/选中）**: `tr` 背景只能覆盖列区域，覆盖不到表格右侧空白 → 统一用绝对定位色块层，且放到**表格内容之下**
  - `.acc-row-highlight`（悬浮，不透明 `--bg-row-hover`）+ 新增 `.acc-row-selection-layer`（选中，每选中行一个 `.acc-row-sel`，`--bg-row-selected`）
  - 两层 `z-index: -1`，配合 `.acc-table-scroll { z-index: 0; isolation: isolate }` 形成层叠上下文 → 色块盖住容器整宽又不遮挡文字；宽度由 JS 设为 `max(表格宽, 容器可视宽)`
  - 选中行**不再显示悬浮色**（`_updateRowHighlight` 遇到 `.selected` 直接隐藏）；移除 `tr.selected` 背景与 `tr{transition:background}`，避免半透明叠加
  - 新增不透明色变量（theme.css 三个主题块）：`--bg-row-hover` `#282828`/`#dfdfdf`、`--bg-row-selected` `#313131`/`#d8d8d8`（= 原半透明色叠在 `--bg-sidebar` 上的不透明等效色）
- **表头行高度**: `.acc-table-titlebar` 加 `min-height: 38px; box-sizing: border-box` —— 选中后出现"已选 N 项"+批量按钮时不再把这一行撑高
- **最左栏展开延时**: `nav-sidebar.js` `EXPAND_DELAY` 2000ms → **1000ms**（静止 1 秒展开，`MOVE_THRESHOLD` 6px 不变）
- **远程配置源保存条件**: 平台(remote_sw) 与 全局(remote_global) **都**要有绿框（AND），`updateBlockButtons`/`saveUrlConfig` 同步改
---

## 十七、账号表末尾占位列 + 菜单文案（2026-10-04）

- **末尾占位列（filler column）**: 表格末尾多一个内部列 `_filler`（`FILLER_COL`），**不在 `columns` 里**，因此不参与排序/显隐勾选/列菜单
  - 宽度 = `容器可视宽 - 可见列宽总和`（下限 0）；`_updateTableWidth()` 里一并算出：`table.style.width = 可见列宽总和 + filler`
  - 效果：① 表格总宽恒 ≥ 容器宽 → **所有真实列（含最右列）右侧都有邻居**，列宽拖拽热区不再压在表格边界上；② 占位单元格属于该行 → **行悬浮/选中的感应区天然覆盖整行**（此前鼠标移到最右列右侧空白处，`closest('tr')` 为 null，悬浮色会消失）
  - 列宽总和 ≥ 容器宽时 filler = 0，其 th/td 加 `hidden-col`（不显示多余边框），横向滚动条照常出现
  - 细节：th/td 用类名 `.manage-col-filler`（**不带 `data-col`**）→ 不会被 `_applyColumnLayout` 的显隐循环碰到；`col` 仍带 `data-col="_filler"` 供设置宽度；空表行 `colspan = columns.length + 1`
  - 右键占位列 → `colByKey('_filler')` 为 null → 菜单**不出现"该列调至合适宽度"**（用户要求）
- **菜单文案**: "所有列自适应大小" → **"所有列调至合适宽度"**；"该列自适应大小" → **"该列调至合适宽度"**
- **表头行更高**: `.acc-table-titlebar` `min-height` 38px → **46px**（选中后出现批量按钮时高度完全不变）
---

## 十八、列宽不生效的真正根因：隐藏列的 col 宽度（2026-10-04）

- **现象**（用户实测）: 隐藏了部分列之后，**最右可见列**既拖不动也"调至合适宽度"无效；**只有所有列都显示时列宽才正常**
- **根因**: `table-layout: fixed` 下**列宽取自 `<col>`**。原实现隐藏列时只给该列的 `th/td` 加了 `.hidden-col { display: none }`，**`<col>` 的宽度仍是原值** →
  - 表格 CSS 宽度 = 可见列宽总和（`_updateTableWidth`）
  - 但声明的列宽总和 = 可见列 + 隐藏列（更大）
  - 固定的表格布局在"列宽总和 > 表格宽度"时会**重新分配/撑开列宽** → 真实渲染宽度不再等于 `colWidth` → 拖动最后一列或自适应改的是声明值，渲染结果被重新分配吃掉，看起来"完全改不动"；所有列都显示时两者恰好相等，所以一切正常
- **修复**: `_applyColumnLayout` 里隐藏列的 `<col>` 同时**归零并隐藏**：`col.classList.toggle('hidden-col', !visible)` + `col.style.width = visible ? 实际宽 : '0px'`（真实宽度仍保存在 `colWidth`，重新显示即恢复）
  - 另加取整：拖拽宽度 `Math.round` + `_updateTableWidth` 里 `sum = Math.round(sum)`，避免小数宽度让"总和 + 占位列"恰好超出容器 1px 而冒出横向滚动条
- **占位列宽度**: `filler = 容器可显示宽(clientWidth) - 可见列宽总和`（≥0）→ 占位列右端**恰好落在列表区域右边缘**；可见列总宽超过容器时 filler = 0、横向滚动条出现
---

## 十九、名称列宽度/悬浮按钮占位/等宽字体（2026-10-04）

- **名称列"调至合适宽度"要含按钮预留宽**: `fitColumn` 里名称列的量取改为**只量名称**（`.dn-text` + `.manage-disabled-tag`，用 `querySelectorAll(...).textContent` 拼接，避免把按钮文字"隐藏/删除"算进去），然后 `maxW += QUICK_ACTIONS_WIDTH`（96，两个按钮最宽态"已隐藏"+"删除" + gap + padding + border 的估算）；下限仍是 `4 字宽 + QUICK_ACTIONS_WIDTH + 8`
- **悬浮按钮常驻占位（修复悬浮时文字位移/截断）**: `.manage-row-quick-actions` 从 `display:none ↔ inline-flex` 切换改为 **`display:inline-flex` + `visibility:hidden ↔ visible`**
  - 根因：按钮用 display 切换时，悬浮瞬间才占宽 → `.dn-text`（flex:1）被挤压、长名称当场变省略号，视觉上就是"文字位移"
  - `visibility:hidden` 的元素不参与命中测试，未悬浮时按钮仍不可点击
  - 与上一条配套：合适宽度已包含按钮预留宽，所以常驻占位不会白白浪费空间
- **列表内容统一等宽字体**: `.manage-account-table td { font-family: var(--font-family-mono) }`（Cascadia Code / Consolas / Sarasa Gothic SC，中文有 Sarasa 兜底）；**表头 th 仍用界面字体**（次级色 + 半粗，作为"标题"与内容区分）