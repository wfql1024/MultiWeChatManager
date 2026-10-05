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


---

## 远程配置加密发布工具（2026-10-04）

### 一、需求与参照
- 参照 `legacy_python/scripts/encrypt_data.py`（注释掉的 v3~v9 旧版本未移植），用 Java 重写；加密 `scripts/original_remote_global_v2.json`、`original_remote_sw_v10.json` → `remote_configs/`
- 算法: `key.ljust(16)[:16]` → AES/CBC/PKCS5Padding + 随机 16 字节 IV → `base64(IV + ciphertext) + " " + key`

### 二、结构决策（用户提出"脚本区不入 classpath 怪怪的"）
- 采纳 `src/tools` 独立源集 + `JavaExec` 任务：工具复用 `CryptoUtils`（消除加密逻辑双份这一真实风险），且不进应用产物
- 已删除最初的 `scripts/EncryptData.java` 单文件版（正是"双份实现"要避免的形态）

### 三、兼容性验证（关键证据）
- 用 Java 解密 `legacy_python/remote_configs/remote_global_v1`、`remote_sw_v9`（Python 产出）→ LF 归一化后与源 JSON 逐字符一致
- Java 加密产物字节数 = Python 版（48,657 / 170,429）
- 发现 v2/v10 与 v1/v9 **内容完全相同**（MD5 一致），本次发布实为版本号提升

### 四、踩坑
- 测试里用"补齐后的 key（尾部带空格）"构造密文会失败：格式按**最后一个空格**切分，key 不能带尾随空格（线上 key 为 15 随机字符 + `=`，天然满足）
- `Path.of(".").toAbsolutePath()` 不会规范化 `.`，`getParent()` 会返回自身 → 输出目录跑到 `scripts/` 下；需 `.normalize()`

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

---

# 开发日志（自 AGENTS.md 迁入：原第九节 + 第十二~二十九节，2026-10-05）

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
---

## 二十、无效账号并入 + 原生程序表 + 名称清洗（2026-10-04）

- **名称列"下划线"根因**: 不是 CSS，而是**账号 ID 里的下划线字符**——SwAccData 里这些账号没有 remark/nickname/alias，名称直接回退成账号 ID（`wxid_5daddxikoccs22`、`wxid_h5m0aq1uvr2f22_32ac`）；换成等宽字体后 `_` 又宽又靠下，看起来就像给名字加了下划线
  - 修复（仅显示层）: `main.js` 新增 `cleanDisplayName(name, idCandidates)`——**当名称恰好等于账号 ID 时去掉下划线**；ID 列仍显示原始 ID，用户自己填的备注/昵称/平台内ID 不动；`AccountTable.onAccountChanged` 里的 `display_name` 定向更新也做同样处理
- **无效账号不再单列一张表**: 无效账号 = `SwAccData` 全部账号 − 原生账号 − 共存账号，按自身类型并入原生/共存表
  - 类型判定 `isCoexistAccount(acc, id)`: SwAccData 节点带 `linked_acc` 字段（`ensureCoexistAccFormatted` 会补齐）→ 共存；兜底按 `id` 是否 `.exe` 结尾
  - 行上打 `invalid: true` → 整行灰字（`tr.invalid-row`）、名称右边加"失效"标签、**永远置底**
  - `index.html` 删除 `#acc-table-invalid-acc` 容器；`TABLE_COLUMNS.invalid` 删除；四表 → 三表
- **置底分组**: `_sortAccounts` 先按排序字段排，再用稳定排序按 `rank` 分组——`invalid` = 2（最底）、`hidden` = 1（次底）、其余 0
- **原生程序表**: 数据源 = 平台 `inst_path` 指向的那个 exe
  - 列: 名称(必选)/版本(**必选，必须显示**)/路径(默认不显示)——原"状态"列删除
  - 新增桥方法 `JsBridge.getSwProgramData(swId)` → `{name, path, version}`；版本取 exe 文件版本（`SwVersionHelper.calcSwVer`，取不到回退补丁 DLL 版本）
  - **旧列配置作废规则**: `_loadColumnPrefs` 增加"陈旧列名"检查——若持久化配置里出现当前列定义中不存在的列名（如被删掉的 `status`），整份列配置作废回默认值（否则会沿用旧的 path 显示与 58px 列宽）
- **隐藏状态可见化**: 悬浮按钮文案 `已隐藏/隐藏` → **`显示/隐藏`**（title 同步为 `显示账号/隐藏账号`），并在名称右边紧挨位置加"隐藏"标签；点按钮后整表重渲染，让隐藏行立即落到"次置底"位置
---

## 二十一、名称列横线真正根因 + 程序表头像 + 标签前缀（2026-10-05）

- **名称列"下划线/分割线"真正根因**: `td` 自身被设成 `display: flex` → 它**不再是 table-cell**，浏览器插入匿名 table-cell 包住它，于是 `td` 自己的 `padding`/`border-bottom` 变成画在**内层盒子**上 → 名称列的底边与其它列错位，看起来就是名称内容下面多了一条横线（其它列是普通 td，所以只有名称列有）
  - **实测证据**（项目同款 JavaFX WebView 17.0.2，见下方验证技巧）:
    - 旧写法 `td{display:flex}`: nameTd `top=82.0 h=34.0 bottom=116.0`，同排 idTd `top=81.5 h=45.0 bottom=126.5` → 名称格比同行矮 11px、底边错位 10.5px
    - 新写法（td 保持 table-cell）: 两格完全一致 `top=194.5 h=45.0 bottom=239.5`
  - 修法: `td.manage-nickname-cell` 不再设 flex，flex 移到内层 `.manage-nickname-inner`
- **悬浮按钮不再占位**: `.manage-row-quick-actions` 改为 `position:absolute; right:0; top:50%` + 悬浮时 `display:inline-flex`（默认 `display:none`）——脱离文档流，悬浮出现时不挤压/位移名称文字，也不预留宽度；"调至合适宽度"仍按用户澄清额外加 `QUICK_ACTIONS_WIDTH`
- **状态标签改成名称前缀**: `.manage-name-tag`（统一类，便于整组重画）+ `.manage-invalid-tag` / `.manage-disabled-tag` / `.manage-hidden-tag`，固定顺序 **失效 → 禁用 → 隐藏**，放在名称前（如 `失效 吾峰起浪`）；只作视觉前缀，**排序仍按 `display_name` 数据**，标签不参与排序
- **原生程序表加头像列**: 显示程序图标——复用侧栏的 `iconCache[swId]`（侧栏已用 `JFC.bridge.extractExeIcon` 提取），未命中则现场提取；行高与账号表一致（同为 32px 头像列；`.manage-account-table tbody tr[data-acc-id] { height: 44px }` 作兜底最小高度）

### 验证技巧：不打扰用户地校验 WebView 里的真实布局（本轮新增）

JavaFX WebView 与 Chromium 的布局细节不同，**要确认 WebView 里的实际几何/样式，就用项目同款 JavaFX WebView 离屏渲染**：

