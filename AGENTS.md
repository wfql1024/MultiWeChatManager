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
> 记忆系统索引: `MEMORY/MEMORY.md` ｜ 最后更新: 2026-10-07

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

> `run` 任务目前带一个**试验开关** `-Dprism.lcdtext=false`（关掉 LCD 次像素抗锯齿，中文观感更干净：
> 实测边缘对比度 51.3→53.5、彩色边缘占比 97%→0%）。保留与否待定，见 `MEMORY/TODOS.MD`。

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

### 启动与多开（互斥体 + 降权）

- **一句话**：点程序表"登录"（或**双击最左栏平台图标**）= **查杀该平台全部互斥体/文件锁 → 以普通用户权限启动平台程序** → 每次点击都新开一个登录窗口
- **互斥体查杀**：`WinHandleOps`（纯 JNA，不依赖外部 handle.exe）—— `NtQuerySystemInformation(SystemExtendedHandleInformation)` 枚举系统句柄 → 只挑目标 PID → `DuplicateHandle(SAME_ACCESS, 目标=当前进程)` + `NtQueryObject` 取名字/类型 → 名字按 Python 规则匹配（`fnmatch(name,wc) || fnmatch(name,"*"+wc+"*")`）→ `DuplicateHandle(..., DUPLICATE_CLOSE_SOURCE)` 在目标进程里关闭；**先全部找完再统一关闭**
  - 入口：`SwOperatorCore.killAllMutexesNow` / `tryKillMutexIfNeededAndReturnRemainedPids` / `AccOperatorCore.killMutexOfAcc`
  - **"已查杀 PID"全局缓存**（`KILLED_PID_AT`，10s TTL）→ 刚清干净的 PID 不再进枚举（实测 931ms → 0ms）
- **降权启动**：`SwNativeOps.createProcessWithoutAdmin` —— **先判断自己是否管理员**：非管理员 → 直接 `CreateProcess`（子进程天然普通权限）；管理员 → 借 explorer 令牌（`GetShellWindow` → `OpenProcessToken(TOKEN_DUPLICATE)` → `DuplicateTokenEx` → `CreateProcessWithTokenW`）；令牌法失败 → 兜底 `explorer.exe` 代启（返回 `-1` = 已启动但 PID 未知）
  - ⚠️ 路径要转成反斜杠再喂给 `CreateProcess*`（项目内部路径是 `/`）
- **桥 / 前端**：`JsBridge.launchPlatformProgram(swId, count)`（循环 count 次「查杀 → 启动」）；`main.js` 的 `launchPlatformProgram` 是**唯一来源**，程序表按钮与图标双击都走它

### 交互约定（点击 / 通知）

- **平台项点击**：统一窗口 `CLICK_WINDOW_MS = 250`。单击当前平台 = 刷新；单击别的平台 = **等窗口后切换**（让双击来得及撤销）；**双击 = 启动该平台程序且不切换**；**三击及以上 = 取消双击效果**。连击计数记在**模块变量**里 —— 不能用 `e.detail`（切平台会重建侧栏 DOM，第二次点击 `detail` 从 1 重来）
- **通知**：成功→ `JFC.toastSuccess`（右下角、**无关闭按钮**、`toast-out` 渐隐后自动移除）；失败→ `JFC.modal`（需要用户注意）

### 表格（三张表共用 `JFC.AccountTable`）

- **平台页两种形态**：`pageMode = 'login'`（默认）/ `'manage'`，右上角二元滑块按钮切换；模式是**会话内变量**（不写配置、不按平台记忆），未设置完备的平台会被强制管理态
- **表顺序**：程序 / 共存账号 / 原生账号（共存是主推）；**空表不显示**
- **列定义属性**（一切行为由属性驱动，代码不按 key 特判）：
  `key / label / mandatory / pinned / sortable / sortType / loginOnly / defVisible / defWidth / fixed / cellClass`
  - **`sortable` 默认 `true`**（构造时补默认值；只有勾选框/头像显式 `false`）
  - `pinned`（勾选框/头像/名称）= 固定最左、不可拖动换序，**但可以排序**
  - `loginOnly`（pid/hwnd）= 只在登录态出现；**非必显**，默认显示、用户可自由隐藏（个性化入档）
