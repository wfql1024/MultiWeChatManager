# CLAUDE.md — JhiFengMultiChat（极峰多聊）

> 最后更新: 2026-07-06
> 当前阶段: 见 MEMORY/FACTS.MD
> 记忆系统: MEMORY/（MEMORY.md 索引 + DECISIONS.MD/TODOS.MD/FACTS.MD + DEV_LOGS.MD）

---

## 一、项目身份

- **项目名**: JhiFengMultiChat（极峰多聊）
- **定位**: Windows 桌面端多平台聊天软件管理器（Java 17 重写版）
- **功能**: 微信/企业微信/QQ/TIM/钉钉/飞书多账号管理 — 多开、防撤回、一键登录、窗口切换
- **Python 旧版参考**: `legacy_python/`（不在版本控制中，仅供数据结构/业务逻辑参考）
- **工作目录**: `D:\SpaceDev\MyProj\JhiFengMultiChat`
- **远端**: `main` 分支

---

## 二、技术栈

| 层面 | 选型 |
|------|------|
| JDK | 17 LTS (`D:\SpaceDev\softwareDev\SDKs\Java\jdk-17.0.2`) |
| 构建 | Gradle 8.8 (Kotlin DSL) |
| UI | JavaFX 17, `StageStyle.TRANSPARENT` |
| 渲染 | WebView 内嵌 HTML/CSS/JS |
| JSON | Jackson 2.16 |
| 日志 | SLF4J 2.0.9 + Logback 1.4.14 + jul-to-slf4j 桥 |
| HTTP | `java.net.http.HttpClient`（JDK 内置） |
| 加密 | `javax.crypto.Cipher`（AES/CBC/PKCS5Padding） |
| 异步 | `Executors.newCachedThreadPool` → `Platform.runLater` → `executeScript` |
| 图标 | MCP 服务器 `mcp-universal-icons` + `icons-mcp`（`.mcp.json`） |
| JNA | 5.14.0 (`jna` + `jna-platform`)，用于 Windows API 调用 |
| 测试 | JUnit 5.10.2 + Mockito 5.10.0 |

---

## 三、项目结构

```
├── build.gradle.kts
├── settings.gradle.kts
├── run.bat
├── logo.png
│
└── src/main/
    ├── java/com/jfmultichat/
    │   ├── Launcher.java              # 入口: 设 logdir → ConfigManager.init() → launch JavaFX
    │   ├── MainApp.java               # Application, saveAll() on exit
    │   ├── config/
    │   │   ├── AppEnv.java            # 运行环境判断 (DEV/TEST/PROD)
    │   │   ├── AppPaths.java          # %APPDATA%/JhiFengMultiChat/{version}/ 路径规范
    │   │   ├── AppVersion.java        # 版本号 + 产品名 + 公司名
    │   │   ├── IConfigStore.java      # 统一配置接口（字典式读写）
    │   │   ├── JsonConfigStore.java   # JSON 配置存储基类
    │   │   ├── RootConfig.java        # RootConfig.json POJO（代理/URL/数据目录）
    │   │   ├── ConfigManager.java     # 配置管理器单例 — 统筹所有 ConfigStore
    │   │   ├── CryptoUtils.java       # AES-CBC 解密 + [INFO] 级日志
    │   │   └── RemoteConfigFetcher.java # HTTP下载 + 解密 + 本地缓存
    │   ├── bridge/
    │   │   └── JsBridge.java          # JS↔Java 桥 + 异步回调 + 所有数据访问 + BridgeConfigProvider
    │   ├── swcore/                    # Windows 路径探测 + 补丁引擎（独立包）
    │   │   ├── SwCoreConstants.java   # 常量统一定义（RemoteSwKey/AccKeys）
    │   │   ├── SwHexUtils.java        # 特征码扫描（hex模式/通配符/截断）
    │   │   ├── SwRuleResolver.java    # 规则解析（simple/custom/jmp_offset/relation）
    │   │   ├── SwAdapterChecker.java  # 补丁状态检测
    │   │   ├── SwConfigAccessor.java  # 配置读取包装器（Provider 注入）
    │   │   ├── SwPathResolver.java    # 路径解析（resolve_sw_path, is_valid_sw_path）
    │   │   ├── SwVersionHelper.java   # 版本计算（calc_sw_ver）
    │   │   ├── SwRectCalculator.java  # 截图区域计算
    │   │   ├── SwPidMutexOps.java     # PID-互斥体配置操作
    │   │   ├── SwAccountOps.java      # 账号列表, 共存模式, 多开检测
    │   │   ├── SwOperatorCore.java    # DLL切换/共存/登录/备份
    │   │   ├── SwAvatarOps.java       # 头像截取/缓存
    │   │   ├── SwInfoFuncCore.java    # Facade 入口
    │   │   ├── SwPathDetective.java   # 路径探测（六级策略/批量pathType/并发/懒加载）
    │   │   └── SwNativeOps.java       # JNA 原生操作封装 + MemoryMapIterator
    │   ├── setting/
    │   │   ├── AbsSetting.java        # JSON 配置基类 (SLF4J)
    │   │   └── RemoteGlobalSetting.java # 远程全局配置 (回退 classpath 种子)
    │   ├── model/
    │   │   ├── AboutInfo.java / LinkEntry.java / ReferenceEntry.java / SponsorEntry.java
    │   └── ui/
    │       ├── MainWindow.java        # 主窗口 (StackPane + 标题栏 + WebView + 缩放手柄)
    │       ├── FloatingSidebar.java / SampleWindow.java
    │
    └── resources/
        ├── logback.xml
        ├── css/ (main.css, main-light.css, sidebar.css)
        ├── data/remote_global_v1.json  # 种子数据
        └── web/
            ├── index.html
            ├── css/ (theme.css, main.css)
            └── js/
                ├── bridge.js           # JS→Java 桥 (含异步回调 _handleAsync)
                ├── icons.js            # SVG 图标
                ├── app.js              # 路由 + toast + ensureRemoteConfigs
                ├── components/nav-sidebar.js
                └── pages/
                    ├── settings.js     # 设置页
                    └── manage.js       # 管理页（下拉面板/自动探测/优先级选择）

└── src/test/java/com/jfmultichat/swcore/
    ├── SwNativeOpsTest.java           # JNA 三方案对比 + 去子进程
    └── SwPathDetectiveTest.java       # 29 tests (批量/并发/Mock)
```

