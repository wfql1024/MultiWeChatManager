# DEV_LOGS — 开发过程记录

> 本文件用于记录临时性、易变性的开发决策、实验过程和调试信息。项目骨架类事实请放入 FACTS.MD。

---

## 开发过程架构笔记

> 以下为项目核心架构设计记录，涉及系统交互模式和通信机制。

### JS↔Java异步架构

**绝对不能阻塞 UI 线程！** 所有网络操作必须后台线程执行。

```
JS 调用 void Java 方法 → 立刻返回
                   ↓
       ThreadPool 后台线程
       · HTTP 下载  · AES 解密  · JSON 解析
                   ↓
       Platform.runLater → scriptExecutor
       → JFC.bridge._handleAsync(type, cbId, jsonStr)
                   ↓
       JS 回调更新 DOM
```

**关键方法**：
- 同步: `getSwConfig()`, `getSwDetailData()`, `getSwExistedAccounts()`, `saveSwConfig()`, `extractExeIcon()`, `getLogDir()`
- 异步: `testRemoteUrlAsync(url, cbId)`, `fetchUpdateDataAsync(cbId)`, `tryEnsureRemoteConfigsAsync(cbId)`, `detectPathsAsync(swId, cbId, pathKeysJson)`, `getAccAvatarAsync(swId, accountId, cbId)`
- **detectPathsAsync 注意**: 第三个参数是 JSON 字符串 `'["inst_path","data_dir"]'`（非 varargs！JavaFX JS 桥不支持 varargs），为空时默认全三项

### 远程配置兜底机制

任何需要读取远程配置的操作，都必须先检查 → 缺失则异步下载 → 失败则 toast 提醒 + 强制跳转设置页。

```
JFC.ensureRemoteConfigs(onReady)
  ├── checkRemoteConfigReady() — 同步快速检查
  ├── 已就绪 → onReady()
  └── 缺失 → tryEnsureRemoteConfigsAsync() — 后台下载
        ├── 成功 → onReady()
        └── 失败 → JFC.toastError(msg) + forceGotoSettings()
```

调用点：`app.js` 启动检查、`manage.js` loadPlatformList / selectPlatform

### Toast通知系统

```javascript
JFC.toastError('消息', duration);    // 右下角红色，默认 4 秒
JFC.toastSuccess('消息', duration);  // 右下角绿色，默认 3 秒
```

动态创建容器 `#toast-container`，带 ✕ 手动关闭。CSS: `main.css` `.toast-container` / `.toast`。

### 页面架构

### 全局侧栏 (`#nav-sidebar`)
平台列表（动态渲染）+ 底部统计/设置入口。平台列表由 `main.js` 渲染，进入软件即加载（`MainWindow.injectJsBridge()` 触发）。

### 主页面 (`#page-main`)
唯一主内容区，无内嵌左栏。`main.js` 中 `getEl` 作用域隔离: `querySelector('#page-main #' + id) || document.getElementById(id)`。跨页面元素（`#nav-platform-list`）直接用 `document.getElementById`。

### 详情区
路径输入框（内嵌 ▼ 下拉面板，body 层 `position:fixed`，z-index:40）、设置面板（窗帘折叠 + 高度拖动）、账号表格（多选 + 排序 + 批量操作）。自动填充优先级: 存在 > 进程 > 内存映射 > DLL遍历 > 注册表 > 猜测/其他SW > 来源数量。

### 设置页各页面状态

| 页面 | 数据来源 | 加载方式 | 关键方法 |
|------|---------|---------|----------|
| 外观 | LocalGlobalConfig.json | 同步 | `getTheme()` / `saveTheme()` |
| 配置 | RootConfig.json | 同步 + 异步测试 | `getConfigData()` / `saveConfigData()` / `testUrlAsync()` |
| 日志 | 本地日志目录 `AppPaths.getLogsDir()` | 同步 | `openLogDir()` / `getLogDir()` |
| 更新 | RemoteGlobalConfig (network) | **异步** | `fetchUpdateDataAsync()` + "更新远程配置"按钮 |
| 鸣谢 | RemoteGlobalConfig (network) | **异步** | `fetchThanksDataAsync()` |
| 关于 | RemoteGlobalConfig (network) | **异步** | `fetchAboutDataAsync()` |

