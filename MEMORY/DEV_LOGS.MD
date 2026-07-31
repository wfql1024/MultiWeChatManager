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
- 未提交（6 文件）: logback.xml, Launcher.java, JsBridge.java, bridge.js, index.html, settings.js
- 后台会话 worktree 隔离: 用户要求直接改主目录文件，`.claude/settings.json` 设 `"worktree": {"bgIsolation": "none"}`（gitignored）