- **三表差异收口**：`rowKind`（`'acc'` / `'prog'`）+ `rowActionsOf(kind, mode, ctx)` 一处来源，供名称列按钮 / 右键菜单 / 批量按钮共用
- **名称列三表统一**：都用 `key='display_name'` → 复用 `.manage-nickname-cell`（可点击就地编辑 remark / 1 级色 / 15px / 字重 600 / 中英分段）
- **列交互**：短按列头 = 排序（▲/▼ 紧贴列名、与列名同色，不做着色加粗）；按下后移动 >4px = **拖动换序**（两阶段：阶段一**列头与列内容一起**用 `transform` 位移滑动、元素全留在表格流里、**零布局影响**；阶段二松手写回顺序 + 重建列头 + 整表重刷；落点只认**初始槽位**，不能用实时布局）；右边缘 = 调宽
- **列个性化（写 `account_columns.<表id>`）**：`visible` / `width` / `order`（列顺序）/ `hideColNamesInLogin`（= 登录模式下整行列头隐藏）
- **列显隐归属**：管理模式显示全部列（除登录态专列）、菜单里没有"显示列"；"显示列"勾选区只在登录态提供
- **程序表**：**没有 PID/HWND 列**（程序只是启动器，不算具体账号）；`version` 非必显；"登录"左边有 `× __` 实例数量输入框（`×` 是静态前缀删不掉，1 位、留空 = 1、空白灰显 `1`、样式与相邻按钮同字号同行高）
- **全选框**：统一在表格标题行、**表名左侧**，与数据行勾选框**同款**（`.acc-check` 基类不再限定表格作用域）且水平位置由 `_syncSelectAllPosition()` **运行时实测对齐**（不靠算术）
- **字体**：中文 = 微软雅黑（`--font-family-base`）、英文 = 等宽（`--font-family-mono`）；字号 `--fs-table:14px`、名称列 `--fs-name:15px`
  - **本 WebKit 做不到"一个元素里中文雅黑 + 英文等宽"**：等宽族缺中文会走系统 CJK 回退、`@font-face + unicode-range` 也不生效
    → 必须由 JS 拆段（`scriptSplitHtml()` → `.cjk-run` / `.lat-run`）。编辑框是 `<input>`，只能统一一种字体（等宽）
- **文字三级色** `--text-level1/2/3`（深色 纯白/浅灰/深灰；浅色 纯黑/深灰/浅灰）：
  普通行名称列 1 级、其它列 2 级；隐藏行（`tr.hidden-row`）整行 2 级；失效行（`tr.invalid-row`）整行 3 级
- 自绘勾选框：`.acc-check`（透明 input 只当状态载体）+ `.acc-check-box`；勾选态是**一整块填充**（`border-color: transparent`，不要用同色 border 凑）
  → 推广到所有"要填满"的元素（按钮/滑块/色块）：**border 要么不加、要么透明**

### 账号数据约定

- **PID / HWND 只存内存**（不落配置文件）：Java `AccRuntimeStore`（`swId → accId → {pid, hwnd}`）+ 前端 `accRuntimeMap`；进平台时经 `JFC.bridge.getAccRuntimeMap` 取一次，Java 维护完成后由 `PlatformEventBootstrap` 推送（`pid` / `main_hwnd` 字段）；配置里历史遗留的 `pid`/`main_hwnd` 会被写 null 清掉。两列只在登录态出现、非必显
- **失效账号**由 `main.js` 推导：`SwAccData` 里有记录、但**不在 `getSwExistedAccounts` 列表里** → 并入对应表置底 + 3 级灰 + "失效"标签
- **`origin_exe` 不是账号**：它是 `SwAccData.<sw>.origin_exe` 里"原生程序自己的备注"节点，**所有遍历账号的地方都必须排除它**
  （`JsBridge.getSwDetailData` / `getAccountList`、`AccConfigAccessor.getAllAccounts`、两处"取第一个账号"的退化路径）