---

## 四、数据存储路径

```
%APPDATA%/JhiFengMultiChat/4.0.0.7000/
├── RootConfig.json                   # 锚点，永不移动。存储代理/URL列表/数据目录
├── UserFiles/                        # 正式版
│   ├── LocalGlobalConfig.json        # 软件偏好（主题、窗帘状态等）
│   ├── LocalSwConfig.json            # 各平台设置（{swId: {inst_path, remark, ...}}）
│   ├── SwAccData.json                # 账号数据
│   ├── SwCache.json                  # 适配缓存
│   ├── RemoteGlobalConfig.json       # 远程全局配置缓存
│   ├── RemoteSwConfig.json           # 远程平台配置缓存
│   └── logs/
└── DevUserFiles/                     # 开发版（--dev），文件结构相同
```

**RootConfig.json 字段**:
```json
{
  "user_data_path": "...",
  "remote_global_urls": ["https://..."],
  "remote_sw_urls": ["https://..."],
  "use_proxy": false,
  "proxy_ip": "",
  "proxy_port": ""
}
```
注意：程序硬编码的默认 URL 不存入配置，仅存用户添加的地址。

---

## 五、配置层架构（重要！）

### 接口层次

```
IConfigStore (interface)
  ├── getData() / setData() / reload() / save()
  ├── getString(key, defaultVal) / getBoolean / put / remove / has
  └── ensureFile() / isEmpty()
        ↑
JsonConfigStore (base class — Jackson ObjectNode 读写)
  ├── getSubNode(key) / setSubNode / removeSubNode / fieldNames()
  ├── loadFromJson(json) / toJson() / deepCopy()
        ↑
ConfigManager (单例 — 统筹 6 个 ConfigStore + RootConfig POJO)
  ├── getRootConfig()        → RootConfig POJO
  ├── getGlobalConfig()      → LocalGlobalConfig.json ObjectNode
  ├── getSwConfig(swId)      → LocalSwConfig.json.{swId}
  ├── getRemoteGlobal()      → RemoteGlobalConfig.json ObjectNode
  ├── getRemoteSw()          → RemoteSwConfig.json ObjectNode
  ├── getAccountMap(swId)    → SwAccData.json.{swId}
  └── getSwCache()           → SwCache.json
```

**未来扩展**：若要更换存储格式（如 YAML、数据库），只需实现新的 `IConfigStore`，替换 `ConfigManager` 中的 store 创建即可。

---

## 六、JS↔Java 异步架构（重要！）

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

**关键方法**:
- 同步: `getSwConfig()`, `getSwDetailData()`, `saveSwConfig()`, `extractExeIcon()`
- 异步: `testRemoteUrlAsync(url, cbId)`, `fetchUpdateDataAsync(cbId)`, `tryEnsureRemoteConfigsAsync(cbId)`, `detectPathsAsync(swId, cbId, pathKeysJson)`
- **detectPathsAsync 注意**: 第三个参数是 JSON 字符串 `'["inst_path","data_dir"]'`（非 varargs！JavaFX JS 桥不支持 varargs），为空时默认全三项
- `bridge.js`: `registerAsync(fn)` 注册回调，`_handleAsync(type, cbId, json)` 是 Java 调用入口

