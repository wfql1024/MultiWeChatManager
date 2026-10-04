# JhiFengMultiChat 项目结构文档

> 最后更新: 2026-08-01

---

## 一、根目录概述

```
JhiFengMultiChat/
├── build.gradle.kts              # Gradle 构建脚本 (Kotlin DSL)
├── settings.gradle.kts           # Gradle 设置文件
├── run.bat                       # 运行脚本
├── logo.ico                      # 应用图标 (ICO 格式)
├── logo.png                      # 应用图标 (PNG 格式)
├── AGENTS.md                      # 项目主文档（规则文件）
├── MEMORY/                       # 记忆系统文档目录
│   ├── MEMORY.md                 # 索引与摘要
│   ├── DECISIONS.MD              # 决策记录
│   ├── DEV_LOGS.MD               # 开发过程日志
│   ├── FACTS.MD                  # 事实摘要
│   └── TODOS.MD                  # 待办列表
├── .old/                         # 废弃代码归档
│   └── manage.js                 # 原管理页 JS
├── src/                           # 源码目录（main / test / tools 三个源集）
├── resources/                     # 资源文件目录
├── scripts/                       # 构建/运行/发布脚本 + 远程配置源 JSON
├── remote_configs/                # 远程配置发布产物（加密后，客户端按 URL 下载）
├─ .claude/                       # Claude 配置目录
├─ .gradle/                       # Gradle 缓存目录
├─ .git/                          # Git 版本控制目录
├─ bin/                           # 编译输出目录
├─ build/                         # 构建输出目录
├─ storage/                       # 数据存储目录
└─ legacy_python/                 # Python 旧版参考 (不在版本控制中)
```

---

## 二、Java 源码结构 (`src/main/java/com/jfmultichat/`)

```
com/jfmultichat/
├── Launcher.java                    # 程序入口点
├── MainApp.java                     # JavaFX Application 主类
├── PlatformEventBootstrap.java      # EventBus 订阅装配点（流A 平台维护 / 流B 数据定向推送）
├── acccore/                         # 账号信息核心（对应 Python acc_func_core）
│   ├── AccCoreConstants.java        # 账号数据键 + 状态枚举
│   ├── AccConfigAccessor.java       # 账号数据访问器（读写 SwAccData.json）
│   ├── AccInfoFuncCore.java         # 头像/展示名/登录状态/共存判断/窗口绑定
│   ├── AccOperatorCore.java         # 登录配置读写/进程管理/互斥体查杀
│   └── AccOpsProvider.java          # 账号操作提供器（转 swcore 接口）
├── appcore/                         # 应用信息核心（对应 Python app_func_core）
│   ├── AppCoreConstants.java        # 常量定义（RootConfig/GlobalSetting/RemoteSw/AccKey 键名）
│   ├── AppConfigAccessor.java       # 配置访问器，直接读写 ConfigManager
│   └── AppCore.java                 # 远程配置获取、版本检查、平台列表、数据迁移、代理设置
├── bridge/                          # JavaScript ↔ Java 桥接
│   └── JsBridge.java                # JS 调用 Java 的入口 + 异步回调机制 + EventBus 触发/推送
├── config/                          # 配置管理子系统
│   ├── AppEnv.java                  # 运行环境判断 (DEV/TEST/PROD)
│   ├── AppPaths.java                # 路径规范定义
│   ├── AppVersion.java              # 版本号与元数据 (唯一来源)
│   ├── IConfigStore.java            # 配置存储接口
│   ├── JsonConfigStore.java         # JSON 配置存储基类 (Jackson)
│   ├── ConfigManager.java           # 配置管理器单例
│   ├── CryptoUtils.java             # AES-CBC 加密解密工具
│   ├── RemoteConfigFetcher.java     # 远程配置下载与缓存
│   ├── RootConfig.java              # RootConfig.json POJO
│   └── SwConfigProvider.java        # 公开的 SwConfigAccessor.Provider（newAccessor）
├── core/                            # 跨切面基础设施
│   ├── EventBus.java                # 轻量事件总线单例（subscribe/publish，观察者模式）
│   └── event/                       # 事件定义
│       ├── PlatformEnteredEvent.java    # 平台进入事件（流A 触发自动维护）
│       └── AccountDataChangedEvent.java # 账号数据变更事件（流B 触发定向 UI 刷新）
├── model/                           # 数据模型 (用于 About/Reference/Sponsor 页面)
│   ├── AboutInfo.java               # 关于页面数据模型
│   ├── LinkEntry.java               # 链接条目
│   ├── ReferenceEntry.java          # 引用条目
│   └── SponsorEntry.java            # 赞助条目
├── setting/                         # 设置项抽象基类
│   ├── AbsSetting.java              # JSON 配置基类 (SLF4J 日志)
│   └── RemoteGlobalSetting.java     # 远程全局配置 (回退 classpath 种子)
├── swcore/                          # Windows 探测与补丁引擎核心
│   ├── SwCoreConstants.java         # 常量统一定义 (RemoteSwKey/AccKeys)
│   ├── SwHexUtils.java              # 特征码扫描 (hex/通配符/截断)
│   ├── SwRuleResolver.java          # 规则解析 (simple/custom/jmp_offset/relation)
│   ├── SwAdapterChecker.java        # 补丁状态检测
│   ├── SwConfigAccessor.java        # 配置读取包装器 (Provider 注入)
│   ├── SwPathResolver.java          # 路径解析函数
│   ├── SwVersionHelper.java         # 版本计算工具
│   ├── SwRectCalculator.java        # 截图区域计算
│   ├── SwPidMutexOps.java           # PID-互斥体配置操作
│   ├── SwAccountOps.java            # 账号列表与多开检测
│   ├── SwOperatorCore.java          # DLL切换/共存/登录/备份
│   ├── SwAvatarOps.java             # 头像截取与缓存
│   ├── SwInfoFuncCore.java          # Facade 入口
│   ├── SwPathDetective.java         # 六级路径探测策略 (并发执行)
│   └── SwNativeOps.java             # JNA 原生操作封装 + MemoryMapIterator
├── ui/                              # UI 窗口管理
│   ├── MainWindow.java              # 主窗口 (透明 Region + WebView + 缩放手柄)
│   ├── FloatingSidebar.java         # 浮动侧栏组件
│   └── SampleWindow.java            # 示例窗口类
└── utils/                           # 工具类
    └── AvatarUtils.java             # 头像获取工具类 (本地/URL/SVG 三路回退)
```