1. 生成一个只含目标 DOM + 项目 CSS 的临时 HTML（CSS 直接内联进 `<style>`，避免 file:// 相对路径问题）
2. 写个小 `Application`：`WebView` 放进 `Scene`，`stage.setX(-4000); setY(-4000); show()`（屏幕外，用户看不到），`eng.executeScript("... getBoundingClientRect()/getComputedStyle ...")` 把结果 `System.out.println` 出来
3. 运行（**注意两个坑**）:
   - `javac` 必须加 `-encoding UTF-8`，否则中文注释按 GBK 解析报错
   - `--module-path` 要带上 `javafx-base/graphics/controls/media/web` 的 **win** jar（`javafx.web` 依赖 `javafx.media`）
   ```bash
   javac -encoding UTF-8 --module-path "<fx win jars>" --add-modules javafx.controls,javafx.web NickCheck.java
   java  --module-path "<fx win jars>" --add-modules javafx.controls,javafx.web -cp . NickCheck
   ```
4. 校验完删除临时文件（放在 `build/` 下，gitignore 已覆盖）
---

## 二十二、高清图标 + 悬浮按钮边框 + 把手宽度 + 收起禁拖（2026-10-05）

- **程序图标/左栏图标模糊的根因**: `FileSystemView.getSystemIcon()` 在 Windows 上只给 **16x16** 小图标，渲染到 22px（左栏）/32px（列表）被放大 → 模糊
  - 真正的 32x32 大图标要经 `sun.awt.shell.ShellFolder.getIcon(true)`，但有两道坎：
    1. **模块导出**: 需 `--add-exports java.desktop/sun.awt.shell=ALL-UNNAMED`（此前只导出了 `javafx.web/com.sun.javafx.webkit`）→ 反射被拒 → 一直退回 16px
    2. **惰性图片**: 该 Image 的 `getWidth(null)` 返回 **-1**，旧代码 `width >= 8` 判断失败 → 即使能反射也拿不到。用 `new ImageIcon(img)` 包一层可触发同步加载拿到真实尺寸
  - 修复: `JsBridge.extractIconFromFile` 改为**三种方案各取候选、选尺寸最大者**（`pickBiggerIcon` + `iconSide`）；`imageToBase64DataUrl` 上限 64→**256**（保持宽高比）
  - 实测（`--add-exports` 下）: Weixin/WeChat/QQ 的 exe 均选出 **32px**（改前 16px），PNG data URL 约 1.3–1.8KB；32px 正好 1:1 用于列表头像列，左栏 22px 为降采样 ✓
  - 同步在 `build.gradle.kts`（`applicationDefaultJvmArgs` + `run` jvmArgs）与 `scripts/package-exe.bat`（两处 `--java-options`）加上该导出；反射被拒时只是回退 16px，不会崩
- **悬浮按钮上下边框消失**: `.manage-nickname-inner` 之前有 `overflow: hidden`，而按钮改为绝对定位后不再贡献高度 → 内层盒只有文字行高（~21px）< 按钮高度（~22px）→ **上下边框被裁掉**。修复：内层去掉 `overflow: hidden`（名称截断本来就由 `.dn-text` 自己负责）+ `min-height: 22px`
- **把手宽度随窗口变化**: 把手 SVG 是 `width:100%` + `preserveAspectRatio="none"`，viewBox 宽度必须与元素宽度一致；而 `initHandleSvg()` 只在切换平台/展开收起时调用，**窗口 resize 时没调用** → viewBox 停留在旧宽度 → 把手被非等比拉伸/压缩（点一次把手触发 `initHandleSvg` 才恢复）。修复：`initHeightDrag` 里注册 `window.resize → initHandleSvg()`，并让 `initHandleSvg` **每次都重算 path d**（不再只在 d 为空时设置）
- **收起状态禁止拖动底部分割线**: 收起时面板高度为 0，拖动会瞬间跳到最小高度、与鼠标脱节。修复：`onDown` 里若 `panel.classList.contains('collapsed')` 直接返回；并用 `syncHandleDragCursor()` 把两个拖动区的光标切成 `default`（展开时 `ns-resize`），在 `applyCurtainState` 与初始化时同步
---

## 二十三、平台图标 64x64 + PNG 缓存 + 侧栏/标签/记住平台（2026-10-05）

- **图标升级到 64x64（关键发现）**: `FileSystemView.getSystemIcon(File, int w, int h)` 在 Windows 上**支持任意尺寸**（实测 48/64/128/256 全部可用），是公开 API、不需要 `--add-exports` —— 比之前"取系统大图标 32x32"更容易也更清晰
- **新增桥方法 `JsBridge.getSwIcon(swId)`**: 图标缓存到 **`{用户数据目录}/{swId}/{swId}.png`**（如 `Weixin/Weixin.png`，与老 `SwAccountOps.getSwLogo` 的路径约定一致）
  - 有缓存图且平台软件路径（`inst_path`）未变 → 直接用缓存图，不重复提取
  - 缺图，或 `inst_path` 与记录的 `icon_src_path` 不一致（用户改了软件路径）→ 重新按 **64x64** 提取并覆盖缓存，同时把 `icon_src_path` 写回 `LocalSwConfig`
  - 提取失败 → **什么都不做**，保留原图继续使用（无图时返回空串，前端回退文字图标）
  - 左栏与"原生程序"表头像列都走它（同一份缓存）；实测 Weixin/QQ 的 exe 均得到 64x64、300+ 颜色、PNG 约 2–3KB
- **悬浮按钮改回文档流内**: 悬浮显示时**挤压名称文字**、名称自动以 `…` 结尾（`flex-shrink: 0` 保证按钮不被压缩）；背景改不透明（`--bg-card`；"已隐藏"态用不透明等效色新变量 `--qa-on-bg`，深 `#2d3a48` / 浅 `#e0edf9`）—— 之前 `background: transparent` + `--color-primary-light` 看起来发虚/半透明
- **状态标签放大**: `.manage-name-tag` 字号 `--font-xs`(13px) = 列表正文 14px − 1；`padding: 1px 8px` + `border-radius: 6px` + `line-height: 1.4`，圆角矩形完整包住文字
- **最左栏"卡住不收"兜底**: 点击平台后账号列表加载会卡顿，期间的 `mouseleave` 可能被吞掉 → 侧栏保持展开。新增两层兜底：
  1. **文档级 `mousemove`**（capture）：指针在侧栏外移动且侧栏已展开 → 立即 `collapse()`
  2. **展开期间 400ms 定时校验**：`document.elementFromPoint(lastX, lastY)` 不在侧栏内 → `collapse()`
  3. 抽出统一的 `collapse()` 供 mouseleave/兜底共用
- **移除最左栏"统计"按钮**: `index.html` 的 `#nav-sidebar` 底部只留"设置"（`#page-statistics` 占位页与 `icons.js` 的 statistics 图标资源保留备用）
- **记住最后显示的平台**: 切换平台时 `saveGlobalConfig({last_sw_id})`（存 `LocalGlobalConfig.json`）；启动时 `loadPlatformListInternal` 读到该字段且平台仍存在 → 直接 `selectPlatform(lastSwId)`，不再停在"点击平台"占位页
---

## 二十四、设置区域高度/展开态全局统一 + 若干修正（2026-10-05）

### 设置区域"窗帘"：由 per-platform 改为全局统一（"违背祖宗"的决定）

> **改造前的实现与经验结晶已完整存档** → [`MEMORY/ARCHIVE_settings_curtain_animation.md`](MEMORY/ARCHIVE_settings_curtain_animation.md)（含逐字代码 + 13 条踩坑结论）