### 加密协议

远程配置文件加密格式（对应 Python `CryptoUtils.decrypt_response`）：

```
HTTP 响应文本 = base64(IV[16] + ciphertext) + " " + key
解密: Base64解码 → IV=前16字节, key=key.ljust(16)[:16].encode()
     → AES/CBC/PKCS5Padding 解密 → UTF-8 JSON
```

Java 实现: `CryptoUtils.decryptResponse(String)`，每步有 `[INFO]` 级日志。

**下载/解密日志关键词**: `[下载]` 和 `[解密]`，搜这两个 tag 即可追踪完整流程。

---

## 头像显示功能重构（2026-07-30）

### 背景
账号列表头像不显示，需将 Java 版本调整至与旧版 Python 一致的行为，同时适配用户可设置的自定义数据目录。

### 修改内容

1. **新增 `AvatarUtils.java`** (`src/main/java/com/jfmultichat/utils/AvatarUtils.java`)
   - 核心方法：`getAvatarDataUrl(sw, acc, avatarUrl)` → data URL (base64 SVG)
   - 获取顺序：本地文件 `{userDir}/{sw}/{acc}/{acc}.jpg` → URL 下载（以 `/0` 结尾）→ SVG 文字头像回退
   - 路径使用 `ConfigManager.getInstance().getUserDataPath()`（支持用户自定义数据目录）
   - 关键日志：`[头像] INFO` 级别输出每一步状态

2. **修改 `JsBridge.getAccountGroupData()`**
   - 单行调用 `AvatarUtils.getAvatarDataUrl()` 替代原有复杂逻辑

3. **CSS 调整** (`src/main/resources/web/css/main.css`)
   - `.manage-account-avatar`: `border-radius` 从 `50%` → `6px`（圆角矩形）

4. **SVG 文字头像样式**
   - 深灰背景 `#555` + 白色首字母（大写），圆角矩形 `rx=6`

### 经验教训（开发笔记）
- `img` 标签内的 SVG 无法继承外部 CSS 的 `currentColor`，需用硬编码颜色（#555 + white）
- ConfigManager 的用户路径优先于 AppPaths 默认路径，确保设置页修改的数据目录生效
- 日志级别需设为 INFO（root level=INFO），debug 级别不会输出到控制台
- 所有文件路径在存储前统一用 `replace('\', '/')` 转义，避免 JSON 解析错误
- 文字头像取首字符而非旧版的最后4字符，更符合左栏平台图标风格

### 验证方式
启动应用后观察 Java 控制台是否有 `[头像]` 日志，浏览器中应显示带首字母的灰色圆角头像。

## 历史对话基本大纲(2026-07-30)
1. 分析当前账号列表头像显示逻辑（JsBridge.getAccountGroupData + main.js渲染）
2. 对比旧版 Python 获取头像的方式（AccInfoFuncCore.get_acc_avatar_from_files）
3. 设计新方案：AvatarUtils工具类 + ConfigManager路径 + SVG文字回退
4. 实现代码修改（Java类、JsBridge引用、CSS样式）
5. 记忆系统整理：DEV_LOGS.md记录本次任务，FACTS.MD骨架化，CLAUDE.md精简
6. 验证与问题排查指导（日志级别、SVGcurrentColor问题、路径正确性）

---

## page-main 复制迁移（2026-07-04~05）

### 背景
将原有的 manage.js 页面功能迁移到 page-main，作为应用的主页。用户希望保持现有功能完整的同时简化侧栏导航。

### 执行过程

1. **完整复制** - 将 manage.js 的内容复制到 main.js，DOM 结构保持不变
2. **侧栏精简** - 移除"登录"和"管理"两个导航按钮，仅保留平台列表、统计和设置入口
3. **作用域隔离修复** - `getEl(id)` 函数从 `document.getElementById` 改为 `querySelector('#page-main #' + id) || document.getElementById(id)`，确保元素查询只在主页面内优先查找
4. **旧代码剥离** - 将 manage.js 移至 `.old/manage.js`，HTML 中删除 `#page-manage` 区块
5. **JS 注入时序调整** - `MainWindow.injectJsBridge()` 在 WebView 加载完成后注入桥，并主动执行 `if(JFC.pages.main)JFC.pages.main.init()` 触发主页面初始化