---

## 七、远程配置兜底机制

任何需要读取远程配置的操作，都必须先检查 → 缺失则异步下载 → 失败则 toast 提醒 + 强制跳转设置页。

```
JFC.ensureRemoteConfigs(onReady)
  ├── checkRemoteConfigReady() — 同步快速检查
  ├── 已就绪 → onReady()
  └── 缺失 → tryEnsureRemoteConfigsAsync() — 后台下载
        ├── 成功 → onReady()
        └── 失败 → JFC.toastError(msg) + forceGotoSettingsConfig()
```

**调用点**: `app.js` 启动检查、`manage.js` loadPlatformList / selectPlatform

---

## 八、Toast 通知系统

```javascript
JFC.toastError('消息', duration);    // 右下角红色，默认 4 秒
JFC.toastSuccess('消息', duration);  // 右下角绿色，默认 3 秒
```

动态创建容器 `#toast-container`，带 ✕ 手动关闭。CSS: `main.css` `.toast-container` / `.toast`。

---

## 九、页面架构

### 全局侧栏 (`#nav-sidebar`)
平台列表（动态渲染）+ 底部统计/设置入口。平台列表由 `main.js` 渲染，进入软件即加载（`MainWindow.injectJsBridge()` 触发）。

### 主页面 (`#page-main`)
唯一主内容区，无内嵌左栏。`main.js` 中 `getEl` 作用域隔离: `querySelector('#page-main #' + id) || document.getElementById(id)`。跨页面元素（`#nav-platform-list`）直接用 `document.getElementById`。

### 已废弃
`#page-manage` → `.old/`，`manage.js` → `.old/manage.js`。

### 详情区
路径输入框（内嵌 ▼ 下拉面板，body 层 `position:fixed`，z-index:40）、设置面板（窗帘折叠 + 高度拖动）、账号表格（多选 + 排序 + 批量操作）。自动填充优先级: 存在 > 进程 > 内存映射 > DLL遍历 > 注册表 > 猜测/其他SW > 来源数量。

---

## 十、设置页各页面状态

| 页面 | 数据来源 | 加载方式 | 关键方法 |
|------|---------|---------|---------|
| 外观 | LocalGlobalConfig.json | 同步 | `getTheme()` / `saveTheme()` |
| 配置 | RootConfig.json | 同步 + 异步测试 | `getConfigData()` / `saveConfigData()` / `testUrlAsync()` |
| 更新 | RemoteGlobalConfig (网络) | **异步** | `fetchUpdateDataAsync()` + "更新远程配置"按钮 |
| 鸣谢 | RemoteGlobalConfig (网络) | **异步** | `fetchThanksDataAsync()` |
| 关于 | RemoteGlobalConfig (网络) | **异步** | `fetchAboutDataAsync()` |

---

## 十一、加密协议

远程配置文件加密格式（对应 Python `CryptoUtils.decrypt_response`）：
```
HTTP 响应文本 = base64(IV[16] + ciphertext) + " " + key
解密: Base64解码 → IV=前16字节, key=key.ljust(16)[:16].encode()
     → AES/CBC/PKCS5Padding 解密 → UTF-8 JSON
```
Java 实现: `CryptoUtils.decryptResponse(String)`，每步有 `[INFO]` 日志。

**下载/解密日志关键词**: `[下载]` 和 `[解密]`，搜这两个 tag 即可追踪完整流程。

---

## 十二、用户偏好（严格遵守）

1. **字号要大** — 所有字号 +2：h1=20, h2=17, h3=15, body=15, sm=14, xs=13, btn=15/13
2. **括号规范** — 数据目录输入框: `（默认）`(中文全角括号)；网址列表: `(默认)`(英文半角)
3. **标题层级** — 一级标题(h1): 区块标题；二级标题(h2): 小节标签；三级标题(h3): 子节标签
4. **后台线程** — 绝对不用 `setTimeout` 模拟异步；必须用 Java `ExecutorService` + `Platform.runLater` + `executeScript`
5. **编译不要问** — `gradle build` 直接执行，只有 `rm -rf` 这类高风险命令需要确认
6. **Python 旧版参考** — 业务逻辑优先参考 `legacy_python/` 中对应代码
7. **字体** — 基础字体 `"Microsoft YaHei", "PingFang SC", "Segoe UI", system-ui`；等宽字体 `"Cascadia Code", "Consolas", monospace`
8. **理解指令要精准** — 用户说"复制粘贴"，就是字面意义的完整复制粘贴，不要自作主张做 ID 去重、变量重命名、sed 替换等"优化"。用户说"不要改"，就一个字都别改。
9. **复用已验证代码** — 已完美工作的动画/逻辑，直接复用，不要重写、不要"改进"、不要创造新方案。用户明确指出参考对象时，照搬即可。
10. **简单操作不要复杂化** — 移动按钮、复制页面等简单需求，直接操作 DOM/文件，不要引入新架构、新模块、新命名体系。越简单越好。
11. **回退要干脆** — 用户要求回退到提交时，直接 `git checkout HEAD -- <files>`，不要反复确认、不要保留"可能有用的改动"。