- **新规则**:
  - **高度**与**展开/收起态**都只存一份（`LocalGlobalConfig.json` 的 `settings_height` / `settings_expanded`），所有平台共用；任一平台拖动高度、点击把手都会写回同一记录
  - **例外（未启用平台）**: 三个路径项（`inst_path`/`data_dir`/`dll_dir`）**未填全**的平台视为"未启用" → **强制展开**，且它的展开/收起**不写全局记录**（`isSwSettingsComplete()` 把关）；高度拖动不受此限制，照常同步全局
  - 设置填全后即变"启用"，此时展开/收起才影响所有平台
- **一次性迁移**: 全局无高度记录时，沿用旧版当前平台的 `LocalSwConfig.<sw>.settings_height` 作为初始全局高度
- **跨平台丝滑动画仍保留且更有用**: 全局处于收起态时切到"未启用平台"会强制展开，此时正是靠 `animatePanelHeight(targetH, null, _prevHeight)`（`_prevHeight` 为上一平台的实际高度，收起时≈0）从 0 平滑涨到目标高度
- 实现要点: `loadCurtainGlobal(swId)` / `saveCurtainGlobalHeight(h)` / `saveCurtainGlobalExpanded(expand)` / `isSwSettingsComplete(swId)`；切换平台时 `shouldExpand = 启用 ? !全局collapsed : true`，目标高度一律 `curtain.height`
- 手动展开的目标高度改为**以全局记录为准**（而不是 `scrollHeight`），保证"拖过一次的高度"对所有平台生效

### 本轮其他修正

- **图标提取必须先确认是"程序"**: `inst_path` 存成目录的平台（如 WeChat）会被当文件夹取图标 → `getSwIcon` 现在要求 `isFile() && .exe`；若是目录则尝试拼远程配置的 `executable`（`WeChat.exe` 之类），拼不到就跳过（保留原图/无图）
- **分割线光标**: 原实现把光标写在拖动 rect 的**内联 style** 上、且 `syncHandleDragCursor()` 在 `applyCurtainState` **改类之前**调用 → 状态错位（收起/展开都可能显示同一种光标）。改为 **CSS 驱动**：移除内联光标，`body.curtain-collapsed` 时拖动区 `cursor: default`（否则 `ns-resize`），并用 **MutationObserver 监听面板 `collapsed` 类**同步 body 类——面板状态在多处被改动也不会漏
- **撤销名称下划线清洗**: 用户澄清当初要的是"去掉分割线"，"下划线"是口误 → 删除 `cleanDisplayName`（`main.js` + `account-table.js` 的定向更新），名称恢复原样显示
---

## 二十五、单一职责修正：图标只认程序、未启用只读绿框、高度漂移根治（2026-10-05）

- **图标提取（单一职责）**: `getSwIcon` 只做一件事——看"软件路径"存的值**是不是程序**（`isFile() && .exe`）；不是就什么都不做。**删掉了**上一轮加的"目录 + 远程 executable 拼接"逻辑——"目录里该是哪个 exe"属于**路径探测流程**的职责，不该由图标提取越界处理
- **"未启用"判定改为只读绿框（单一职责）**: 不再自己判断"三个路径填没填全"，而是**读取三个路径项的绿框状态**
  - 绿框由路径检查流程（`validatePathInput` → `JFC.bridge.checkPath`）判定：现在除了改边框色，还写入 `input-ok` / `input-warn` / `input-error` 类，并把结果记到 `swPathGreen[swId][key]`
  - 窗帘侧只读：`isSwSettingsComplete(swId)` 遍历 `PATH_FIELD_KEYS = ['inst_path','data_dir','dll_dir']`，三项都 `true` 才算启用
  - **时序兜底**: 进入平台时检查结果尚未回来 → 先按"启用"处理；结果回来后若发现未启用，由 `enforceCurtainForCompleteness()` 补一次强制展开（带高度动画）
- **"拖完高度后第一次切换平台总会变高一点点"根因**: 两套内容区高度算法不一致——
  - 拖动中用 `content.maxHeight = 面板高 - 20`；而 `animatePanelHeight` 收尾用 `content.maxHeight = 面板高` → 切换平台后内容区松了 20px，面板就"变高一点点"，再切一次因为两边都稳定了所以看不出变化
  - 手动展开的动画收尾还有 `panel.style.maxHeight = ''`（清空上限 → 按自然内容高度渲染），与记录高度又不同
  - **修复**: 新增 `applyPanelHeight(panelH)` 作为唯一入口（面板 `max-height = H` 且 `content.max-height = H - 20`，成对设置），拖动、动画收尾、手动展开、`applyCurtainState(true)` 全部改走它；另外 `_prevHeight` 改取**语义高度**（`parseInt(panel.style.maxHeight)`）而不是含 padding/border 的渲染高度，作为动画起点不再多算一截
---

## 二十六、设置区域切换时"闪一下"的真正根因：写死的 20px 偏移（2026-10-05）

- **现象**（用户描述）: 跨平台切换时，高度不变（100→100）会"没动画但闪到 ~120 再跳回 100"；高度变化（100→300）会"动画到 ~320 再闪回 300"
- **排查方式**: 用项目同款 JavaFX WebView 离屏渲染一个**复刻面板结构 + 真实 CSS** 的页面，逐 25ms 采样面板渲染高度，对比四种方案的"高度轨迹"：

| 方案 | 100→100 | 100→300 | 内容可滚动 |
|---|---|---|---|
| V0 现状（内容区 `面板高 - 20`） | `100 -> 80` ✗ 闪 | `... -> 300 -> 280` ✗ 冲到 300 再弹回 280 | true |
| V1 面板 border-box + 内容不设上限 | 100 ✓ | 100 → … → 300 ✓ | **false** ✗ 滚动条再也不出现 |
| V2 实测 chrome 补偿 | 100 ✓ | 100 → 300（无中间帧，不丝滑）✗ | true |
| **V3 面板与内容区同值 + 动画期间内容区解除上限** | **100 ✓** | **100→122→…→300 ✓ 精确收在 300** | **true ✓** |

- **根因**: 内容区被写死 `max-height = 面板高 - 20`（所谓"预留"），而动画期间内容区是 `max-height:none` → 动画能涨到 `H`，停下来却回落到 `H - 20` → 切换平台就表现为"闪一下"或"冲过头再弹回"。**写死的偏移量制造了两套不一致的高度语义**（记录值 = 渲染值 + 20）
- **修复（无任何魔法数字）**: `applyPanelHeight(h)` 给**面板与内容区同一个值**；动画期间内容区 `max-height:none`（否则涨不上去）保留；滚动条靠内容区自己的 `overflow-y:auto` 照常出现（V3 实测 `scrollHeight > clientHeight` 为 true）
- **教训**: 面板与内容区这类"父子都被同一高度约束"的场景，**必须同值**；任何 `- N` 的预留都会在"动画/静态"两条路径上产生不一致。要补偿也应实测（V2 的 chrome 实测值是 0，说明当初那个 20 纯属臆测）
---

## 二十七、LocalGlobalConfig 冗余节点清理 + 账号区滚动自动收起（2026-10-05）

### 一、配置节点审计（实测 storage/4.0.0.7000/DevUserFiles/LocalGlobalConfig.json）

清理前 11 个顶层节点 → 清理后 **5 个**：`theme` / `account_columns` / `last_sw_id` / `settings_height` / `settings_expanded`