### 关键设计决策

- **保守迁移策略**：先完整复制再调试，避免逐行重写导致的功能丢失或回归错误
- **保留旧代码**：`.old/` 目录保留历史版本，便于回溯和对比
- **单一主页原则**：page-main 成为默认首页，manage.js 仅作为历史归档

### 验证方式
启动应用确认：
- 侧栏仅显示平台列表、统计和设置入口
- 主页面功能（平台选择、路径探测、账号管理）正常运作
- Java 控制台无 JS 错误，头像显示正常

---

## 账号列表来源 + 头像显示 + 日志设置页（2026-07-31）

### 一、账号列表来源接入磁盘扫描
- 背景: 列表仅读 SwAccData.json 持久化记录；磁盘真实存在的账号目录/共存 exe 未记录时不显示
- 实现:
  - `JsBridge.getSwExistedAccounts(swId)` → `SwConfigProvider.newAccessor()` + `SwInfoFuncCore.getSwAllAccountsExisted(swId, null)`（返回 `List<String>` 账号 ID）
  - `main.js loadAccountData` 以磁盘结果为准，按账号 ID 与 `getSwDetailData` 详情合并；未记录新账号显示空白详情，磁盘已删残留记录不再显示
- 关键: `SwInfoFuncCore` 构造传 `(accessor, null, null, null)`；accountOps 为 null 在共存分支安全（`AccInfoFuncCore` 静态方法同模式）

### 二、头像显示接入
- 背景: 直接渲染 avatar_url 不显示；AvatarUtils 未接入桥
- 实现: `getAccAvatarAsync` 后台线程：`AccInfoFuncCore.getAvatarFromCache`（截图缓存恢复本地文件）→ `getAccAvatarFromFile`（AvatarUtils 三路：本地文件 → URL 下载(`/0` 结尾) → SVG 回退）→ `_handleAsync('avatar', cbId, json)` 推送
- 前端: 头像优先级 `avatar_data > avatar_url > 占位符`；`requestAccountAvatar` 异步加载（`_avatarFetching` 防重）+ `updateAccountAvatarCell` 逐行更新（SVG 回退不降级替换已有真实图片）
- **大坑**: `_handleAsync` 第三参若传对象字面量则 JS 侧 `data`=null（不触发 `JSON.parse`）。必须双编码：`MAPPER.writeValueAsString(payload)` 包一层 → JS 收到字符串 → parse 成功（SVG data URL 内单引号也安全）

### 三、日志目录修复
- 现象: 根目录出现 `jfmultichat.logdir_IS_UNDEFINED/`（Logback 对未定义属性 `${name}_IS_UNDEFINED` 的替换产物），内容为 7/14-18 历史遗留
- 修复:
  - logback.xml: `<file>` 与 `<fileNamePattern>` 两处改 `${jfmultichat.logdir:-logs}`（属性缺失回退相对 logs，永不再出现 _IS_UNDEFINED）
  - `Launcher.main`: `System.setProperty("jfmultichat.logdir", ...)` 移到 main 首行（任何 Logger 前）
  - 删除遗留目录 `jfmultichat.logdir_IS_UNDEFINED/`
- 验证: 运行后日志写入 `%APPDATA%\JhiFengMultiChat\4.0.0.7000\DevUserFiles\logs`，根目录无新 _IS_UNDEFINED