### 开发者工具源集 (`src/tools/java`)

发布辅助工具，不进应用产物（独立 `tools` 源集，`gradle jar` 中不含 `com/jfmultichat/tools`）：

```
com/jfmultichat/tools/
└── EncryptRemoteConfigs.java        # 远程配置加密发布（复用 config.CryptoUtils）
```

**远程配置发布流程**：

| 步骤 | 操作 |
|---|---|
| 1. 维护源 JSON | 编辑 `scripts/original_remote_global_<vN>.json` / `original_remote_sw_<vN>.json` |
| 2. 加密产出 | `gradle encryptRemoteConfigs`（或 `scripts\encrypt-configs.bat`）→ 写 `remote_configs/remote_global_<vN>` / `remote_sw_<vN>` |
| 3. 更新客户端内置 URL | `RemoteConfigFetcher.BUILTIN_REMOTE_*_VERSION`（改了版本号才需要） |
| 4. 提交推送 | `remote_configs/` 随仓库发布，客户端按 main 分支 raw URL 下载 |

- 加密格式在 `config` 包内只有一份实现：`CryptoUtils.encryptAndAppendKey` / `decryptResponse`；`CryptoUtilsTest` 覆盖往返、已知向量与历史 Python 产物兼容性。
- 加密前按通用换行读取源文件（CRLF → LF），与历史 Python 版行为一致。

---

## 三、资源文件结构 (`src/main/resources/`)

