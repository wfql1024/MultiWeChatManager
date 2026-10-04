# AGENTS.md — JhiFengMultiChat（极峰多聊）

> **本文件只写"项目当前状态的全局视图"：不写历史、不写细节、不写教训。**
> 判断标准：**"这是现在是什么样，还是曾经发生了什么？"**
>
> | 要写的内容 | 去处 |
> |---|---|
> | 变更过程 / 开发日志 | `MEMORY/DEV_LOGS.MD` |
> | 踩坑与技术教训 | `MEMORY/LESSONS.MD` |
> | 当前事实 / 决策记录 | `MEMORY/FACTS.MD` / `MEMORY/DECISIONS.MD` |
> | 待推进事项 | `MEMORY/TODOS.MD` |
> | 架构与目录细节 | `docs/project_structure.md` |
>
> 记忆系统索引: `MEMORY/MEMORY.md` ｜ 最后更新: 2026-10-05

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

## 八、关键约定（改代码前必读）

### 配置分层与命名

| 文件 | 放什么 |
|---|---|
| `RootConfig.json` | 代理 / 远程配置源（**不随用户数据目录迁移**） |
| `LocalGlobalConfig.json` | 软件偏好：`theme` / `account_columns` / `last_sw_id` / `settings_height` / `settings_expanded` |
| `LocalSwConfig.json` | 每平台配置（路径、备注、快捷键、`icon_src_path`…） |
| `SwAccData.json` | 每平台账号详情（展示名、隐藏/禁用、`linked_acc`…） |
| `RemoteGlobalConfig.json` / `RemoteSwConfig.json` | 远程下发的平台定义（加密存储） |

- 文件名一律双驼峰 PascalCase；用户数据目录内的子目录用 PascalCase（`UserFiles` / `DevUserFiles`）
- `saveGlobalConfig` 是**顶层浅合并**：写嵌套对象（如 `account_columns`）必须先读出来再合并；**JSON `null` 表示删除该字段**
- 配置类每次 `getData()` 都会从磁盘 reload，读写锁保证并发安全

### 新增一条"账号字段更新"操作的标准路径（EventBus 流B）

1. Java 侧写库后 `EventBus.getInstance().publish(new AccountDataChangedEvent(swId, accId, changedMap))`
2. `main.js` 的 `onAccountChanged(payload)` 按 `payload.changed` 的字段**定向更新对应单元格**（不整表重渲染；未知字段忽略、保持幂等）
3. 装配已就绪（`PlatformEventBootstrap.install`），无需额外注册

### JS ↔ Java 桥

- 桥方法用**固定参数**（JavaFX 桥不支持 varargs）；路径等复杂参数用 JSON 字符串传递
- 耗时操作必须后台线程 + `Platform.runLater` → `executeScript`；Java 主动推送用 `pushToJs`
- 推送对象必须**双编码**为 JS 字符串字面量（`_handleAsync` 只解析字符串），布尔值前端用 `=== true` 严格比较
- 页面元素查询走 `getEl(id)`（`#page-main` 作用域优先，再回退全局）

### 前端渲染原则

- **一个状态的渲染只允许一个写入点**；状态变更先落到"事实来源"（配置文件 / 记录），再统一渲染
- 表格：`table-layout: fixed` + colgroup 决定列宽；**隐藏列的 `<col>` 必须同时归零**；表格宽度 = 可见列宽总和 + 占位列
- 单元格不要设 `display:flex`（会破坏 table-cell）；需要 flex 就在内层加元素
- 行悬浮/选中着色用绝对定位色块层 + **不透明等效色**，靠 `isolation: isolate` 控制层叠

### 文档纪律

本文件**只保留**：项目身份 / 技术栈 / 结构指针 / 运行命令 / 关键约定 / 指针。其余按顶部表格分流。

## 九、指针

- 开发日志（逐次变更记录）：[`MEMORY/DEV_LOGS.MD`](MEMORY/DEV_LOGS.MD)
- 技术教训与经验结晶：[`MEMORY/LESSONS.MD`](MEMORY/LESSONS.MD)
- 事实 / 决策 / 待办：[`MEMORY/FACTS.MD`](MEMORY/FACTS.MD) ｜ [`MEMORY/DECISIONS.MD`](MEMORY/DECISIONS.MD) ｜ [`MEMORY/TODOS.MD`](MEMORY/TODOS.MD)
- 架构与目录细节：[`docs/project_structure.md`](docs/project_structure.md)
- 设置区域"窗帘"改造前的实现存档：[`MEMORY/ARCHIVE_settings_curtain_animation.md`](MEMORY/ARCHIVE_settings_curtain_animation.md)