| 节点 | 判定 | 依据 / 处理 |
|---|---|---|
| `manage_settings_collapsed`（各平台收起态 map） | ✗ 冗余 | 早期 Python 移植遗留；代码里只剩一个**从未被引用**的常量 → 连常量一起删掉 |
| `manage_settings_height` | ✗ 冗余 | 更早的"全局高度"记录，已被 `settings_height` 取代；代码零引用 |
| `account_columns.<表id>`（扁平键，出现 3~4 份） | ✗ 冗余 | 历史 bug：保存写成了扁平键，读取端只认嵌套结构 → 读取端兼容分支一并删除（仅删代码会留脏数据，故补一次性清理） |
| `account_columns.visible` / `.width` | ✗ 冗余 | 更早版本把单表配置直接挂在 `account_columns` 下；无任何读取代码 → 首次启动清理 + `_saveColumnPrefs` 保存时顺手剔除（防回归） |
| `account_columns.invalid_acc` | ✗ 冗余 | 该表已删除（无效账号并入原生/共存表） |
| `account_columns.origin_prog` | ✗ 冗余 | 内含已删除的 `status` 列 → 代码本就会按"陈旧列名"作废该配置（等于没在用），直接删除 |
| `theme` / `account_columns.{origin_acc,coexist_acc}` / `last_sw_id` / `settings_height` / `settings_expanded` | ✓ 在用 | 保留 |

- **删除能力**: `JsBridge.saveGlobalConfig` 增加「**JSON null = 删除该字段**」语义（`ConfigManager.updateGlobalConfig` 对 null 走 `remove`），前端 `cleanLegacyGlobalConfig()` 在 `init()` 里跑一次即完成清理（表实例就绪后再跑，才能判定哪些表还活着）
- **代码清理**: `SwCoreConstants.MANAGE_SETTINGS_COLLAPSED` 删除；`account-table.js` 去掉扁平键兼容读取；保存时剔除 `account_columns` 下的 `visible`/`width`
- **数据清理**: 两份实际文件（`D:\SpaceDev\MyProj\JhiFengMultiChat\storage\...` 与项目内 `storage\...`）已就地清理，备份为 `LocalGlobalConfig.json.bak-20261005`

### 二、账号区域"有效滚动"→ 自动收起设置区域

- **触发**: 在账号区域（`.account-area-inner`）滚动滚轮，且**确实滚动了内容** → 自动收起设置区域
- **"有效"判定**: 滚轮事件里记下 `scrollTop`，下一轮事件循环比对是否变化 —— 没有纵向滚动条、或已滚到边界（`scrollTop` 不变）都算**无效滚动**，不收起
- **记录规则**: 收起统一走 `toggleSettingsPanel(false)` → 已**启用**平台会写全局记录（所有平台一起收起）；**未启用**（设置不完备）平台只本地收起、**不记录**（复用第二十五节的绿框 gating，无需新分支）
---

## 二十八、"刚进平台时莫名从 0 涨上来"的根因：本地收起残影被当成动画起点（2026-10-05）

- **现象**（偶发、只在启动初期）：记录为展开、跨平台高度相同时，进入平台会看到面板"从 0（但不完全是从 0）涨到目标高度"；每个平台都点开过一遍后就不再出现
- **实测（复刻面板 + 真实 CSS 的离屏 WebView 采样，三种起点）**:
  | 场景 | 高度轨迹 |
  |---|---|
  | A 首次进入（内容先空后填，起点=180） | `16 -> 180 -> 200` |
  | B 已稳定（起点=实际渲染高度 200） | `200`（无动画） |
  | **C 起点=0（面板当时确实是收起的）** | **`0 -> 20 -> 65 -> 131 -> 159 -> 178 -> 190 -> 197 -> 200`** ← 与用户描述完全一致 |
- **根因**: 未启用平台的收起按 4.2 **不写全局记录**，但**面板元素的 inline 高度确实变成了 0**。切到下一个平台时：
  - 全局记录仍是"展开" ⇒ `shouldExpand = true`（符合预期，面板应该就是展开的）
  - 而动画起点取的是面板当前高度 ⇒ **0** ⇒ 于是走了 `0 -> 目标高度` 的动画（用户感知为"刚进页面莫名跳一段动画"）
  - "每个平台都点开过一遍就不再出现"的原因：首次访问会**自动探测路径** → 平台变"启用" → 不再有强制展开的平台 → 也就不会出现"只在本地收起"的残影
- **修复**（三条分支，各司其职）:
  1. **首次进入平台**（页面刚从"全部平台"占位切过来，面板从未按平台显示过）→ **直接落位**，不做动画（没有有意义的"上一个高度"）
  2. **上一个平台只是本地收起 + 全局记录仍是展开** → **直接落位**，避免假动画
  3. 其余情况照常动画：普通跨平台从上一个高度滑到目标高度；**全局收起 → 切到强制展开平台时仍从 0 平滑涨上来**（4.3 要的效果，保留）
  - 新增状态: `_prevWasCollapsed`（切换前那个平台是否收起）、`_panelShownOnce`（是否已按平台显示过一次）
---

## 二十九、设置区域"单一渲染依据"重构（2026-10-05）

- **背景（用户实测）**: 记录为"收起"时关闭程序 → 重启后**记录是收起、渲染却是展开**；切换平台时两种规则互相拉扯，切几个平台后才统一。
  根因：面板的高度/类名有**多条写入路径**（切换平台、点把手、拖动、完备性回调、强制展开…），各自读不同的状态，导致"记录"与"渲染"长期不一致
- **重构原则（用户提出，已落地）**: **渲染的唯一依据是"期望状态"，状态变更一律先落到事实来源，再统一渲染**
  - `desiredCurtainState(swId)`：**唯一推导处** = ① 全局记录（`settings_height` / `settings_expanded`）② 例外：未启用平台恒为展开，其本地展开/收起记在 `forcedLocalState`（不写记录，4.2）
  - `applyCurtainRender()`：**唯一 DOM 写入点**（类名/箭头/高度/动画都在这里决定）；状态与上一帧一致时直接返回（不重放动画）
  - `setCurtainExpanded(expand)`：启用平台 → 先 `saveCurtainGlobalExpanded` 写记录；未启用平台 → 只改 `forcedLocalState`；然后统一渲染
  - `setCurtainHeight(h)`：写记录 + 立即渲染（拖动结束调用）
  - `enforceCurtainForCompleteness()`：完备性变化后只是**再调一次渲染**（幂等）
  - `_lastRender` 记录"上一帧真实渲染状态"（是否显示过 / 展开 / 是否来自记录 / 高度），动画起点与"是否做动画"都由它推导，取代原先散落的 `_prevHeight` / `_prevWasCollapsed` / `_panelShownOnce`
- **消除闪烁**: 进入平台时**先同步跑一遍三个路径的绿框检查**（`checkPath` 是同步桥调用），让"是否启用"在渲染前就确定，避免"先按记录收起渲染、200ms 后检查回来又强制展开"
- **平台由未启用变为启用**: `setPathGreen` 里清掉该平台的 `forcedLocalState` → 此后完全跟随全局记录（不再有历史残影）
- 顺带删除：旧的 `applyCurtainState()`（及其手写展开/收起动画）与 `toggleSettingsPanel()` 里那套独立动画，全并到 `applyCurtainRender()` + `animatePanelHeight()`