### 四、设置页"日志"子项
- 导航: `#settings-nav` 加 `<li data-setting="log">日志</li>`（与"外观""配置"同级）
- 区块: `#settings-section-log`（`config-form` 结构）：日志目录路径显示（`#log-dir-path`）+ "打开日志目录"（btn-primary）+ "上传日志"（占位，点击 toast「上传功能待实现」）
- JS: `settings.js` `logInited` 标志 + `initLogSection()` + `showSection` 分发 `if (name === 'log')`
- Bridge: `openLogDir()`（`Desktop.getDesktop().open`，目录不存在先创建）+ `getLogDir()`
- **路径决策**: 固定 `AppPaths.getLogsDir()`（`%APPDATA%\JhiFengMultiChat\{ver}\{Dev?}UserFiles\logs`，`AppEnv.isDev()` 决定 Dev/Prod），**不随用户自定义数据目录**；与 logback 实际写入一致

### 五、仓库卫生
- commit `5216773`: 纳入 acccore/appcore/SwConfigProvider + docs/project_structure.md + 账号列表/头像两功能
- legacy_python 保持忽略（用户确认）；.old 暂不动
- 后续提交 `e7e348c`: 日志修复 + 设置页"日志"子项 + 文档（6 文件）
- 后台会话 worktree 隔离: 用户要求直接改主目录文件，`.claude/settings.json` 设 `"worktree": {"bgIsolation": "none"}`（gitignored）

---

## 展示名 + SwAccData 自动填充 + EventBus 事件机制（2026-08-01）

### 一、账号展示名显示
- 背景: "昵称"列头名不副实，应显示 remark 优先的展示名
- 实现:
  - `JsBridge.getSwDetailData` 每账号注入 `display_name` = `AccInfoFuncCore.getAccOriginDisplayName(sw, id)`（remark→nickname→alias→账号 ID）
  - index.html 表头 "昵称 ↕" → " ↕"（去文字留排序箭头），`data-sort="nickname"` → `"display_name"`
  - main.js: `sortField` 默认改 `display_name`；渲染用 `acc.display_name || nickname || id`；头像首字符同步用展示名

### 二、SwAccData 账号自动填充
- 背景: 磁盘扫描出账号但 SwAccData 无节点，详情无法挂载
- 实现: `AccInfoFuncCore.syncSwAccAccounts(sw, accountIds)` 遍历 `getSwAccData(sw, acc)` 检查，缺失 `updateSwAccData(sw, acc, emptyMap)` 补空节点；`JsBridge.getSwExistedAccounts` 取得列表后调用

### 三、EventBus 事件机制（核心）
- **动机/痛点**: 数据更新只能在每个更新方法里触发整表重渲染，刷新带动系列加载；`getSwAccountsLoginStatus` 为 god-method（配置/pid/写库/状态计算耦合）
- **选型讨论**: ① 自建 EventBus（选定：订阅方零依赖 JsBridge、可扩展）；② JsBridge 多槽 Consumer（订阅方须持 JsBridge 引用）；③ JavaFX Property（FX 线程约束）。用户选定①
- **新增**:
  - `core/EventBus.java`: 单例，`ConcurrentHashMap<Class, CopyOnWriteArrayList<Consumer>>`，publish 调用方线程同步分发，单订阅者异常隔离
  - `core/event/PlatformEnteredEvent(swId)` / `AccountDataChangedEvent(swId, accountId, changed)`
  - `PlatformEventBootstrap.install(bridge)`: 流A 订阅（后台维护）、流B 订阅（定向推送 UI）
- **流A 平台进入自动维护**:
  - 前端 `selectPlatformInternal` 顶部 `JFC.bridge.notifyPlatformEntered(swId)` → `JsBridge.notifyPlatformEntered` 发布事件
  - 订阅者 `JsBridge.runInBackground` 后台执行: `resolvePidAccountMap` → `associateCoexistAccounts` → `updateAccLoginData`（拆分自 `getSwAccountsLoginStatus`，原方法保留门面，去掉 `relayData`/`hasMutex` 死代码）
- **流B 数据更新定向刷新**:
  - `saveAccount` 写库后发布 `AccountDataChangedEvent(swId, acc, updates)`
  - 订阅者 `JsBridge.pushAccountDataChanged` 双编码推送 `JFC.bridge._onAccChanged(json)`（教训 #45）
  - 前端 `main.js onAccountChanged`: 定位 `tr[data-acc-id=...]`，按 changed 字段更新徽章（`updateRowStateBadge`，复用 `stateBadgeHtml`）/展示名（`.manage-nickname-cell`）/头像（`updateAccountAvatarCell`），未知字段忽略
  - toggle-hidden 迁移: 去掉 `renderAccountTable(accountData)`，事件推送定向更新徽章（"返回后仅更新这一块"）
