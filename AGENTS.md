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
> 记忆系统索引: `MEMORY/MEMORY.md` ｜ 最后更新: 2026-10-06

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

### 表格（三张表共用 `JFC.AccountTable`）

- **名称列三表统一**：都用 `key='display_name'` → 复用 `.manage-nickname-cell`（可点击就地编辑 remark / 1 级色 / 15px / 字重 600 / 中英分段）。
  程序表用 `showRowActions:false` 关掉"隐藏/重置/删除"悬浮按钮（那是账号语义）
- **字体**：中文 = 微软雅黑（`--font-family-base`）、英文 = 等宽（`--font-family-mono`）；字号 `--fs-table:14px`、名称列 `--fs-name:15px`
  - **本 WebKit 做不到"一个元素里中文雅黑 + 英文等宽"**：等宽族缺中文会走系统 CJK 回退、`@font-face + unicode-range` 也不生效
    → 必须由 JS 拆段（`scriptSplitHtml()` → `.cjk-run` / `.lat-run`）。编辑框是 `<input>`，只能统一一种字体（等宽）
- **文字三级色** `--text-level1/2/3`（深色 纯白/浅灰/深灰；浅色 纯黑/深灰/浅灰）：
  普通行名称列 1 级、其它列 2 级；隐藏行（`tr.hidden-row`）整行 2 级；失效行（`tr.invalid-row`）整行 3 级
- 自绘勾选框：`.acc-check`（透明 input 只当状态载体）+ `.acc-check-box`；勾选态是**一整块填充**（`border-color: transparent`，不要用同色 border 凑）

### 账号数据约定

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

### 离线验证（`build/_probe`）

- 交互/渲染类改动用**离屏 WebView 探针**验证：真实 `index.html` + 桩桥（`StubBridge` 记录调用）+ 驱动脚本断言；需要时做**离屏像素统计**（ASCII 位图 / 颜色分类 / 形状轮廓比对）
- Java 侧逻辑用直连探针跑真实代码（如 `AccFilesProbe`）
- 边界：离屏环境**拿不到 DOM 选区**（`window.getSelection()` 恒空）→ 光标/输入法这类交互必须真机验证，别在探针里下结论

### 文档纪律

本文件**只保留**：项目身份 / 技术栈 / 结构指针 / 运行命令 / 关键约定 / 指针。其余按顶部表格分流。

## 九、指针

- 开发日志（逐次变更记录）：[`MEMORY/DEV_LOGS.MD`](MEMORY/DEV_LOGS.MD)
- 技术教训与经验结晶：[`MEMORY/LESSONS.MD`](MEMORY/LESSONS.MD)
- 事实 / 决策 / 待办：[`MEMORY/FACTS.MD`](MEMORY/FACTS.MD) ｜ [`MEMORY/DECISIONS.MD`](MEMORY/DECISIONS.MD) ｜ [`MEMORY/TODOS.MD`](MEMORY/TODOS.MD)
- 架构与目录细节：[`docs/project_structure.md`](docs/project_structure.md)
- 设置区域"窗帘"改造前的实现存档：[`MEMORY/ARCHIVE_settings_curtain_animation.md`](MEMORY/ARCHIVE_settings_curtain_animation.md)
