# CLAUDE.md — JhiFengMultiChat（极峰多聊）

> 最后更新: 2026-06-21  
> 当前阶段: Phase 0 — 配置管理 + 设置页 UI 完成

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
    │   │   ├── AppVersion.java        # 版本号 + 产品名 + 公司名 + parseVersion/splitVersions
    │   │   ├── RootConfig.java        # root_config.json 模型
    │   │   ├── ConfigManager.java     # 配置管理器单例（~400行）
    │   │   ├── CryptoUtils.java       # AES-CBC 解密 (对应 Python decrypt_response)
    │   │   └── RemoteConfigFetcher.java # HTTP下载 + 解密 + 本地缓存
    │   ├── bridge/
    │   │   └── JsBridge.java          # JS↔Java 桥 + 异步回调 + 所有数据访问
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
                ├── icons.js / app.js
                ├── components/nav-sidebar.js
                └── pages/settings.js   # 设置页全部逻辑 (~600行)
```

---

## 四、数据存储路径

```
%APPDATA%/JhiFengMultiChat/4.0.0.7000/
├── root_config.json              # 锚点，永不移动
├── user_files/                   # 正式版
│   ├── local_config.json         # global设置 + Sw配置
│   ├── sw_acc_data.json          # 账号数据
│   ├── sw_cache.json             # 适配缓存（不解析内部结构）
│   ├── remote_global.json        # 远程全局缓存
│   ├── remote_sw.json            # 远程平台缓存
│   └── logs/
└── dev_user_files/               # 开发版（--dev）
```

---

## 五、JS↔Java 异步架构（重要！）

**绝对不能阻塞 UI 线程！** 所有网络操作必须后台线程执行。

```
JS 调用 void Java 方法 → 立刻返回
                   ↓
       ThreadPool 后台线程
       · HTTP 下载
       · AES 解密 (CryptoUtils.decryptResponse)
       · JSON 解析
                   ↓
       Platform.runLater → scriptExecutor
       → JFC.bridge._handleAsync(type, cbId, jsonStr)
                   ↓
       JS 回调更新 DOM
```

**关键类和方法：**
- `JsBridge`: `testRemoteUrlAsync(url, cbId)`, `fetchUpdateDataAsync(cbId)`, `fetchThanksDataAsync(cbId)`, `fetchAboutDataAsync(cbId)` — 全是 `void`，结果通过 `pushToJs()` 回传
- `bridge.js`: `registerAsync(fn)` 注册回调，`_handleAsync(type, cbId, json)` 是 Java 调用的入口
- `settings.js`: `JFC.bridge.testUrlAsync(url, fn)` → fn 在后台线程完成后被调用

---

## 六、设置页各页面状态

| 页面 | 数据来源 | 加载方式 | 关键方法 |
|------|---------|---------|---------|
| 外观 | local_config.json | 同步 | `getTheme()` / `saveTheme()` |
| 配置 | 混合 | 同步 + 异步测试 | `getConfigData()` / `saveConfigData()` / `testUrlAsync()` |
| 更新 | remote_global (网络) | **异步** | `fetchUpdateDataAsync()` + `AppVersion.splitVersions()` |
| 鸣谢 | remote_global (网络) | **异步** | `fetchThanksDataAsync()` (含 thanks+sponsor+reference) |
| 关于 | remote_global (网络) | **异步** | `fetchAboutDataAsync()` (home+project, 不含reference) |

---

## 七、配置页 URL 列表

远程平台和远程全局各有一个 URL 列表，结构：
- 默认行（内置 Gitee/GitHub 地址）：`(默认) url`，input readonly，删除按钮禁用
- 用户行：可编辑/删除
- 每行有"测试"按钮，异步执行 HTTP → 解密 → JSON解析
- 底部"测试全部"（所有行并发后台线程）、"添加"（拷贝最后一行 URL）
- 保存条件：每个 section 至少有一个绿框（测试通过）

---

## 八、加密协议

远程配置文件加密格式（对应 Python `CryptoUtils.decrypt_response`）：
```
HTTP 响应文本 = base64(IV[16] + ciphertext) + " " + key
解密: Base64解码 → IV=前16字节, key=key.ljust(16)[:16].encode()
     → AES/CBC/PKCS5Padding 解密 → UTF-8 JSON