- **线程模型**: publish 同步（调用方线程）；耗时订阅者 `runInBackground`；UI 推送 `pushToJs`（内部 Platform.runLater）

### 四、NPE 修复（Map.of null 值）
- 现象: 切换平台约 3 秒后 `[PlatformMaintenance] 维护失败` NPE @ `updateAccLoginData:565`
- 根因: `Map.of(AccKey.PID, pid, ...)` 中未运行账号 pid=null → `ImmutableCollections$MapN` 构造器 `Objects.requireNonNull` 抛 NPE（原 god-method 未接线从未触发，接入后暴露潜伏 bug）
- 修复: 改 `HashMap`（`ConfigManager.updateAccount` 对 null 值移除键 → 未运行账号不存 pid）；relay 读回 `pidMutexNode.get(pid)` 先判空再 `.asBoolean`（缺省 false）
- 教训 #50

### 五、仓库卫生
- commit `c2561a4`: 展示名 + 自动填充（4 文件）
- 本次提交: EventBus 全套（MainApp/AccInfoFuncCore/JsBridge/bridge.js/main.js + 新增 core/ + PlatformEventBootstrap）+ 文档（CLAUDE.md/MEMORY/project_structure.md），已通过进入平台页与隐藏切换实测、维护日志无报错

---

## 账号列表列定制与交互升级（2026-08-16）

### 一、新列结构（7 列，从左到右）
| 列 | 来源 | 说明 |
|----|------|------|
| 勾选框 | — | 行内勾选框默认 opacity:0 + pointer-events:none，仅行悬浮/选中时短暂显示；列头全选框保留常显 |
| 头像 | 现状 | 无列名、不可排序 |
| 展示名 | display_name | 无列名；右端悬浮操作按钮（隐藏/删除），仅行悬浮显示；禁用账号旁加小标签 |
| 快捷键 | SwAccData.hotkey | 点击单元格激活输入框，keydown 捕获组合键（Ctrl/Alt/Shift+字母/数字/F键），Esc 取消、Enter/失焦保存 |
| ID | id | 列名"账号ID"→"ID" |
| 平台内ID | SwAccData.alias | 默认不显示 |
| 昵称 | SwAccData.nickname | 默认不显示 |

### 二、列头右键菜单（Windows 资源管理器风格）
- thead contextmenu → `#account-col-menu`（body 层 fixed，z-index:500，视口边界翻转定位）
- 勾选显示列：4 个必选列（勾选框/头像/展示名/快捷键）锁定不可取消；ID 默认显示；平台内ID/昵称默认隐藏
- "所有列自适应大小" / "该列自适应大小"：临时 span 测量（复制 fontFamily/fontSize/fontWeight）+ padding，头像列按内容物宽度
- 配置持久化：`LocalGlobalConfig.json.account_columns = {visible: {...}, width: {...}}`（getGlobalConfig/saveGlobalConfig）

### 三、列间竖线拖拽调列宽
- `table-layout: fixed` + colgroup，列宽由 `<col data-col>` 控制（JS 覆盖 width）
- 每个可见列 th 右侧注入 `.col-resizer`（absolute，7px 热区 + ::after 1px 竖线），mousedown→mousemove→mouseup 拖拽，最小 30px
- 拖拽时 `body.resizing-cols` 禁文本选择；松开保存宽度
- 最后一个可见列不加竖线；可见列变化后重建（applyColumnLayout → initColResizers）