---

## 三十、彻底移除"借标题当提示条"（flashTitle）（2026-10-05）

- **背景**: 平台标题区 `#manage-detail-title` 被当成"通知条"用：`flashTitle()` 临时把标题文字换成"已隐藏 / 已显示 / 已删除 / 尺寸已获取"之类的提示，过一会儿再换回平台名 → 一个控件承担了两种语义，且 `main.js` 与 `account-table.js` **各自实现了一份** `flashTitle()`
- **先排查写入点（再动手删，避免漏删/多删）**:
  - `main.js setTitleDisplay()`：平台进入 / 保存备注 / 标题输入框回车 → **唯一正当写入**，保留
  - `main.js flashTitle()`：仅用于"获取登录窗口尺寸"的成败提示
  - `account-table.js flashTitle()`：批量隐藏/显示、批量删除、单行删除成功/失败
- **改动**: 删掉两份 `flashTitle()` 实现 + **全部 8 处调用**（`account-table.js` 5 处：单行显示/隐藏、批量隐藏/显示、批量删除、单行删除成功、单行删除失败；`main.js` 3 处：取尺寸的三种结果）；`#manage-detail-title` 之后只剩 `setTitleDisplay()` 与标题输入框的 keydown/blur 绑定会写它
- **为什么这么做（用户裁定）**: 状态变化优先靠**就地可见的变化**表达 —— 按钮文案（隐藏/显示）、行内标签（失效/禁用/隐藏）、行置底、行消失；真要提示也应放在**该功能所属区域内部**，不要跨区域"借用"别的控件
- **副作用（明确接受）**: 删除失败、取尺寸失败等错误路径**不再有任何提示**（行消失 / 字段保持空白即为结果）；将来若需要反馈，另建非标题的提示渠道（"toast 通道"目前仍在 `TODOS.MD` 的待办里）

---

## 三十一、刷新入口 + 页面进度条 + 平台图标 SVG 化 + 当前平台单击刷新策略（2026-10-05 晚）

- **标题栏刷新按钮（Java 侧自绘 SVG）**: `MainWindow.makeSvgTitleBtn(extraClass, pathData...)` —— 用 SVG `Path` 拼图标，`TITLE_ICON_PX = 16`、`scale = TITLE_ICON_PX / 24.0`（按 24×24 设计稿缩放）；刷新图标取 **Lucide `rotate-cw`**（MIT，stroke-width 2、圆头圆角），由 `btnRefresh` 持有
- **冷却（防连点）**: `MainWindow.REFRESH_COOLDOWN_MS = 2000`，点击后 `btnRefresh.setDisable(true)` + `PauseTransition(Duration.millis(REFRESH_COOLDOWN_MS))` 置灰 2 秒；`refreshCurrentPage()` 里 `executeScript` 求值 `(JFC.router && JFC.router.refresh) ? JFC.router.refresh() : false`
- **真正的冷却门在前端**: `app.js` 的 `JFC.router.refresh()` 内判 `if (now - lastRefreshAt < REFRESH_COOLDOWN_MS) return false;` —— 返回 `true/false` 表示"这次刷新是否真的执行了"；**Java 侧那个 2 秒只管按钮置灰**，两边同一语义、互不依赖（Java 不认识前端的执行结果，也不该认识）
- **`JFC.router`（单页路由，本轮定稿）**: `navigate(page)` / `refresh()` / `current()` / `detectActivePage()` / `init()`；`detectActivePage()` 从 DOM 里实际可见的页面反推当前页（不靠自己记的变量，避免与实际显示漂移），`init()` 时以它为准
- **页面进度条**: `.page-progress`（`app.js` 的 `JFC.progress`）—— 页面"开始加载数据"时 `show()`、装载完 `hide()`；为避免一闪而过设 `MIN_MS = 400`，收起前 `wait = Math.max(0, MIN_MS - (Date.now() - shownAt))`
- **平台图标 PNG → SVG**: 默认平台图标从"PNG 位图"改为**内联 SVG**（`getDefaultPlatformIcon(swId)`：`<rect x=3 y=3 width=18 height=18 rx=4>` + `<text>` 首字母，`viewBox="0 0 24 24"`）→ 任意缩放下不糊，也不依赖缓存文件是否存在
- **当前平台的点击策略（用户裁定）**: 点**别的**平台 = 立即切换；点**当前**平台 = 单击刷新；当前平台的双击/多击一律不响应（路径预留）。实现用 `MULTI_CLICK_GUARD_MS = 250`：单击刷新要等 250ms 确认没有后续点击才执行（Windows 双击间隔量级）
- **验证**: `build/_probe/RouterProbe.java`（路由跳转 / 冷却门 / `current()` / `detectActivePage()`）、`ClickPolicyProbe.java`（单击与双击的时序判定）、`IconProbe.java`（SVG 图标渲染）

---

## 三十二、账号管理功能（行内/批量操作 + 就地编辑 + 快捷键录入定稿）（2026-10-05 晚）

- **一个必须先解决的前提（离屏实测）**: JavaFX WebView 里 **`window.confirm()` 恒返回 `false`**（没装 confirm handler 时既不弹窗也不返回 true）、`alert()` 是空操作 → 之前所有"删除账号"的确认**永远静默取消**，用户连提示都看不到 ✗
- **自建弹窗 `JFC.modal`**（`app.js`）: `confirm({title, message, okText, danger}, onResult)` 与 `custom({title, bodyHtml, center, actions:[{text, cls, onClick}]})`；键盘也必须走 `JFC.keys.keyCodeOf()`（本 WebView 的 `event.key` 为空串），Esc/Enter 在里面处理
- **行内 + 批量按钮**: 名称列右端悬浮按钮「隐藏/显示」「重置」（**失效行**再加「删除」）；表格标题栏批量按钮「隐藏」「重置」「删除」+「取消」（`data-batch="toggle-hidden|reset|delete|cancel"`）；批量栏在无选中项时由 `toggle-hidden` 类整体隐藏
- **名称列就地编辑（remark）**: 点名称 → 该格换成 `<input class="name-input">`，预填 `acc.remark`；**留空时用灰字 placeholder 显示"不填会显示什么"** = `display_name_auto`（= 名称回退链去掉 remark 的结果，与提交后真正显示的名称**同一份输入推导**，不是另写一套规则）；Enter / 点格外提交，Esc 取消；空白提交 = 清空备注 → 名称回退到自动识别结果
- **平台标题输入框**: `setTitleDisplay(name, fallbackName)` 同时设"值"与"灰字提示"（fallback = 远程 alias 或 swId）→ 备注留空时也能看到会显示成什么
- **快捷键录入定稿（用户逐条裁定）**: **松手即确认**（所有键松开的那一刻提交并退出输入框，此前是"点别处才提交"，点别处若顺手选中行会触发重渲染 → 未提交的录入随 DOM 一起丢）；**无效即回退**（只有修饰键如 Alt+Shift、或普通键多于一个如 Alt+A+B → 恢复原键值，**不保存也不清空**）；**Backspace = 清空并退出**；Esc = 放弃；**Enter = 忽略**（不当热键，避免"回车确认"的习惯把热键改成 Enter）；**Tab 算普通键**（可录成 Tab）；预览 = 已按下的普通键 + 当时修饰键拼装（松键顺序不影响结果）
- **验证**: `build/_probe/RoundProbe.java` —— 真实 `index.html` + 桩桥 `StubBridge`（记录桥调用次数与最近一次 JSON）+ 逐 step 断言；覆盖"删除确认走自建弹窗""名称预填 / 灰字=回退名 / 空白提交已保存 / Esc 未保存""快捷键松手提交 / 无效回退 / Backspace 清空"等（62 条）