```
Java 实现: `CryptoUtils.decryptResponse(String)`

---

## 九、内置远程配置 URL

```java
// RemoteConfigFetcher.java — 四个内置地址
REMOTE_SW_GITEE   = ".../MultiWeChatManager/raw/main/remote_configs/remote_sw_v9"
REMOTE_SW_GITHUB  = ".../MultiWeChatManager/main/remote_configs/remote_sw_v9"
REMOTE_GLOBAL_GITEE  = ".../MultiWeChatManager/raw/main/remote_configs/remote_global_v1"
REMOTE_GLOBAL_GITHUB = ".../MultiWeChatManager/main/remote_configs/remote_global_v1"
```
注意: `main` 分支暂未上传这些文件，用户会手动加 `python` 分支的地址。HTTP 客户端已配置 `.followRedirects(NORMAL)`。

---

## 十、用户偏好（严格遵守）

1. **字号要大** — 所有字号 +2：h1=20, h2=17, body=15, sm=14, xs=13, btn=15/13
2. **括号规范** — 数据目录输入框: `（默认）`(中文全角括号)；网址列表: `(默认)`(英文半角)
3. **标题层级** — 一级标题(h1): 区块标题如"软件更新""代理"；二级标题(h2): 小节标签如"数据目录""远程平台"
4. **"数据目录"/"远程平台"/"远程全局"三者必须用同一个 CSS class** (`config-subtitle`)，统一风格
5. **后台线程** — 绝对不用 `setTimeout` 模拟异步；必须用 Java `ExecutorService` + `Platform.runLater` + `executeScript`
6. **编译不要问** — `gradle build` 直接执行，只有 `rm -rf` 这类高风险命令需要确认
7. **Python 旧版参考** — 业务逻辑优先参考 `legacy_python/` 中对应代码
8. **字体** — 基础字体 `"Microsoft YaHei", "PingFang SC", "Segoe UI", system-ui`；等宽字体 `"Cascadia Code", "Consolas", monospace`

---

## 十一、已知问题 / 待解决

1. **自动滚动** — 赞助列表和技术参考的自滚动效果不稳定（有时不会向下滚）。当前用 `requestAnimationFrame` 双缓冲启动 + `setTimeout` 链式调度。可能需要调试 `scrollHeight`/`clientHeight` 的获取时机。
2. **默认 URL 404** — 四个内置 URL 指向 `main` 分支但文件尚未上传。用户手动添加 `python` 分支的地址作为临时方案。
3. **版本号硬编码** — `AppVersion.VERSION = "4.0.0.7000"`，打包流程需从此处读取并注入 `.exe` 资源。
4. **`legacy_python/utils/encoding_utils.py` 源码丢失** — 只有 `.pyc` 编译文件，`CryptoUtils.decrypt_response` 的加密密钥逻辑已通过反编译字节码还原为 Java。

---

## 十二、关键技术教训

1. **WebView 拦截鼠标** → 透明 Region 覆盖层绕过
2. **root 引用时序** → 先建 root 再 buildResizeHandles
3. **location listener 二次触发** → suppressLinkIntercept 标志
4. **maximized 拖拽** → DRAG_THRESHOLD=4 阈值
5. **isDragging 标志** → 防窗口闪移
6. **UTF-8 BOM** → `.bat` 用 Bash `cat >` 写
7. **Java 方法签名歧义** → getStringOr(defaultVal, ...path)
8. **Logback 属性时序** → `jfmultichat.logdir` 必须在首次 `LoggerFactory.getLogger()` 之前
9. **HTTP 重定向** → `HttpClient` 默认不跟随，必须 `.followRedirects(NORMAL)`
10. **WebView JS bridge 返回值** → boolean 可能被序列化为字符串，JS 端用 `=== true` 严格比较

---

## 十三、运行命令

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

# 完整构建（生成 jar）
gradle build --no-daemon
# 如果报 "Failed to clean up stale outputs" → taskkill //F //IM java.exe → rm -rf build → 重试
```

---

## 十四、待推进 (后续 Phase)

1. Native 层 JNA（进程/窗口/注册表）
2. 登录页 / 管理页 / 统计页
3. 数据库层 SQLite + DAO
4. 远程配置加密下载完成（URL 就绪后即可工作）
5. 二进制补丁引擎迁移（待评估合法性）
6. 打包流程（从 AppVersion 读取版本信息，注入 .exe 资源）