### 四、状态/操作列移除（用户决策）
- 移除"状态"徽章列与"操作"按钮列
- 行内操作改为展示名列右端小按钮：`隐藏`（选中态 .on = 已隐藏，高亮）/`删除`（红），仅行悬浮显示
- 行右键菜单：隐藏/显示、删除（与按钮同走 `handleAccountAction`）
- 禁用状态保留为展示名旁 `.manage-disabled-tag` 小标签（数据态，无切换入口）
- 状态推送：saveAccount → AccountDataChangedEvent → `onAccountChanged` → `updateRowQuickActions` 定向更新按钮选中态/标签（原 stateBadgeHtml/updateRowStateBadge 删除）

### 五、排序标识
- 去掉列头 " ↕" 字符（index.html thead 清理）
- 保留点击排序，当前排序列 th 加 `.sorted`（主题色 + 加粗）标识

### 六、onAccountChanged 扩展
- 新增处理字段：hotkey（更新快捷键单元格，data-editing 期间跳过）/alias（平台内ID格）/nickname（昵称格）
- display_name 更新定位 `.manage-nickname-cell .dn-text`（展示名现在包 span）

### 七、关键实现要点
- **事件委托防重复绑定**：thead contextmenu / tbody contextmenu / tbody click（快捷键激活）绑在 bindManageEvents（一次性，容器元素不变），不在每次 render 的 bindAccountEvents 里重复 addEventListener（否则监听器累积）
- **隐藏列**：th/td 同步加 `hidden-col`（display:none），col 宽度保留不影响；7 列始终渲染保证表头与数据对齐
- **快捷键编辑**：`data-editing` 标记防 EventBus 推送覆盖输入框；blur commit 与 Enter commit 用 done 标志防双触发
- **行点击选中排除** hotkey cell / qa-btn / input
- 空行 colspan 6→7

### 八、验证状态
- node --check 通过；gradle compileJava 通过
- 应用实例正在运行锁定 build 目录 → processResources 清理失败，GUI 实测待应用重启后进行

---

## 账号列表四表架构与交互优化（2026-08-16 第二轮）

### 一、可复用列表组件 `js/components/account-table.js`（核心架构）
- 新增 `JFC.AccountTable` 组件类：列定义驱动渲染（任意列组合）、标题行、批量操作、列头右键菜单、列宽拖拽/自适应、行右键菜单、快捷键列编辑、EventBus 流B 定向刷新
- 构造参数：`{id, title, container, columns, enableHotkey, defaultSortField, getSwId}`
- 列定义：`{key, label, mandatory, sortable, defVisible, defWidth, fixed, cellClass}`（mandatory=必选锁定；fixed=固定宽不可拖拽/自适应；cellClass=td 附加类）
- 列配置按表独立持久化：`LocalGlobalConfig.json.account_columns.<tableId> = {visible, width}`
- 全局右键菜单 `#account-col-menu`/`#account-row-menu` 多表共用，`activeTable` 记录当前操作的表；`JFC.AccountTable.closeMenus()` 供外部关闭

### 二、四个表（平台页从上到下）
| 表 | 列定义 | 数据 |
|----|--------|------|
| 原生程序 | 勾选框/名称/路径/状态 | 暂无数据 |
| 原生账号 | 账号 7 列（勾选框 fixed/头像 fixed/展示名/快捷键/ID/平台内ID/昵称） | `getSwExistedAccounts(swId,'origin')` |
| 共存账号 | 账号 7 列 | 暂无数据 |
| 无效账号 | 勾选框/展示名/ID/无效原因 | 暂无数据 |

- `JsBridge.getSwExistedAccounts(swId, only)` 新增 only 参数（"origin"/"coexist"/空=全部），对应 `SwAccountOps.getSwAllAccountsExisted` 的 only 过滤

### 三、标题行（替代原浮动工具行）
- 每表标题行常显：标题左端，"已选 N 项" + 批量按钮（批量隐藏/显示/删除）跟随右侧，未选中时隐藏
- 批量操作在组件内独立管理（每表自己的 selectedIds）

### 四、固定列与竖线
- 勾选框列（40px）/头像列（56px）`fixed: true`：固定宽度、不可拖拽、不参与自适应
- 固定列之间及固定列右侧不注入 `.col-resizer` 竖线（头像左右两侧均无竖线）
- 头像 `border-radius: 50%` → `6px`（圆角矩形）