---

## 三十三、交互修复（编辑态卡住 / 点击落空）+ 自绘勾选框（2026-10-05 晚）

- **"点框外不退出编辑"的根因**: `if (ev.target.closest(cell)) return;` —— `closest()` **只接受选择器字符串**，传元素会抛 `SyntaxError`；而监听器里的异常不中断别的代码，只让**这一个处理器的第一行静默死掉** → "点击框外结束编辑"的逻辑**从来没生效过**。修法：`cell.contains(ev.target)`
- **"编辑后第一次点击落空"的根因**: 提交若在 document 的 `mousedown` 阶段直接 `render()`，用户这一下点击所在的元素会被换掉 → 后续 `click` 落空（表现为"点别处要按两次才生效"）。修法：同步只还原本格，**保存与整表重排延后一拍**（`setTimeout(…, 0)`）
- **"第二次点同一格没反应"的根因**: 单元格若"只重建本格内容"就一直存活，挂在它上面的 `stopPropagation` click 监听会**逐次累积** → 第 N 次进入编辑后，这个格子自己的点击被自己挡住（tbody 的委托收不到）。修法：不在单元格上挂这类监听，委托里判 `e.target.tagName === 'INPUT'` 就够了
- **切换编辑目标**: `this._editFinish = cancelEdit`（对外统一入口）—— 进入新编辑前先收尾上一个格子，且**收尾一律"取消并还原"**，绝不留输入框在页面上（此前会出现"编辑态卡住、改不动也退不出"）
- **自绘勾选框**: 现象 —— 勾选框会**先出现纯方形、随后才变圆角/主题色**（用户看到的"渲染异步"）；根因 —— 原生 `input[type=checkbox]` 在 JavaFX WebView 里**先画一帧原生外观再套 CSS**；修法 —— 别让原生控件承担视觉：`<label class="acc-check">` + **透明 input（只当状态载体，`opacity:0`）** + 自绘 `<span class="acc-check-box">`（边框/圆角/勾全自己画），从第一帧就是最终样子
- **验证**: `RoundProbe` 覆盖以上四条（点框外退编辑 / 点别处一次生效 / 同格二次点击 / 编辑态唯一）+ `CheckboxProbe.java`（离屏像素统计确认自绘外观与点击命中）

---

## 三十四、程序表快捷键列 + 头像弹窗 + 版本号自动获取（2026-10-05 晚）

- **三张表的"快捷键"列**改为**非必显**（列头菜单可隐藏、默认显示），`TABLE_COLUMNS.program` **新增该列**（`defWidth: 110`）+ `initAccountTables` 里 `enableHotkey: true`
  - 账号表：快捷键存 `SwAccData.<sw>.<acc>.hotkey`
  - **原生程序表 = 平台自身**（没有账号节点）→ 存 `LocalSwConfig.<sw>.hotkey`（新增 `SwCoreConstants.LocalSettingKey.HOTKEY = "hotkey"`）；组件新增 `saveHotkey` 选项，由 `main.js savePlatformHotkey()` 注入
  - **为什么不能按 exe 路径往 SwAccData 建节点**: 那会留下一条"路径键"记录，且它不在 `getSwExistedAccounts` 列表里 → 被 `main.js` 判成**失效账号**，账号表里凭空多一行
- **头像弹窗**: 点列表头像 → `JFC.modal.custom()` 弹窗显示**原图**（`.avatar-preview-img` 180px）+「✎ 编辑」+「✕ 移除」
  - 编辑：`JsBridge.pickAccAvatar` → `FileChooser`（图片扩展名过滤器）→ 统一转 JPEG（白底 + `TYPE_INT_RGB`）写入 `{userData}/{sw}/{acc}/{acc}.jpg` 并清 `avatar_url` → 返回新 data URL，前端**就地刷新那一格**（不整表重渲染）
  - 移除：`JsBridge.removeAccAvatar` → 删本地头像文件 + 清 `avatar_url` → 前端重新拉取（回退到链接账号 / 网络头像 / 文字头像）
  - 版式：`JFC.modal.custom({center:true})` + CSS `.modal-card.center`（标题与按钮都居中）；顺带全局 `*:focus { outline: none; }`（用户要求"本项目不要浏览器默认的聚焦虚线框"，代价是 Tab 切换看不到焦点位置，已明确接受）
- **版本号：从"文件名正则"改为读 Windows 文件版本资源**
  - 现象：版本列长期空白
  - 根因：**迁移漏了旧行为** —— 老实现只从文件名抠版本（`WeChat_8.0.47.61.exe` 能抠、`WeChat.exe` 抠不到），而旧版 Python 一直用 `win32api.GetFileVersionInfo` 读**文件版本资源**
  - 改动：`SwVersionHelper.getFileVersion()` 先走 `getWindowsFileVersion()`（JNA `VersionUtil.getFileVersionInfo` 的固定信息 `dwFileVersionMS` / `dwFileVersionLS`，经 `formatFixedVersion(ms, ls)` 拼成四段）；**退化值**（形如 `x.0.0.0` 且 x ≥ 1000，由 `isPlausibleVersion()` 判定）时改用 `dwProductVersion`；都取不到再回退文件名解析
  - **实测 7 个真实 exe**: Weixin `4.1.15.13`、WXWork `5.0.2.6022`、WeChat `3.9.12.55`、QQ `9.7.25.29415`、TIM `3.5.1.22172`、QQNT `9.9.23.42086`、抖音聊天 fileVersion `29622.0.0.0`（垃圾值）→ **productVersion `1.1.32.0`**（正是退化值分支救回来的）
  - 验证：`VersionProbe.java`（直连 `getFileVersion` 对 7 个真实路径）+ `VersionPathProbe.java`（走平台路径链路的版本解析）
- **顺带**: 本轮把 `Map.of(…, null)` 的 **8 处必然 NPE** 扫掉（`Map.of` 不接受 null 值，外面套着 `try/catch` → 症状是"某些逻辑从来没生效"）：`AccOpsProvider.ensureCoexistAccFormatted`(×3)、`AccOperatorCore`（清 pid + has_mutex）、`AccInfoFuncCore.unlinkHwndOfAccount`、`AccInfoFuncCore.deleteAvatarForAcc`、`SwConfigAccessor.getSwSettingAsString`（`SwInfoFuncCore` / `SwOperatorCore` 两个调用方都受害）、`SwHexUtils`（空结果占位）

---

## 三十五、账号头像文字兜底改"名称末尾 4 个字符宽" + 中文字体/抗锯齿实测（2026-10-05 深夜）