---

## 十三、关键技术教训
### DEV_LOGS.md 维护规范
当用户要求总结时：
"总结近期开发"：将未添加到 DEV_LOGS.MD 的节点更新上去并附日期，标题格式 ## 功能名称（YYYY-MM-DD）
"总结近期历史"：新增 ## 标题章节，不追加到之前的"历史对话基本大纲"节点，保持独立可追溯

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

---

## 十四、运行命令

```bash
cd D:\SpaceDev\MyProj\JhiFengMultiChat
export JAVA_HOME="/d/SpaceDev/softwareDev/SDKs/Java/jdk-17.0.2"
export PATH="/d/SpaceDev/softwareDev/SDKs/gradle-8.8/bin:$PATH"

# 开发运行 (scripts/run.bat)
gradle run --no-daemon --args="--dev"

# 仅编译
gradle compileJava --no-daemon

# 完整构建
gradle build --no-daemon

# 打包 (见 scripts/package-exe.bat)
.\scripts\analyze.bat     # 依赖分析
.\scripts\package-exe.bat # 生成安装版+便携版
```

## 十五、待推进

见 `MEMORY/待办.md`。

---

## 十六、swcore 包关键细节

### SwConfigAccessor.Provider 模式
`SwConfigAccessor` 本身不直接读写配置，而是通过 `Provider` 接口注入。`BridgeConfigProvider`（`JsBridge` 内部类）将 `ConfigManager` 适配为 Provider。所有公共方法都转发给 provider。

### 六级路径探测策略（detectAll 并发执行）
1. **内存映射正则** → `queryByMemoryRegex()` 多 pathType 共享一次懒加载扫描（`MemoryMapIterator`）
2. **注册表查询** → `queryByRegister()` 用 `Advapi32Util.registryGetStringValue`
3. **猜测 (addr)** → `queryByGuess()` 从系统目录拼接 sub_path
4. **进程枚举** → `queryByProcess()` 用 `CreateToolhelp32Snapshot` + `Process32First/Next`
5. **其他 SW 推断** → `queryFromOtherSw()` WeChat⇔Weixin / QQ⇔TIM 共用目录
6. **DLL 目录遍历** → `queryDllDirByFiles()` BFS 遍历安装目录查找 DLL

### detectAll 签名
```java
Map<String, List<PathEntry>> detectAll(SwConfigAccessor accessor, String sw, String... pathTypes)
```
- 返回每个 pathType 的所有候选 PathEntry（含 `sources: List<String>`）
- 内部 6 路子查询用 `CachedThreadPool` 并发，`Future.get(30s)` 超时保护
- 同一路径多来源通过 `PathEntry.withSource()` 合并

### MemoryMapIterator（懒加载迭代器）
- `iterateMemoryMapPaths(sw, exeWildcards)` 返回 `MemoryMapIterator extends Iterator<String>, AutoCloseable`
- 内部用 `VirtualQueryEx` + `GetMappedFileNameW` 逐区域推进，每次 `next()` 只返回一条路径
- 多 PID 通过 `CompositeMemoryMapIterator` 串联，`finally` 块确保 `close()` 释放句柄

### normalizePath 统一规范
```java
static String normalizePath(String rawPath)
```
去引号 → `\`→`/` → 盘符大写（`c:`→`C:`）→ 去末尾 `/`。所有 PathEntry 构造点调用。

### 自动填充优先级
存在 > 进程(1) > 内存映射(2) > DLL遍历(3) > 注册表(4) > 猜测(5)=其他SW(5) > 来源数量 > 第一条

### 日志关键词
- `[路径探测] detectAll 完成` — 汇总结果数
- `[路径内存映射] 共享扫描启动` — 懒加载扫描开始
- `[路径内存映射] 匹配成功` — 单条正则命中
- `[路径注册表]` / `[路径猜测]` / `[路径进程]` / `[路径其他SW]` / `[路径DLL目录]` — 各子查询
- `[WebView]` — JS console.log 重定向（需 `--add-exports` + `WebConsoleListener`）

---


### DEV_LOGS.md 维护规范
当用户要求总结时："总结近期开发"将节点更新至 DEV_LOGS.MD 并附日期；"总结近期历史"新增 ## 标题章节，保持独立可追溯。