### 五、列头右键菜单
- 去掉"必选"字样（disabled checkbox 已表达）；固定列"该列自适应大小"显示为禁用

### 六、快捷键录入大修改（修复假死）
- **根因分析**：旧实现 `blur` 时同步 `commit`（替换单元格 DOM）与 `click` 事件竞态 → 点击其他位置后 DOM 已变，click 目标丢失 → "点击无反应"；被 OS 全局热键占用的组合键在 WebView 收不到 → 表现为录入中断
- **修复**：
  - 提交改为 `document mousedown`（点击编辑格外时提交），移除 blur 同步提交，消除竞态
  - 编辑状态全局单一管理（`_editFinish`/`_editDocMousedown`），切换行/重载数据时正确收尾
  - **Java Scene 级捕获兜底**：`JsBridge.notifyHotkeyCapture(active)` 在 Scene 挂 `KeyEvent` EventFilter（capture 阶段），带修饰键组合键推送 `JFC.bridge._onHotkeyCapture` → JS 更新输入框（WebView 收不到的按键兜底；OS 级全局热键占用仍无法拦截）
  - `MainWindow` 创建 Scene 后 `bridge.setScene(scene)`
  - 输入框支持退格/方向键编辑、Enter 提交、Esc 取消
- **已知边界**：OS 级全局热键（其他软件 RegisterHotKey）在系统层拦截，JavaFX/WebView 均收不到——该组合无法录入，属桌面应用通例

### 七、NPE 修复（顺带）
- `AccInfoFuncCore.getSwAllAccountsExisted` 未传 accountOps（null）→ 流A 维护在共存分支 NPE（`ensureCoexistAccFormatted`），WeChat 平台实测触发；改为 `new AccOpsProvider().toSwProvider()`

### 八、验证状态
- node --check 全部通过；gradle compileJava 通过
- 应用重启实测：进入 Weixin 平台，6 账号原生表渲染、头像异步加载、平台维护完成，无 JS 错误无 NPE
- 列宽自适应逻辑待与用户探讨（见上方提问）；GUI 交互实测待用户反馈

---

## 账号列表交互打磨与滚动条体系（2026-08-16 晚间）

### 一、滚动条问题全排查（核心难点，多轮迭代）
- **现象演变**: ①横向滚动条不出现（列宽总和>容器时无条）；②纵向滚动条不出现；③设置区域滚动条需手动调整高度才触发；④滚动条被内容带着滚（absolute 子元素是滚动内容的一部分）；⑤滚动条不随主题、带箭头
- **根因链**:
  1. **列宽联动/无横向滚动**: `table-layout:fixed` + 表格宽=容器宽时多余空间**按比例分配列**（拖宽一列全部变、永不超宽）→ 修：表格宽度恒=可见列宽总和（px）
  2. **内容撑宽容器**: grid `1fr` 列被表格撑宽（`#page-main .manage-layout { grid-template-columns:1fr }` 高特异性覆盖了 `minmax(0,1fr)`）→ 修：page-main 改 flex column + 各级 `min-width:0`
  3. **内容撑高容器（纵向滚动条不出现）**: `.manage-detail-area` 高度 auto 被四表内容撑高 → 无纵向溢出 → 修：`.manage-detail-area { flex:1; min-height:0; min-width:0; overflow:hidden }` + flex column 高度链
  4. **设置区域滚动条需手动触发**: 诊断日志（`console.log` 经 WebView→Java 日志可见）定位——`animatePanelHeight` 动画期间 `content.style.maxHeight='none'`（教训 #37 让面板能撑高）但动画后未恢复 → content 高度=内容高永不溢出 → 修：动画结束恢复 `content.maxHeight=targetHeight`
  5. **滚动条被内容带着滚**: absolute 子元素在滚动容器内是滚动内容 → 修：滚动条**挂滚动容器父级**（宿主 position:relative）
  6. **JavaFX 原生滚动条不可靠**: overlay 风格（鼠标悬停才显示）、纵向需手动触发、带上下箭头、不随深浅主题 → 统一用**自定义 overlay 滚动条**（DOM 元素）