- **需求**: 账号头像的兜底文字原来只取**首字符** → 改为取**名称末尾 4 个字符宽**（中文/全角一个字算 2 宽）
  - Java：`AvatarUtils.textAvatarLabel(name)` + `AvatarUtils.visualUnits(s)`；前端同规则 `JFC.text.tailUnits()` / `JFC.text.isWide()`（**同一规则两处实现，改一处必须同步另一处**）
  - 实测（`AvatarLabelProbe.java` 直连 Java 代码）：「极峰多聊测试」→「测试」、「张三wx」→「三wx」、「wxid_ab12cd」→「12cd」、「WeCha1」→「Cha1」、空 / null →「?」
  - 兜底用的**名称**：原生账号 = `getAccOriginDisplayName`（备注 > 昵称 > 平台内ID > ID）；共存账号 = 链接账号展示名
  - **只影响账号头像**：程序表 / 左栏平台图标的兜底仍取首字符（由 `avatarFallbackTail: !isProgram` 控制）
  - 4 个字符宽时 SVG 字号自动由 10 缩到 8（`textAvatarFontSize`），保证塞得进 18×18 方块
- **中文字体对照（用户要求"在不同处先用不同字体看看"）**: 表格列头 = 宋体 SimSun ｜ 表格内容 = 英文等宽 + 中文微软雅黑 ｜ 按钮 = 本机默认 `sans-serif` ｜ 其余区域 = 基线（微软雅黑优先）
- **结论（离屏像素实测，不是"我觉得"）**: **换字体解决不了"发虚"** —— 四个字体分区的**边缘对比度完全相同**（SimSun 51.3 / 等宽+雅黑 51.3 / 本机默认 51.3 / 雅黑基线 50.2），只有墨量（字重/字形）差异
  | 配置 | 边缘对比度 | 彩色边缘占比（LCD 特征） |
  |---|---|---|
  | 默认 | 51.3 | **97.0%** |
  | `-Dprism.lcdtext=true` | 51.3 | 97.0%（= 默认值，等于没改） |
  | **`-Dprism.lcdtext=false`** | **53.5** | **0.0%** |
  | `-Dprism.text=t2k` | 51.3 | 97.0% |
  → JavaFX（含 WebView 内文本）**默认就是 LCD 次像素抗锯齿**：深色底 + 中文复杂笔画会出现彩色条纹、观感"发糊"；`build.gradle.kts` 的 `run` 任务已加 **`-Dprism.lcdtext=false`** 作为试验开关（保留与否待用户比对后定）
- **可复用的排查手法**: `FontProbe.java`（5 个字体分区 × 4 种 JVM 开关的像素统计）；`FontIdProbe.java`（**字体身份鉴定**：离屏渲染同一个字比"**墨块数**" —— 同字号字重下 雅黑 175 / 宋体 146 / 等宽回退 131，差异足够大；像素指纹逐像素比对对字重、字号、亚像素位置过于敏感，容易得出"全不相同"的假结论）

---

## 三十六、勾选框"填满"真修 + 字号统一 14px（2026-10-05 深夜）

- **现象（用户三次描述、逐次逼近）**: "填充色没有填满，四个角还有小黑点" → 我先按"圆角太大"把 `border-radius` 从 4px → 2px → 0px 试了一遍，用户仍能看出问题
- **真正的根因（用户指出）**: 勾选态被写成了**两层几何** —— `background` 填 padding box（内圆角）+ `border` 当外圈（外圆角），**即使同色，圆角处也会露出两者之间的缝** → 看起来就是"中间的填充 + 周围的边框"，四角发黑
- **修复**: 勾选态改成**一整块填充** —— `background: var(--color-primary)` + `background-clip: border-box` + **`border-color: transparent`**（边框完全不参与画面）；尺寸/圆角沿用基类 = **16px（含 1px 边框，`box-sizing: border-box`）+ 4px 圆角**，与空框外沿完全一致
- **实测证据（`CheckboxProbe.java`）**: 填充 16px / 空框 16px、两者中心重合；**内部镂空 = 0**（形状内部"既非填充色也非勾色"的像素数）；轮廓与空框只差 **15/999** 像素（全是边缘抗锯齿）→ 确认"缝"没了
- **勾的位置**: `transform: translate(-50%, calc(-50% - 1.25px)) rotate(45deg)` —— 先用 `left/top:50%` + `translate(-50%,-50%)` 几何居中，实测"墨迹中心"仍偏下 **1.25px**（旋转 45° 的 L 形视觉重心低于几何中心），按实测值补偿，最终偏移 -0.25px
- **字号统一（用户定）**: `--fs-table: 14px` 用于 列头 / 表内 / 状态标签 / 悬浮按钮 / 批量按钮 /「已选 x 项」；**名称列 15px**（`--fs-name`，比其他列大 1 号）
- **⚠️ 本轮的重要教训（用户批评）**: 用户的 TOP 指令是"**如果**你没办法调试好，就当前状态让填充框边长 +1"—— 这是**条件兜底**，我却跳过"先真修"直接执行了兜底（把填充改成 17px + 左/上各外扩 0.5px），被指出"**说好的逐字呢？"如果"被你吃了吗**"。正确顺序：**先按指令里的目标做真正的修复 → 确实做不到才启用兜底 → 并在回复里说明"兜底未启用 / 为何启用"**。该兜底已在真修后撤销

---

## 三十七、三表名称列统一 + 原生程序名称链（2026-10-06 凌晨）

- **用户两个问题（先查代码再动手）**:
  1. "三张表不是有复用代码吗，为什么程序表名称列没和账号表统一？" → 查出来：组件层**本来就是同一个** `JFC.AccountTable`，是**列 key 不同**走了不同分支 —— 账号表 `key='display_name'` 落到专用名称单元格 `.manage-nickname-cell`；程序表 `key='name'` 落到"通用文本列"`.manage-text-cell`（不可编辑 / 2 级色 / 14px / 不加粗）
  2. "`_alias` 是干嘛的？不是能从远程配置获取吗？" → 查出来：它是**远程别称的内存缓存**（`swConfigData[sw]._alias = 远程 alias`），却被 `saveSwConfig(swId, JSON.stringify(swConfigData[swId]))` **一起写进了 `LocalSwConfig.json`**（用户正是在本地配置里看到它的）；用途只剩 2 处"备注留空时显示什么"的兜底，完全可以从远程配置现取
- **改动 1：三表名称列统一** —— 三张表都用 `key='display_name'` → 复用同一个 `.manage-nickname-cell`（可点击就地编辑 remark / **1 级色** / **15px** / **字重 600** / 中文雅黑 + 英文等宽分段）；程序表用 `showRowActions:false` 关掉账号语义的悬浮按钮（隐藏/重置/删除），`defaultSortField` 同步为 `display_name`；废弃的 `td[data-col="name"]` 样式与列定义一并删除（避免留下会误伤其它表的选择器）
- **改动 2：原生程序名称链** = `SwAccData.<sw>.origin_exe.remark`（原生账号 remark）**>** 平台名称；平台名称自身 = 本地 `remark` > 远程 `alias` > `swId`（`getPlatformDisplayName`）。程序表行 id 从 **exe 路径**改成固定 **`origin_exe`**（`AccCoreConstants.ORIGIN_EXE_ID`）
  - `origin_exe` 只是"程序自己的备注"节点、**不是账号** → **所有遍历账号的地方都必须排除它**：`JsBridge.getSwDetailData`、`JsBridge.getAccountList`、`AccConfigAccessor.getAllAccounts`，以及 `JsBridge` / `SwConfigProvider` 里两处"无 accountId 时取第一个账号"的退化路径（否则账号表会凭空冒出"失效账号 origin_exe"，或把备注写到别的账号身上）
  - 程序表名称列编辑 → `saveAccount(swId, 'origin_exe', {remark})`（与账号表**同一条保存链路**）；快捷键仍存 `LocalSwConfig`
  - `_alias` 清理：不再写入该字段，并在加载配置时 `delete config._alias`（下次保存时本地文件里那条就没了）
