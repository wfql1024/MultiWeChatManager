# CLAUDE.md — JhiFengMultiChat（极峰多聊）

> 最后更新: 2026-06-25
> 当前阶段: Phase 1 — 管理页 UI + 配置层重构完成 + swcore 路径探测 + 配置读写锁

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
    │   │   ├── SwPathDetective.java   # 路径探测（三级策略：注册表/进程/mmap）
    │   │   └── SwNativeOps.java       # JNA 原生操作封装（进程/互斥体/窗口/截图）
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
        ├── css/ (main.css, main-light.css)
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
                    ├── settings.js     # 设置页 (~700行)
                    └── manage.js       # 管理页 (~700行)
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
- 异步: `testRemoteUrlAsync(url, cbId)`, `fetchUpdateDataAsync(cbId)`, `tryEnsureRemoteConfigsAsync(cbId)`
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

## 九、管理页架构

```
┌─ manage-layout (grid) ────────────────────────────┐
│ ┌─ 平台侧栏 (z:50) ─┐  ┌─ 详情区 ────────────────┐ │
│ │ [全部]             │  │ ┌─ 标题（可编辑）─────┐ │ │
│ │ [WeChat]           │  │ │ remark > alias > id │ │ │
│ │ [QQ] ...           │  │ └────────────────────┘ │ │
│ │                    │  │ ┌─ 设置面板（窗帘）───┐ │ │
│ │ hover展开/收起     │  │ │ 软件路径/数据目录   │ │ │
│ │                    │  │ │ DLL路径/登录尺寸    │ │ │
│ └────────────────────┘  │ │ 点击按钮            │ │ │
│                         │ │ ∧ ⚙ ∧（窗帘把手）  │ │ │
│                         │ └────────────────────┘ │ │
│                         │ ┌─ 账号表格 ──────────┐ │ │
│                         │ │ ☑ 头像 昵称 ID 状态 │ │ │
│                         │ │ 批量隐藏/显示/删除  │ │ │
│                         │ └────────────────────┘ │ │
│                         └────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

**平台栏**: 完全复用 `.nav-sidebar` hover 展开/收起样式，z-index:50（低于主导航100）。
**标题**: remark（本地）> alias（远程）> swId。点击可编辑，Enter 保存到 `LocalSwConfig.json.{swId}.remark`。
**设置面板**: 窗帘折叠，偏好持久化到 `LocalGlobalConfig.json.manage_settings_collapsed`。
**账号表格**: 复选框多选 + 表头排序 + 行悬浮操作按钮 + 批量操作栏。

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

---

## 十三、关键技术教训

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

---

## 十四、运行命令

```bash
cd D:\SpaceDev\MyProj\JhiFengMultiChat
export JAVA_HOME="/d/SpaceDev/softwareDev/SDKs/Java/jdk-17.0.2"
export PATH="/d/SpaceDev/softwareDev/SDKs/gradle-8.8/bin:$PATH"

# 正式版
gradle run --no-daemon

# 开发版
gradle run --no-daemon --args="--dev"

# 仅编译
gradle compileJava --no-daemon

# 完整构建
gradle build --no-daemon
# 如果报 "Failed to clean up stale outputs" → taskkill //F //IM java.exe → rm -rf build → 重试
```

---

## 十五、待推进 (后续 Phase)

1. Native 层 JNA（进程/窗口/注册表）— 已实现路径探测三级策略
2. 登录页 / 统计页
3. 数据库层 SQLite + DAO
4. 平台图标提取完善（ExtractIconExW）
5. 二进制补丁引擎迁移（待评估合法性）
6. 打包流程（从 AppVersion 读取版本信息，注入 .exe 资源）

---

## 十六、swcore 包关键细节

### SwConfigAccessor.Provider 模式
`SwConfigAccessor` 本身不直接读写配置，而是通过 `Provider` 接口注入。`BridgeConfigProvider`（`JsBridge` 内部类）将 `ConfigManager` 适配为 Provider。所有公共方法都转发给 provider。

### 三级路径探测策略
1. **注册表查询** → `SwNativeOps.readRegistryValue()` 用 `Advapi32Util.registryGetStringValue`
2. **进程枚举** → `SwPathDetective.detectByProcess()` 用 `CreateToolhelp32Snapshot` + `Process32First/Next`
3. **内存映射正则** → `SwNativeOps.queryMemoryMapPaths()` 用 `VirtualQueryEx` + `GetMappedFileNameW`

### queryMemoryMapPaths 算法
- 不使用 `EnumProcessModules`（那是模块列表，不是物理内存映射）
- 使用 `VirtualQueryEx` 遍历每个内存区域 + `GetMappedFileNameW` 获取文件路径
- `GetMappedFileNameW` 在 JNA 5.14.0 未声明，需通过 `Kernel32Ext` 扩展接口调用
- 返回 NT 路径（`\Device\HarddiskVolume2\...`）需经 `convertNtPathToWin()` 转盘符路径

### 日志关键词
- `[路径内存映射-MEMMAP]` — 列出所有内存映射路径（INFO 级）
- `[路径内存映射-MATCHED]` — 匹配到的路径（INFO 级）
- `[路径内存映射] 正则编译失败` — 警告