- **自定义滚动条 `attachCustomScrollbar(container, axis)`**（account-table.js）:
  - 挂宿主（container.parentElement）不随内容滚动；不占位不撑高（absolute）
  - 5px 胶囊圆角、无箭头、深浅色适配（`[data-theme="light"]` 变深色半透明）
  - 显示条件 = **内容溢出**（hasOverflow，含子元素实测高度兜底）+ 鼠标在内容区/滚动条上；移出 600ms 隐藏；在滚动条上不隐藏（onBar）；滚动/拖拽显示
  - **rAF 逐帧检测**位置/尺寸（JavaFX scroll 事件不可靠，setInterval 100ms 会一顿一顿）+ 拖拽即时刷新
  - 折叠态 track 尺寸 0 保护（NaN 防护）
- **三处统一**: 表内横向（组件 _buildDom attach）/账号区域纵向（main.js `.account-area-inner` + MutationObserver）/设置区域纵向（main.js `.manage-settings-content`）
- **教训**: JavaFX WebView 的 scroll 事件、transitionend、内联样式 CSS 变量（`style="background:var(--x)"`）均不可靠——用 rAF 轮询、setTimeout 兜底、CSS 类而非内联变量

### 二、布局与交互细节
- **高度链**: 见上根因 2/3；页面 `#page-main .manage-layout` 最终用 **flex column**（block 破坏纵向、grid 有覆盖陷阱）
- **列宽**: 表格宽=列宽总和；固定列（勾选框 40/头像 56）`_loadColumnPrefs` 强制 defWidth 不读持久化（防旧配置污染）；自适应下限=列名宽+8px（展示名列=4字符+按钮占位 96px），无上限；fitColumn 只用本列
- **整行悬浮高亮**: JS 高亮层 `.acc-row-highlight`（CSS 类背景与 tr:hover 同源 `--bg-hover`）；mousemove 委托匹配**任意 tr**（含空表空行，`closest('tr')` + parentNode 校验）；**移除 `tr:hover` 背景**（叠加导致列区域/剩余区域颜色不一致——用户截图分析出 48/44/64 三色）；render 后清 hover
- **分割线**: 设置/账号区域分界 `border-top: 1px solid var(--divider-solid)` + 把手 `fill: var(--divider-solid)`；`--divider-solid` = 背景+半透明混合的**不透明等效色**（深 #2c2c2c/浅 #d4d4d4）——用户截图测色（48/44/64）定位出半透明叠加问题
- **空表**: 行高 ≤ 数据行（删旧 `.manage-empty-row td{padding:var(--space-xl)}` 覆盖规则——**文件后部规则优先**导致前部修改无效）；"暂无数据"居左（不同表合并列宽不同，居中位置不一致）
- **列名**: 头像列 label ''（不显示"头像"）；展示名列 label '名称'（用户统称"名称"）；右键菜单覆盖滚动容器空白区域（无"该列自适应"项）
- **NPE 修复**: ①`AccOpsProvider.toSwProvider().updateSwAccData` 从 map 取 **value**（空串）→ 改取 **key**（共存分支写错账号导致读回 null）；②`SwAccountOps.ensureCoexistAccFormatted` 的 `Map.of("linked_acc", null)`（Map.of 禁 null，教训 #50）→ HashMap
- **验证**: headless Edge 实测（滚动条不随内容滚动/显示条件/高度链列不拉伸）、node --check、gradle compileJava、运行日志无 JS 错误无维护失败

### 三、规则文件
- 项目 `CLAUDE.md` → `AGENTS.md`（git mv，DSH 与 Claude Code 通用约定）
- 全局规则 → `~/.dsh/AGENTS.md`（DSH 全局仅认此名；从 `~/.claude/CLAUDE.md` 拷贝，含提交先行/SDK 路径/打包流程/时间戳规则）
- DSH 规则机制: 项目级候选 `["AGENTS.md","CLAUDE.md"]`、本地级 `AGENTS.local.md`/`CLAUDE.local.md`、全局 `$DSH_HOME/AGENTS.md`；`dsh-agent-instructions` 插件实时 watch 注入