- **改动 3：中英分字体的落地（有实测结论，别再走弯路）** —— 本 WebKit **做不到**"一个元素里中文雅黑 + 英文等宽"：
  ① `font-family` 列表里雅黑排在等宽**之后**不生效（等宽族缺中文时走**系统 CJK 回退**，实测中文墨块 131，雅黑应为 175）；
  ② `@font-face + unicode-range` 在这个版本**不生效**（把中文专用字体放列表最前，英文会被它一起吃掉，实测英文墨块 124 = 雅黑，等宽应为 118）
  → 只能**显式分段**：`account-table.js scriptSplitHtml()` 把中文段套 `.cjk-run`、非中文段套 `.lat-run`，各自 `font-family`（定义在 `theme.css`）
  → 编辑态曾改用 `contenteditable` div 想也做两段字体（配按字符偏移恢复光标、组字期间不动 DOM、纯文本粘贴），**用户实测"都没法修改了"** → 回退为 `<input>` + 统一等宽（教训：别为了"样式上的小收益"替换成熟的原生控件）
  - ⚠️ 期间还踩了一个"共用选择器组"的坑：把"昵称列用雅黑"写进 `.manage-text-cell, .manage-alias-cell, .manage-nickname-data-cell` 组里 → 程序表的名称/版本/路径（同属 `.manage-text-cell`）一起变雅黑（用户肉眼发现"原生程序的内容字体你忘记改了"）→ 改为单独写一条规则
- **验证**: `Round2Probe.java` 91 条断言（程序表名称列 = 15px / 字重 600 / 1 级纯白 / 可进入编辑 / 保存到 `origin_exe.remark` / 空备注时显示平台名 / 无悬浮按钮 / 中英分段各自字体）

---

## 三十八、表格文字三级色 + 删除/重置语义 + 批量删除规则（2026-10-06 凌晨）

- **表格文字三级色**（用户定；明暗两套是"反"的）: 令牌 `--text-level1/2/3` 定义在 `theme.css` 三处（dark `:root` / light / auto+light），**只作用于表格内容**（其它 UI 的 `--text-primary/secondary/muted` 不动）

  | | 1 级 | 2 级 | 3 级 |
  |---|---|---|---|
  | 深色 | `#ffffff` 纯白 | `#c0c0c0` 浅灰 | `#6c6c6c` 深灰 |
  | 浅色 | `#000000` 纯黑 | `#4a4a4a` 深灰 | `#999999` 浅灰 |

  - 规则：**普通行** 名称列 1 级、其它列 2 级；**隐藏行**（本轮新增行状态类 `tr.hidden-row`）整行 2 级；**失效行**（`tr.invalid-row`）整行 3 级 —— CSS 里失效规则排在隐藏之后，**同时满足时失效优先**
  - 名称列 `.dn-text`、头像兜底文字 `.manage-avatar-placeholder`、隐藏/失效标签都自带 `color`，必须在 hidden/invalid 规则里一并覆盖（否则它们不跟随）
  - 实测（`Round2Probe` 逐项断言 computed 值）：深色 普通名称 `rgb(255,255,255)` / 普通其它 `rgb(192,192,192)` / 隐藏整行 `rgb(192,192,192)` / 失效整行 `rgb(108,108,108)`；浅色 `rgb(0,0,0)` / `rgb(74,74,74)` / `rgb(74,74,74)` / `rgb(153,153,153)`
  - 排查插曲：首次实测得到"名称列是 2 级、隐藏行是 3 级"，先怀疑 CSS；改成**先打印真实 DOM**（行 class + computed 值）后才发现是**测试数据造错** —— 一个账号在前面的步骤里被点了隐藏按钮（真的变隐藏行），另一个账号被 `main.js` 按"不在 `getSwExistedAccounts` 里"判成了失效 → **CSS 一直是对的**
- **删除 / 重置的语义（用户明确）**: **删除** = 整个节点移除；**重置** = 清空节点内容但**保留空节点**（列表仍能正常加载，初始化流程会重新填属性）
  - 两者都新增"**清除数据目录里的头像文件**"：`AccInfoFuncCore.deleteAccountAvatarFiles(sw, acc)` —— 清掉 `{userData}/{sw}/{acc}/` 下**所有图片**（jpg/jpeg/png/bmp/gif；读取端只认 `{acc}.jpg`，但目录里可能残留历史 png），**非图片文件保留**，目录空了才删目录（**绝不递归删其它文件**）；`deleteAvatarForAcc` 改为复用它；`JsBridge.resetAccount` / `JsBridge.deleteAccount` 各接一次
  - **平台图标 `{userData}/{sw}/{sw}.png` 不受影响**
  - 验证：`AccFilesProbe.java` 直连真实代码 **8/8**（jpg 删 / png 删 / `keep.txt` 保留 / 非空目录保留 / 空目录删除 / 目录本来不存在返回 false 不算失败）
- **批量删除只对失效账号生效**: 最初写成"一个可删的都没有就静默 `return`" → **用户指出"这样用户会疑惑为啥点不了"** → 改为：**确认框照常弹**，文案按选中情况分三种（全正常 → "选中的 N 个账号都是正常账号…无法删除；点击删除不会有任何改动"；混合 → "…有 N 个是正常账号…**将被跳过**；实际只会删除其中 M 条失效账号记录…"；全失效 → 常规文案），用户仍可确认，**执行层才过滤**（只对 `invalidIds` 调 `JFC.bridge.deleteAccount`）
- **行右键菜单三项齐全**（隐藏/重置/删除）: 不能做的**显示为禁用（不隐藏）** —— 正常账号的"删除"是禁用项 + 悬停提示"正常账号（磁盘上仍然存在）无法删除"。踩坑：禁用项一开始**漏写 `data-row-action="delete"`** → 选择器查不到、事件绑定也覆盖不到（探针先报"菜单只有两项"才发现）；修法：**禁用项照样带动作标识**，只在点击处理里 `if (classList.contains('disabled')) return;`
- **顺带修掉一个真 bug**: `ConfigManager.getInstance()` 里 `ConfigManager mgr = new ConfigManager(); mgr.init(false); instance = mgr;` —— `mgr.init(false)` 调到的是**静态** `init`（它自己 new 并初始化了另一个实例赋给 `instance`），紧接着又被这个**未初始化**的 `mgr` 覆盖 → 只要 `getInstance()` 是首个入口（应用正常启动不会，Launcher 先显式 `init` 过；**独立探针 / 工具会**），拿到的实例 `userDataPath == null`，`getUserDir()` 直接 NPE。改为单一路径 `init(false)`；**是写 `AccFilesProbe` 时的 NPE 把它挖出来的**
- **验证**: `Round2Probe` 111 条断言（三级色三态 × 明暗 + 右键菜单三项/禁用/点禁用无反应 + 批量删除三种文案与执行层过滤）、`RoundProbe` 回归 63 条、`gradle test` 57 例 0 失败