- **名称链**：账号 = `remark > nickname > alias > id`；原生程序 = `origin_exe.remark > 平台名称`；平台名称 = 本地 `remark` > 远程 `alias` > `swId`
- **删除 vs 重置**：删除 = 节点整体移除；重置 = 清空节点内容但**保留空节点**。两者都要 `AccInfoFuncCore.deleteAccountAvatarFiles()` 清 `{userData}/{sw}/{acc}/` 下的头像文件
  （只清图片、保留非图片、只删空目录）；平台图标 `{userData}/{sw}/{sw}.png` 不受影响
- **批量删除只对失效账号生效**：确认框照常弹、文案说明"正常账号无法删除/将被跳过"，**执行层**才过滤（按钮点了没反应比弹窗说明更糟）
- 行右键菜单三项齐全（隐藏/重置/删除），不能做的**显示为禁用**（禁用项仍要带 `data-row-action`）

### 交互组件

- 弹窗一律用 `JFC.modal.confirm` / `JFC.modal.custom`（`window.confirm` 在本 WebView 里恒返回 false、`alert` 是空操作）
- 快捷键录入：松手即确认；只有修饰键或普通键多于一个 → 回退原值；Backspace 清空、Esc 放弃、**Enter 忽略**、Tab 可录
- 就地编辑：单元格 HTML 只由 `nameCellInnerHtml()` 产出；提交后**延后一拍**再保存 + 整表重排（避免 mousedown 阶段重建 tbody 让点击落空）

### 离线验证（`build/_probe` —— ⚠️ 现已被 `gradle clean` 清空）

- 交互/渲染类改动用**离屏 WebView 探针**验证：真实 `index.html` + 桩桥（`StubBridge` 记录调用）+ 驱动脚本断言；需要时做**离屏像素统计**（ASCII 位图 / 颜色分类 / 形状轮廓比对）
- Java 侧逻辑用直连探针跑真实代码（如 `AccFilesProbe`）
- 边界：离屏环境**拿不到 DOM 选区**（`window.getSelection()` 恒空）→ 光标/输入法这类交互必须真机验证，别在探针里下结论
- **临时文件放项目根的 `tmp/`**（已 gitignore，可随时删）；**不要放 `build/`** —— 它是构建产物目录，`gradle clean` 会整个清空（**探针源码就是这么丢的**：原先都在 `build/_probe/`，且未纳入版本控制 → 重建探针请放 `tmp/`）

### 文档纪律

本文件**只保留**：项目身份 / 技术栈 / 结构指针 / 运行命令 / 关键约定 / 指针。其余按顶部表格分流。

## 九、指针

- 开发日志（逐次变更记录）：[`MEMORY/DEV_LOGS.MD`](MEMORY/DEV_LOGS.MD)
- 技术教训与经验结晶：[`MEMORY/LESSONS.MD`](MEMORY/LESSONS.MD)
- 事实 / 决策 / 待办：[`MEMORY/FACTS.MD`](MEMORY/FACTS.MD) ｜ [`MEMORY/DECISIONS.MD`](MEMORY/DECISIONS.MD) ｜ [`MEMORY/TODOS.MD`](MEMORY/TODOS.MD)
- 架构与目录细节：[`docs/project_structure.md`](docs/project_structure.md)
- 设置区域"窗帘"改造前的实现存档：[`MEMORY/ARCHIVE_settings_curtain_animation.md`](MEMORY/ARCHIVE_settings_curtain_animation.md)