```
resources/
├── logback.xml                      # SLF4J + Logback 日志配置
├── css/                             # JavaFX 桌面 CSS
│   ├── main.css                     # 主题样式 (深色)
│   ├── main-light.css               # 主题样式 (浅色)
│   └── sidebar.css                  # 侧栏专用样式
├── data/                            # 种子数据
│   └── remote_global_v1.json        # 远程配置默认种子
├── icons/                           # 应用图标
│   └── logo.png
└── web/                             # Web 前端 (HTML/CSS/JS)
    ├── index.html                   # 主页面入口
    ├── css/                         # Web CSS
    │   ├── main.css                 # 页面主样式
    │   └── theme.css                # 主题样式
    └── js/                          # JavaScript
        ├── app.js                   # 路由 + toast + 远程配置兜底
        ├── bridge.js                # JS↔Java 桥 (含异步回调 _handleAsync)
        ├── icons.js                 # SVG 图标
        ├── components/
        │   ├── nav-sidebar.js       # 侧栏导航组件
        │   └── account-table.js     # 可复用列表组件（四表架构：列定义驱动/标题行/菜单/列宽/快捷键编辑）
        └── pages/                   # 页面模块
            ├── main.js              # 主页面逻辑 (从 manage.js 复制)
            └── settings.js         # 设置页逻辑
```

---

## 四、用户数据存储路径

```
%APPDATA%/JhiFengMultiChat/{version}/
├── RootConfig.json              # 锚点配置 (代理/URL/数据目录, 永不移动)
├── UserFiles/                   # 正式版数据存储
│   ├── LocalGlobalConfig.json   # 软件偏好 (主题/窗帘状态等)
│   ├── LocalSwConfig.json       # 各平台安装配置 ({swId}: {inst_path, remark})
│   ├── SwAccData.json           # 账号数据 ({sw_id}: [{acc_id, ...}])
│   ├── SwCache.json             # 适配缓存
│   ├── RemoteGlobalConfig.json  # 远程全局配置缓存
│   └── RemoteSwConfig.json      # 远程平台配置缓存
│   └── logs/                    # 运行时日志
└── DevUserFiles/                # 开发版 (--dev) 数据存储 (同结构)
```

---

## 五、关键架构特性

### 1. 配置层架构 (三层抽象)
```
IConfigStore (接口)
  ├── getData()/setData()/reload()/save()
  ├── getSet/remove/have()/ensure()
  ↓
JsonConfigStore (实现 — Jackson ObjectNode)
  ├── getSubNode()/setSubNode()/removeSubNode()
  ├── loadFromJson()/toJson()/deepCopy()
  ↓
ConfigManager (单例统筹者)
  ├── getRootConfig() → RootConfig POJO
  ├── getGlobalConfig() → LocalGlobalConfig.json ObjectNode
  ├── getSwConfig(swId) → LocalSwConfig.json.{swId}
  ├── getRemoteGlobal() → RemoteGlobalConfig.json ObjectNode
  └── ... (访问所有 6 个 ConfigStore)
```

### 2. JS↔Java 异步架构
```
JS 调用 void Java 方法 → 立刻返回
               ↓
     ExecutorService 后台线程
     · HTTP 下载 · AES 解密 · JSON 解析
               ↓
     Platform.runLater → scriptExecutor
     → JFC.bridge._handleAsync(type, cbId, jsonStr)
               ↓
     JS 回调更新 DOM
```

### 3. 六级路径探测策略 (并发执行)
内存映射正则 > 注册表 > 猜测 > 进程 > 其他SW > DLL遍历

---

## 六、相关文档索引

| 文档 | 内容描述 |
|------|----------|
| `CLAUDE.md` | 项目总览 + 关键技术教训 (44条) |
| `MEMORY/MEMORY.md` | 各记忆文档索引摘要 |
| `MEMORY/DECISIONS.MD` | 关键决策记录 (page-main/头像重构等) |
| `MEMORY/DEV_LOGS.MD` | 开发过程笔记 (页架构迁移细节/经验教训) |
| `MEMORY/FACTS.MD` | 当前阶段事实汇总 |
| `MEMORY/TODOS.MD` | 待办任务清单 |
| `HANDOFF.md` | 交接文档 |
| `remote_sw_structure.md` | 远程结构定义 |
| `logic_filter_rules.md` | 逻辑过滤规则 |
| `handle-shape-preview.html` | Handle 形状预览 |

---

# 关键技术参考（自 AGENTS.md 第十节迁入，2026-10-05）

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
