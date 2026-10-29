# facts — 当前事实 · 功能手册

> **用途**：给开发者（用户）与 Agent **定位** —— "我要改 X，该去哪个文件/哪个功能块"。
> **不写什么**：不写历史（去 `dev_logs.md`）、不写为什么这么定（去 `decisions.md`）、不写踩过的坑（去 `lessons.md`）、不写架构细节（去 `docs/project_structure.md`）。
> **更新方式**：**就地重写** —— 它是"现在是什么样"的快照，不追加、不留旧版本。始终与代码保持一致。

---

## 1. 代码结构地图

### 1.1 入口链
```
Launcher.main                        ← 应用入口（设日志目录/编码 → 初始化 ConfigManager → 应用代理 → 启动 JavaFX）
└─ MainApp (JavaFX Application)      ← 建窗、注入 JS 桥
   └─ MainWindow                     ← Stage/WebView 宿主；setupWebView() 里关掉了 WebView 自带右键菜单
      └─ WebView 加载 web/index.html
         └─ js/app.js → js/router.js → js/pages/main.js → js/components/account-table.js
```

### 1.2 后端包职责（`src/main/java/com/jfmultichat/`）

| 包 | 分管 |
|---|---|
| `Launcher` / `MainApp` / `ui/` | 入口与 JavaFX 窗口宿主（`MainWindow`：Stage、WebView、JS 注入、上下文菜单开关） |
| `bridge/` | **JS ↔ Java 桥**（`JsBridge` 是所有前端调用的落点；`pushToJs` 反向推送） |
| `config/` | 配置读写（`ConfigManager` 单例）、路径规范（`AppPaths`）、环境（`AppEnv`）、远程配置抓取与解密（`RemoteConfigFetcher`、`CryptoUtils`）、根配置模型（`RootConfig`） |
| `core/` | 通用基础设施：自建 **EventBus** + 事件类型 + `PlatformEventBootstrap`（把后端变化推给前端） |
| `core/task/` | **任务中心内核**（长耗时流程的可见性/取消/统计，见 §2.6）：`JfTask`、`TaskContext`、`TaskRegistry`、`TaskStats`、`TaskJfrEvent`、`TaskCancelledException` |
| `acccore/` | **账号层**：账号信息/配置状态/头像/登录（`AccInfoFuncCore`、`AccOperatorCore`、`AccConfigAccessor`、`AccRuntimeStore`、`AvatarUtils`） |
| `appcore/` | **平台/应用层**：平台定义与适配（`AppCore`、`AppConfigAccessor`、`SwAdapterChecker` 适配判断） |
| `swcore/` | **平台程序操作层**：启动/降权（`SwNativeOps`、`SwOperatorCore`）、窗口与句柄（`SwInfoFuncCore`、`WinHandleOps`、`UiaOps`）、平台配置访问（`SwConfigAccessor`、`SwConfigProvider`）、常量（`SwCoreConstants`） |
| `setting/` | 设置页后端逻辑 |
| `model/` | 数据模型 |
| `utils/` | 工具（日志、文件、图片等） |

### 1.3 前端结构（`src/main/resources/web/`）

| 文件 | 分管 |
|---|---|
| `js/app.js` | 启动、全局工具、路由装配、右键事件合成（见 §2.1） |
| `js/router.js` | 页面切换 + 刷新冷却 + 顶部进度条 |
| `js/bridge.js` | 桥的 JS 侧封装（含 `_handleAsync` 回调分发） |
| `js/pages/main.js` | **平台页主逻辑**（渲染三张表、平台/账号操作、设置区域、登录与多开入口） |
| `js/components/account-table.js` | **三张表共用的表格组件**（列系统、排序、列换序/调宽、行操作、批量、就地编辑、右键菜单） |
| `js/components/*` | 其他组件（弹窗 `modal`、toast、图标等） |
| `js/components/task-center.js` | **任务中心面板**（右上角抽屉：三小栏 + 取消 + 「查看更多」，见 §2.6） |
| `js/pages/tasks.js` | **「任务与统计」页**（`#page-statistics`：统计卡 + 三小栏 + 明细表） |
| `css/main.css` | 全部样式（含文字三级色、勾选框、表格、窗帘动画） |
| `css/task-center.css` | 任务中心面板 + 任务与统计页的样式 |

---

## 2. 功能手册

### 2.1 入口界面

- **最左栏（`#nav-sidebar`）**：平台列表（动态渲染）+ 底部统计/设置入口。由 `main.js` 渲染。
  - **点击策略**（统一窗口 **250ms**）：单击当前平台 = 刷新；单击别的平台 = **等窗口后切换**；**双击 = 启动该平台程序（不切平台）**；**三击及以上 = 取消双击效果**。连击计数记在**模块变量**（不能用 `e.detail`：切平台会重建侧栏 DOM）
- **主内容区（`#page-main`）**：唯一主内容区，无内嵌左栏；元素查询走 `getEl(id)`（作用域隔离）
- **标题区**：只显示平台名称；右侧有 SVG 刷新按钮（→ `router.refresh()`，2s 冷却 + 进度条最小显示 400ms）
- **右键**：Java 侧 `webView.setContextMenuEnabled(false)`（为去掉"重新加载页"）→ **DOM 的 `contextmenu` 不再派发** → `app.js` 用 `mousedown(button===2)` **合成** `contextmenu` 补上
- **通知**：成功 → `JFC.toastSuccess`（右下角、**无关闭按钮**、`toast-out` 渐隐后自动移除）；失败 → `JFC.modal`

### 2.2 平台界面（登录态 = 默认）

平台页有**两种形态**：`pageMode = 'login'`（默认）/ `'manage'`，右上角二元滑块切换。模式是**会话内变量**（不写配置、不按平台记忆）；未设置完备的平台会被强制管理态。

#### 2.2.1 三张表

| 表 | 内容 | 备注 |
|---|---|---|
| 程序表 | 平台自身 | **没有 PID/HWND 列**（程序只是启动器）；`version` 非必显；"登录"左边有 `× __` 数量输入框（1 位、留空 = 1、空白灰显 `1`） |
| 共存账号表 | 共存账号（主推） | 列 = 原生账号列 + 最后登录账号等 |
| 原生账号表 | 原生账号 | 列 = 原生账号列 + **"配置"列**（见 §2.2.3） |

- **表顺序**：程序 / 共存 / 原生；**空表整表不显示**
- **三表差异收口**：`rowKind`（`'acc'` / `'prog'`）+ `rowActionsOf(kind, mode, ctx)` 一处来源 → 名称列按钮 / 右键菜单 / 批量按钮共用
- **失效账号**（`SwAccData` 有记录但不在 `getSwExistedAccounts` 列表里）：并入后两张表、**置底**、整行 3 级灰 + "失效"标签

#### 2.2.2 列系统

- **列定义属性**（一切行为由属性驱动，代码不按 key 特判）：
  `key / label / mandatory / pinned / sortable / sortType / loginOnly / defVisible / defWidth / fixed / cellClass`
  - `sortable` **默认 true**（勾选框/头像显式 `false`）
  - `pinned`（勾选框/头像/名称）= 固定最左、不可拖动换序，**但可以排序**
  - `loginOnly`（pid/hwnd/配置）= 只在登录态出现；**非必显**，默认显示、用户可隐藏
- **列顺序**：`TABLE_COLUMNS.coexist = TABLE_COLUMNS.account.concat([...])` —— **加到 account 基表会泄漏到共存表**（所以"配置"列单独挂在原生账号表的 columns 上）
- **交互**：短按列头 = 排序（▲/▼ 紧贴列名、同色）；按下移动 >4px = **拖动换序**（两阶段：阶段一列头+列内容一起 `transform` 位移、零布局影响；阶段二松手写回 + 重建列头 + 整表重刷；落点只认**初始槽位**）；右边缘 = 调宽
- **列个性化**（`LocalGlobalConfig.json` → `account_columns.<表id>`）：`visible` / `width` / `order` / `hideColNamesInLogin`（登录模式下整行列头隐藏）
- **显隐归属**：管理态显示全部列（除登录态专列）、菜单里没有"显示列"；"显示列"勾选区只在登录态提供
- **全选框**：在**表格标题行、表名左侧**，与行内勾选框同款（`.acc-check` 基类不限定表格作用域），水平位置由 `_syncSelectAllPosition()` **运行时实测对齐**
- **字体**：中文微软雅黑 + 英文等宽 → 由 JS 拆段（`scriptSplitHtml()` → `.cjk-run`/`.lat-run`）；字号 表内 14px、名称列 15px；编辑框是 `<input>`，只能统一等宽
- **文字三级色**：`--text-level1/2/3`（深色 纯白/浅灰/深灰）→ 普通行名称 1 级/其它 2 级；隐藏行整行 2 级；**失效行与 `no_cfg` 行整行 3 级**
- **勾选框自绘**：`.acc-check`（透明 input 只当状态载体）+ `.acc-check-box`；勾选态 = **一整块填充**（`border-color: transparent`）

#### 2.2.3 数据来源与两类账号

- **PID / HWND**：**只存内存** —— Java `AccRuntimeStore`（`swId → accId → {pid, hwnd}`）+ 前端 `accRuntimeMap`；进平台时经 `JFC.bridge.getAccRuntimeMap` 取一次，维护完成后由 `PlatformEventBootstrap` 推送；配置里历史遗留的 `pid`/`main_hwnd` 会被写 `null` 清掉
- **`origin_exe` 不是账号**：它是 `SwAccData.<sw>.origin_exe` 里"原生程序自己的备注"节点 → **凡遍历账号的地方都必须排除它**（`JsBridge.getSwDetailData`/`getAccountList`、`AccConfigAccessor.getAllAccounts`、两处"取第一个账号"的退化路径）
- **名称链**：账号 = `remark > nickname > alias > id`；原生程序 = `origin_exe.remark > 平台名称`；平台名称 = 本地 `remark` > 远程 `alias` > `swId`
- **账号列表来源** = **磁盘扫描**（`getSwExistedAccounts`）
- **"配置"列**（原生账号表）：值 = 该账号自己的登录配置文件（`{config_dir}/{account}_{平台配置文件名}`，**同时认旧命名** `{account}.{ext}`）的修改时间，没有 = `no_cfg`；**实时按文件判断、不入 `SwAccData`**
- **`no_cfg` 行规则**（登录态）：整行三级灰 + **不渲染勾选框**（平时/悬浮都不显示）+ 行点击不选中 + 全选跳过 + 右键"登录"禁用 + 置底 → **批量登录天然不会带上它们**
- **头像**：`{用户数据目录}/{swId}/{accId}/{accId}.jpg`；平台图标 `{用户数据目录}/{swId}/{swId}.png`（64×64，来源记在 `LocalSwConfig.<sw>.icon_src_path`）

#### 2.2.4 行操作与批量

- **行操作来源**：`rowActionsOf(kind, mode, ctx)` → 名称列悬浮按钮 / 右键菜单 / 批量按钮
- **登录**：账号行"登录"（原生账号）/ 批量登录 / 程序表"登录"（开 N 个实例）
- **隐藏 / 重置 / 删除**：删除 = 节点整体移除；重置 = 清空内容保留空节点；**两者都清该账号的头像文件**（只清图片、保留非图片、只删空目录）；**批量删除只对失效账号生效**（确认框照常弹、执行层过滤）
- **名称就地编辑**：单元格 HTML 只由 `nameCellInnerHtml()` 产出；提交后**延后一拍**再保存 + 整表重排
- **快捷键录入**：松手即确认；只有修饰键或普通键多于一个 → 回退原值；Backspace 清空、Esc 放弃、**Enter 忽略**、Tab 可录
- **账号区滚动**：滚轮**真的改变 `scrollTop`** → 自动收起设置区（未启用平台只收起不记录）

#### 2.2.5 多开与登录

- **多开**（程序表"登录" / 双击最左栏图标）：`JsBridge.launchPlatformProgramAsync(swId, count, cbId)` —— 后台线程里 **先查杀一次 → 再同时唤起 N 个**（避免"先开一个再杀一个"的竞态）；启动成功 toast、失败弹窗
  - **toast 不提权限字样**（用户 2026-10-13）：只说"正在启动 N 个实例 / 已启动 N 个实例" ——
    降权启动是本项目**正常流程**，不给用户额外信息（前端三处已清：`main.js` 启动中/结果 toast、`account-table.js` 同步兜底）
  - **单个实例启动**：`SwOperatorCore.launchOneInstance(sw, exe, accessor, ops[, skipKill])` —— **默认内化查杀**；`skipKill=true` 供"先杀一次、再连开 N 个"
  - **降权启动**：`SwNativeOps.createProcessWithoutAdmin` —— 非管理员直接 `CreateProcess`；管理员借 explorer 令牌（`CreateProcessWithTokenW`）；失败兜底 `explorer.exe` 代启（返回 `-1`）
- **原生账号登录**：`AccOperatorCore.loginOrigin`（入口：账号行"登录"/批量登录 → `main.js.loginAccounts` → `JsBridge.loginAccountsAsync`）
  1. **替换该账号的登录配置**（`operateAccConfig("use")` = 账号配置 → 平台配置）
  2. 开登录窗（含查杀互斥体）
  3. **预摆位**：开窗前按账号总数算好格子（`login_size` 优先，兜底 屏幕/6 × 屏幕/3），窗口一出现立刻挪到位；**失败/超时的格子空着、不重排**
  4. 全部打开并摆位后**才统一点击**"登录"（后台 `PostMessage`；比例取远程 `auto_click.login_btn.location`，默认 0.5/0.75）
  5. 等所有登录窗关闭（**20 秒**上限，收尾观察用；可取消）。**任何单个账号失败都不中断整批**
  - 前端只做 **2 秒防连点**；整条流程**登记为任务**（kind `login`）→ 右上角任务中心可见/可取消、自动进统计（见 §2.6）
- **共存账号登录**（已实现）：`AccOperatorCore.loginCoexist`（入口：共存账号表行"登录"/批量/快捷键 → `main.js.loginCoexistAccounts` → `JsBridge.loginCoexistAccountsAsync`）
  - **与原生登录的唯一实质差异：不替换、也不读登录配置**（没有 `operateAccConfig`）——
    共存账号 id **本身就是程序目录下的副本 exe 名**，直接 `openSwAndReturnHwnd(sw, accId, …)` 按它启动即可
    （照旧版 `_open_acc_return_hwnd_and_pid` 的共存分支：`open_sw(sw, exe=acc)`，注释原文"共存账号无需替换配置文件"）
  - 其余**完全复用**原生那套：预摆位、一出现就挪位、全部开完统一点击、等窗口关闭 20s、取消检查点、同一统计口径
  - 任务 kind = **`login_coexist`**（统计页单列一张卡，口径与 `login` 相同）
  - 前端分流开关：表选项 **`accType`**（`'origin'` / `'coexist'`，`main.js` 建表时给共存表传 `'coexist'`）→
    `account-table._loginAccounts` 按它决定走 `loginAccounts` 还是 `loginCoexistAccounts`（批量/单行/快捷键三条路径共用）
- **登录窗口尺寸**：`SwOperatorCore.getLoginSize`（格式 `宽*高`）；没有登录窗会**自动开一个**、量完 `WM_CLOSE` 关掉；设置区"获取"按钮 → `JsBridge.fetchLoginSize` → 存**本平台本地配置** `login_size`（**不是**远程配置）

#### 2.2.6 互斥体查杀与窗口/句柄核心

- **互斥体查杀**：`WinHandleOps`（纯 JNA，不依赖外部 handle.exe）—— `NtQuerySystemInformation(SystemExtendedHandleInformation)` 枚举系统句柄 → 只挑目标 pid → `DuplicateHandle(SAME_ACCESS, 目标=当前进程)` + `NtQueryObject` 取名字/类型 → 名字按 Python 规则匹配（`fnmatch(name,wc) || fnmatch(name,"*"+wc+"*")`）→ `DuplicateHandle(..., DUPLICATE_CLOSE_SOURCE)` 关闭；**先全部找完再统一关闭**
  - 入口：`SwOperatorCore.killAllMutexesNow` / `tryKillMutexIfNeededAndReturnRemainedPids` / `AccOperatorCore.killMutexOfAcc`
  - **句柄名查询带 300ms 超时**（`ObjectNameInformation` 在**命名管道**上会阻塞）
  - **"已知无互斥体 PID"长期缓存**（软件生命周期；成功开出新窗口即登记"启动前那些 pid"，**读取侧真过滤**）
  - **builtin / freely**：`freely` = 程序目录 DLL 打过补丁（不创建互斥体）→ 无需查杀。现判定：**配置显式写 `freely_multirun` 才跳过**，其余按 builtin。**补丁状态探测待接入**（`SwAdapterChecker`，须按平台缓存）
- **取句柄核心**：`SwInfoFuncCore.getHwndsOfSwByWndType(sw, 类型)` = 平台 pid → 各 pid 顶层窗口 → 按 `wnd_class.<类型>.matching` 规则筛选（**唯一命中**才算）；`getLoginHwndsOfSw` / `getMainHwndsOfSw` / `getHwndsByPidAndWndType` / `waitHwndExclusivelyForPid` 共用它
  - 规则键：`ClassNameWildcards`（`fnmatch`：`* ? [seq]`）、`Name`/`Title`、`ProcessId`/`PID`、`OR*` 子规则、`!` 取反；**`FinalSelect` 尾筛**（`Size/Width/Height` × `Extreme|End(max/min)/Equals/Greater/Less`）多命中时选唯一
  - **两趟匹配**：Win32 类名先扫；**整条规则一个都没命中**时才用 **UIA 类名**兜底（`UiaOps`：纯 JNA COM 调 `UIAutomationCore.dll`，实例 ThreadLocal 复用）
  - **等窗口**：`waitHwndExclusivelyForPid` **只对"新出现"的窗口**做规则匹配

### 2.3 平台界面（管理态 = 多出的部分）

- **设置区域**（登录态隐藏，但**记录不动**）：高度/展开由 `settings_height` / `settings_expanded` 驱动，唯一渲染入口 `applyCurtainRender()`；**未启用平台**（三路径非全绿）每次渲染强制展开且不写记录
- **路径绿框**：`validatePathInput` → `JFC.bridge.checkPath` → 写 `input-ok/warn/error` 类 + `swPathGreen[swId][key]`；窗帘只读它
- **行操作增多**：隐藏/重置/删除、就地编辑名称与快捷键、批量操作（登录态按钮只剩"登录/批量登录"）

### 2.4 设置界面

- 设置区域内的各子项：路径探测、日志、代理、远程配置源等（详见 `docs/project_structure.md` 与 `setting/` 包）
- **三块配置独立保存**（改哪块存哪块）

### 2.5 全局设置项（`LocalGlobalConfig.json`）

`theme` / `account_columns` / `last_sw_id` / `settings_height` / `settings_expanded`（历史遗留如 `manage_settings_*`、`_alias` 已在加载时清理）

### 2.6 任务中心与统计（`core/task/` + 前端两处入口）

**定位**：所有**长耗时流程**（账号登录、批量多开…）统一登记，做到"看得见、叫得停、有统计"。核心约定：**统计与任务中心同源** —— 任务的启停边界天然就是计时区间，业务代码里**零计时、零写盘**。

#### 2.6.1 内核

| 类 | 职责 |
|---|---|
| `TaskRegistry`（单例） | `submit(kind, title, target, Runnable/Consumer)` 登记并跑在**自己的 daemon 池**；`list()` / `cancel(id)` / `cancelAll()`；`addListener(...)` 变化订阅；已完成保留 **300** 条后淘汰最旧 |
| `JfTask` | 状态机 `RUNNING → CANCELLING → CANCELLED / DONE / FAILED`（`zh()` 出中文）；字段 id/kind/title/target/startedAt/finishedAt/phase/phaseBase/phaseSuffix/done/total/error/`phaseMs`/`metrics`；`toMap()` 给前端 |
| `TaskContext` | 挂在 **ThreadLocal** 上 → **业务方法签名一律不用改**；静态入口：`checkpoint()` / `phase(显示[,统计键])` / `phaseSuffix()` / `progress()` / `metric()` / `metricSet()` / `step(name, Runnable)`；不在任务里时全部退化成无操作 |
| `TaskCancelledException` | 取消时抛出 → 一路弹回任务边界，**只在 `TaskRegistry` 里 catch 一次** → 标 `CANCELLED`（不是 FAILED） |
| `TaskStats` | 任务结束时记一条 → 内存按 kind 聚合 + `{用户数据目录}/stats/task_stats.jsonl` |
| `TaskJfrEvent` | JFR 事件 `com.jfmultichat.TaskRun`（kind/sw/result/durationMs/lastPhase），任务结束 `commit()` |

#### 2.6.2 取消语义（协作式）

- Java **没有安全的强制杀线程**：取消 = 置标志 + `interrupt()`，流程跑到**安全检查点**才停
- **已做的动作不回滚**（已开的窗口保留，用户手动关）；**不再继续**后面的步骤
- 安全点位置：`loginOrigin` 每账号开头/点击每个窗口前、`waitHwndExclusivelyForPid` 与 `waitHwndsClose` 的轮询内、批量多开每轮、`WinHandleOps.findHandles` 每个候选句柄前
- native 段无法中断 → 靠各自超时兜（句柄名 300ms、互斥体查杀总预算 `DEFAULT_KILL_BUDGET_MS = 5000`、**UIA 800ms + 连续 3 次超时熔断 60s**）

#### 2.6.3 统计口径（用户 2026-10-12 定，取代"总时长÷应开窗数"）

- 流程上报两个**覆盖式**指标（`metricSet`，取消也保留）：
  - `login`：`开窗轮次`（开窗循环进行到第几个，成功/失败/超时/中途取消都算一轮）+ `开窗时长ms`（从开始到**最后一次成功开窗**）
  - `login_coexist`：同 `login`（共存登录单列一张统计卡）
  - `multilaunch`：`开实例数`（实际发起启动次数）+ `多开时长ms`（到最后一次成功启动）
- `TaskStats` 的 `DERIVED` 表声明 `kind → {时长键, 轮次键}`，据此给出：
  - **总平均** = Σ时长 ÷ Σ轮次；**单次三项** = 末次 / 最短 / 最长（每次运行的"时长÷轮次"）
  - `PER_UNIT_CAP_MS` **异常样本上限**：login/multilaunch 60s、refresh 2s，超限的整条丢弃（对齐旧版 `StatisticData`）
- 每个指标的聚合 = `{sum, count, avg, min, max}`；各**阶段耗时**由 `TaskContext.phase()` 自动结算上一阶段（同阶段名累加，统计键不带序号）
- JSONL 字段（`schema:1`）：`ts / id / kind / sw / ms / result / phase / title / phases{} / metrics{}` —— 只到**平台级**，不含账号明文；**为将来上传分析设计**

#### 2.6.4 前端两处入口

- **标题栏**：`MainWindow` 的"活动"图标（`btnTasks`）+ **主题色实心圆角标**（`taskBadge`，由 Java 侧直接订阅 `TaskRegistry` 更新 —— 单一写入点）；点击 → `JFC.taskCenter.toggle()`
- **任务中心面板**（`js/components/task-center.js`）：贴标题栏下沿的抽屉；三小栏 **进行中 / 已完成（含失败）/ 已取消**；行内显示状态标签 + 阶段（带动态后缀）+ 耗时 + 取消；底部「查看更多」→ `JFC.router.navigate('statistics')`
- **「任务与统计」页**（`#page-statistics`，入口：最左栏底部**统计** + 面板「查看更多」）：统计卡（次数/成功·失败·取消/**总平均**/单次末次·最短·最长/阶段耗时/业务指标）+ 三小栏明细表
- 面板与页面都**每秒拉取** `getTaskList()`，用**指纹（id\|状态\|阶段\|进度）比对**决定是否重画 → 阶段实时而不闪、不打断点击
- **滚动条**：面板列表（`.tc-list`）与任务页明细（`.tasks-body`）都**复用项目既有设计** —— 同 `.settings-form`：
  **默认隐藏、悬停才显示 4px 细条**（track 透明、thumb `rgba(255,255,255,0.12)`、圆角 2px）
- **打开面板时的默认栏**：若有任务在**进行中** → 优先定位「进行中」（否则保留上次停留的栏）——
  打开面板的动机通常就是"看现在在跑什么"

#### 2.6.5 新流程接入三件套（照抄即可）

```java
TaskRegistry.get().submit("detect", "探测 WeChat 路径", swId, () -> {   // ① 登记 → 可见/可取消/统计/角标 全自动
    TaskContext.step("扫注册表", () -> registryScan(sw));                // ② 分步 → 检查点+阶段+计时 一次搞定
    for (int i = 0; i < n; i++) {
        TaskContext.checkpoint();                                       // ③ 循环里加安全点
        TaskContext.phase("校验 " + (i + 1) + "/" + n, "校验");          //    显示带序号、统计键不带
        TaskContext.metricSet("已校验", i + 1);                          //    业务指标自己上报
    }
});
```
桥接入点：`JsBridge`（`getTaskList` / `cancelTask` / `cancelAllTasks` / `getTaskStats`）+ `js/bridge.js` 同名包装。

---

## 3. 数据与配置形态

### 3.1 配置文件分层

| 文件 | 放什么 | 位置 |
|---|---|---|
| `RootConfig.json` | 代理 / 远程配置源 / `user_data_path` | 版本根目录（**不随用户数据目录迁移**） |
| `LocalGlobalConfig.json` | 软件偏好（见 §2.5） | 用户数据目录 |
| `LocalSwConfig.json` | 每平台配置（路径、备注、快捷键、`login_size`、`icon_src_path`…） | 用户数据目录 |
| `SwAccData.json` | 每平台账号详情（展示名、隐藏/失效、`linked_acc`、`channel`、`ordinals`…） | 用户数据目录 |
| `RemoteGlobalConfig.json` / `RemoteSwConfig.json` | 远程下发的全局/平台定义（**加密存储**） | 用户数据目录 |

- 文件名一律**双驼峰 PascalCase**；用户数据目录内子目录用 PascalCase（`UserFiles` / `DevUserFiles`）
- `saveGlobalConfig` 是**顶层浅合并**：写嵌套对象必须先读出来再合并；**JSON `null` = 删除该字段**
- **配置类每次 `getData()` 都从磁盘 reload**（读写锁保证并发安全）→ 热路径不要反复读（见 §3.2 缓存）

### 3.2 远程配置

- **加密格式**（对应旧版 Python `CryptoUtils.decrypt_response`，是**对外契约**）：`HTTP 响应 = base64(IV[16] + ciphertext) + " " + key`；
  解密 = Base64 解码 → IV 取前 16 字节、`key = key.ljust(16)[:16]` → AES/CBC/PKCS5Padding → UTF-8 JSON。
  Java 侧 `CryptoUtils.decryptResponse` / `encryptAndAppendKey`（工具在 `src/tools` 源集，不进应用产物）；下载/解密日志关键词 `[下载]`、`[解密]`
- **读取前的兜底**：`JFC.ensureRemoteConfigs(onReady)` = 同步快检 → 就绪即回调 → 缺失则后台 `tryEnsureRemoteConfigsAsync()` → 失败 `toastError` + 强制跳设置页
- **结构**：`config_addresses`（变量模板）、`wnd_class.login|main.matching.<ver>` + `.original.class_name`、`auto_click.login_btn.location`/`ctrl_names`、`coexist.channels.<ch>.exe_wildcard`/`ordinals`/`mutex_wc`、`mutex_handle_wildcards`、`config_handle_wildcards`、`exe_wildcards`…
- **长期缓存**：`ConfigManager` 缓存 `remoteSw` / `remoteGlobal`（volatile）；写入口 `setRemoteSw`/`setRemoteGlobal` 顺手刷新；切用户数据目录 `invalidateRemoteCache()`
- **发布流程**：改 `scripts/original_remote_sw_<vN>.json` → 跑 `scripts/publish-configs.bat`（或 `gradle encryptRemoteConfigs`）→ 版本号变了就同步 `RemoteConfigFetcher.BUILTIN_REMOTE_*_VERSION` → 提交推送

#### 版本化配置与"同步填充"（2026-10-23 用户重申）

- **三族**：`global`（main v2 → python v1）、`sw`（main v10 → python v9）、`setting`（**只在 python 侧**：v4 / v7 / v8）
- **维护线**（用户 2026-10-23 定）：Python 侧**冻结在 sw_v9 / global_v1**（旧版程序不再加功能）；
  Java 侧现役 sw_v10 / global_v2，**今后会出 v11、v12…且各版本可能都有用户在用 → 每个都要维护**，
  直到用户明确交代某版本退役。详见 `decisions.md` D-55。
- **铁律**：旧版发布的 JSON **结构绝对不可改** —— 旧客户端把版本号与解析方式写死了；
  同步 = **按旧版已有结构填充内容**，旧版结构表达不了的内容**直接丢弃**；多条映射按版本**级联**（v10→v9→v8…）。
- **已实测的结构差异**（工具：`LegacyConfigSync.adapt`，位于 `src/tools`）：

| 步骤 | 差异 | 状态 |
|---|---|---|
| sw v10 → v9 | 仅 `channels.<ch>.relation`（渠道级关系，v10 新增）；v9 只有 `features[].patch_rules[]` 里 `type=relation` → 搬进去 | **已实现** |
| global v2 → v1 | 结构完全一致 | 原样直通 |
| setting v8 → v7 | v8 用 `channels.<ch>.features[]`；v7 用 `channels.<ch>.feature_ver_adaptations.<ver>[]`（按版本分组） | 待实现（main 侧暂无 setting 源） |
| setting v7 → v4 | v4 更老：`mode.channel.<ch>` + `mode.feature.<ver>.<ch>` + `mode.precise.<ver>` 平面结构，信息量更少，只能填它支持的部分 | 待实现 |

- **同步产物的排版**：4 空格缩进、`": "` 分隔、空容器写 `{}`/`[]`（Jackson 默认是 `{ }`/`[ ]`，工具里做归一化），
  目的是让 python 侧 diff 只剩"真正移动的内容"。
- **发布命令**：`gradle publishRemoteConfigs`（加密 main 侧 → 同步 python 侧 → 再加密 python 侧）；
  `CryptoUtilsTest.publishedConfigsMatchTheirSources` 会校验源与加密产物一致 → **改了源必须重跑发布**。

### 3.3 路径探测（自动填充优先级）

**存在**（已保存的路径）> 进程 > 内存映射 > DLL 遍历 > 注册表 > 猜测/其他 SW > 来源数量。
绿框由路径检查流程判定；**"该用哪个路径"的判定权只在探测流程，使用方只读结果**（见 `decisions.md` D-04）。

### 3.4 用户数据目录内容

```
{userData}/
├─ LocalGlobalConfig.json / LocalSwConfig.json / SwAccData.json / SwCache.json
├─ RemoteGlobalConfig.json / RemoteSwConfig.json
├─ stats/task_stats.jsonl       ← 任务统计（一行一条，schema:1；任务中心与统计页的数据源之一）
├─ logs/                       ← 日志（跟随 RootConfig.user_data_path）
└─ {swId}/                     ← 平台图标 {swId}.png、账号头像 {accId}/{accId}.jpg 等
```

---

## 4. 运行与构建

### 4.1 命令

| 场景 | 命令 |
|---|---|
| 开发运行 | `gradle run --no-daemon --args="--dev"` |
| 仅编译 | `gradle compileJava --no-daemon` |
| 单元测试 | `gradle test --no-daemon`（当前 57 例） |
| 远程配置加密发布 | `scripts\publish-configs.bat` |
| 打包 | `scripts\package-exe.bat` / `scripts\package.bat` |
| 依赖分析 | `scripts\analyze.bat` |
| 前端语法检查 | `node --check <js 文件>` |

**Gradle wrapper**（2026-10-22 加）：`gradle/wrapper/gradle-wrapper.properties` 的 `distributionUrl` 指向
`file:///D:/SpaceDev/Env/Infrastructure/runtime/gradle-9.8.0-bin.zip`（本机安装用 `tar.exe -a -c -f` 打的 144.6MB zip），
让 VS Code 的 Gradle 扩展不再联网下载 9.8.1。

### 4.2 环境与编码

- JDK 17（`D:\SpaceDev\Env\Infrastructure\runtime\Java\jdk-17.0.2`）、Gradle 9.8、Git 2.56
- `run` / 打包都带 `-Dprism.lcdtext=false`（灰度抗锯齿，试验开关）
- **编码**：JVM 侧 `-Dfile.encoding/-Dsun.stdout.encoding/-Dsun.stderr.encoding=UTF-8`；终端侧需 UTF-8（`chcp 65001` + `[Console]::OutputEncoding`）；日志文件 UTF-8；`Launcher` 最早处装 JUL→SLF4J 桥
- **日志目录**：跟随 `RootConfig.user_data_path`（`AppPaths.resolveLogsDirEarly()`，在 `Launcher` 首行、早于任何 logger；读不出回落 APPDATA）；**测试**走 `build/test-logs`（`logback-test.xml` 只打控制台）

### 4.3 打包产物

`build/portable/`（便携版）、`build/exe/`（安装版，WiX 3.14）；版本号唯一来源 `AppVersion.java`（当前 `4.0.0.7000`）。

---

## 5. 浮动侧栏（窗口切换器）与多平台窗口唤起

> 2026-10-13~15 建成；**规矩见 `AGENTS.md`「窗口唤起 / 平台适配」一节**，这里只写"现在是什么样"。

### 5.1 侧栏代码结构（`com.jfmultichat.ui`）

| 文件 | 职责 |
|---|---|
| `FloatingSidebar` | 侧栏窗口本体：跟随外部窗口、按钮列表（🏠 主窗 + 已绑定账号，含头像/平台徽标/🧪 测试台按钮）、贴边隐藏、切窗、`armPendingPlace`、`updateActiveHighlight`（只改样式类不重建 → 不丢滚动）、`revealActive`（最短步滑到当前项） |
| `SidebarPrefs` | 贴边/对齐/尺寸模式/主窗按钮位置；`LocalGlobalConfig.json` 的 `sidebar` 节点；`buttonSize/contentLength`、`MIN_BTN=22 / BTN=44 / GAP=8 / PADDING=12 / COLLAPSED=6` |
| `SidebarLayout` | 纯几何：`sidebarRect`、`collapsedAtScreenEdge`/`expandedAtScreenEdge`、`atScreenEdge`、`windowRectForSwitch`（由侧栏矩形反算窗口矩形）、`fitLength`、`needsScroll` |
| `WinEventWatcher` | WinEvent 钩子（专用线程 + `GetMessage` 泵），`WINEVENT_OUTOFCONTEXT`，**刻意不带 `WINEVENT_SKIPOWNPROCESS`**（自己的主窗前台事件也要）；暴露 `getSeq/getForegroundHwnd/getLastEvent` |
| `WindowActivationLab` | 唤起测试台（侧栏 🧪 打开，**最大化**启动）：顶行 hwnd/前台/侧栏当前/托盘 uid/尺寸/位移，下面 **38 个方案** + 「执行方案」+ 大日志区 |

- 侧栏消费循环是 `AnimationTimer` 读两个 volatile（`AccRuntimeStore.version()` / `Watcher.getSeq()`），不变即早退 → 空闲零 CPU
- 主题：`css/sidebar.css` + `sidebar-light.css`（looked-up 颜色 `-jf-sb-*`，由 `MainWindow.applyTitleBarTheme` → `MainApp.onThemeChanged` 传入）
- 折叠态热区：JavaFX 透明窗**按像素命中** → 用 6px 可见细条 + 1% alpha 铺满 + `-fx-background-insets` 两层 + `pickOnBounds` 做 16px 热带

### 5.2 平台适配器（`com.jfmultichat.platform`）

- `PlatformAdapter`：`Ctx{sw,acc,hwnd,pid,visibleBefore,rect,wantMaximized,resolvedHwnd}`；
  钩子 `activate`（默认保状态激活）/`beforePlace`/`afterPlace`/**`allowExternalPlacement`**（默认 true）
- `PlatformAdapters`：按约定名加载 `com.jfmultichat.platform.adapt.{平台id}Adaptation`，别名只有 `QQ→QQNT`；带缓存与失败缓存，**永不返回 null**
- `adapt/ElectronAdaptation`（QQNT 等）：`activate` = 窗口已可见→什么都不做；否则 `trayActivateByPid(pid, trayIconId())`（回退 `trayActivate(hwnd,…)`）；`afterWake` **只读**地把重生主窗 hwnd 记进 `ctx.resolvedHwnd`；**不允许外部摆位** ✗
- `adapt/QQNTAdaptation`：只给 `trayIconId()=3`
- `adapt/WeixinAdaptation`：已可见→什么都不做；**任务栏「微信」图标恰好 1 个 → `trayIconActivateByUia("微信", hwnd)` 托盘唤出**；≥2 个（多开）或任务栏自隐藏 → 兜底 `weixinWakeByTitleBarDoubleClick(hwnd)`（标题栏双击×2，用户三方案实测胜出）

### 5.3 `swcore/WindowActivationOps` 对外入口（唤起与探针）

`trayActivate(hwnd,uid)` / `trayActivateByPid(pid,uid)` / `hasElectronTray(ByPid)` / `findMainWindowOfPid(pid)`（**可见优先 + 隐藏兜底**，且排除 `*MessageWindow*`/`IME`/`SoPy*`/`Sogou*`/`MSCTF*` 辅助窗口）/ `weixinWakeByTitleBarDoubleClick(hwnd)` / **`trayIconActivateByUia(name, verifyHwnd)`**（Win11 任务栏 XAML 图标的 UIA `Invoke` ✓ 零坐标 ✓）/ **`countTrayIcons(name)`** / `findWindowByClassGlobal(class)` / `clickScreen(x,y)`，以及探针用 `probeTrayIcons` / `probeTrayClickMessages` / `probeTrayUidMapping` / `probeRectIndices` 等

### 5.4 `swcore/UiaOps` 能力与**已校正的 vtable 下标**

- 既有：属性读取（`getClassName` / `getProperties`）；本轮新增：`listByClassKeyword`（**不设数量上限，别再犯 60 条上限的错**）、`findByNameWithRect`、`invokeByNames`、`invokeButtonExact`（**类名+名字完全相等**）、`invokeByClassKeyword`、`invokeTitleBarButtonByIndex`、`titleBarChildren`、`buttonScreenRect`、`probeRectIndices`、`dumpDescendants`
- 下标依据：**项目实测过** `24=AutomationId`、`30=ClassName`；**接口只有一个方法**故无歧义 `ElementArray 3=get_Length / 4=GetElement`、`InvokePattern 3=Invoke`；其余为按序推（`6=ElementFromHandle/FindAll`、`10=GetCurrentPropertyValue`、`16=GetCurrentPattern`、`21=CreateTrueCondition`、`TreeScope: None0/Element1/Children2/Descendants4`）
- **`25`(矩形)/`26`(可点)/`28`(ControlType) 实测读出来是全 0 或垃圾** ✗ → 需要几何时改用 `probeRectIndices` 现场校准
- 跨进程 COM 一律走 **800ms 线程池超时 + 连续 3 次熔断**

### 5.5 探针基建（自己跑，别让用户点）

- `scripts/probe-run.bat <探针类名> [参数]`：自动从 Gradle 缓存拼 JNA/SLF4J 类路径、编译并运行 `tmp/probe/<类名>.java`（⚠️ 在 pwsh 下 .bat 会因 UTF-8/GBK 被 cmd 读坏 → 可直接手拼类路径跑 `java -cp build\classes\java\main;tmp\probe\out;…<jars>`）
- 现有探针：`UiaProbe`（UIA vs Win32 类名 / 矩形下标扫描）、`TrayProbe`（按 pid 列窗口 + `Shell_NotifyIconGetRect` 命中）、`TrayMsgProbe`（给托盘宿主枚举 `WM_APP/WM_USER` 消息）、`TrayUidProbe`（**托盘 uid ↔ 账号窗口 映射**）、`TrayUiaProbe`（任务栏 UIA 找图标 + Invoke）、`TrayAllIconsProbe`（任务栏全部图标名）

### 5.6 已实测的平台结论（2026-10-15）

| 平台/场景 | 结论 |
|---|---|
| QQNT | `PostMessage(Electron_NotifyIconHostWindow, 0x8001, uid=3, 0x201)` 可唤醒 ✓；**唤醒后不得再做任何外部操作** ✗（否则"出来但卡住"）；**pid 过期场景尚未处理**（`状态: 待定`） |
| 微信 单实例 | 任务栏 UIA `Invoke("微信")` = 最自然的托盘唤出 ✓（探针实证 `visible=false→true`） |
| 微信 多开 | 托盘图标**同名「微信」**✗ 无法指定账号 → 用标题栏双击×2（作用在指定 hwnd 上，按账号精确 ✓） |
| 任务栏自动隐藏 | UIA 里没有图标 → 落回双击×2 ✓ |
| 其它平台 | 走默认"保状态激活" ✓（未逐平台验证 ✗） |
| 微信自绘标题栏 | UIA **无几何** ✗ 且 `InvokePattern.Invoke()` 是**空操作** ✗ → 只能"真实点击"（双击×2 ✓）；而 Win11 任务栏是 XAML ✓ 两样都有 ✓ |

---

## 6. 侧栏设置体系（2026-10-17~19 建成）

### 6.1 数据模型（`ui/SidebarPrefs`，`LocalGlobalConfig.json#sidebar`）

| 字段 | 取值 | 说明 |
|---|---|---|
| `edge` | left/right/top/bottom | 贴哪条边 |
| `align` | start/center/end | 该边上的位置（**合起来 = 12 个位置** ✓） |
| `size_mode` | match(铺满)/fit(自适应) | **铺满 = 条延伸到该边整条** ✓ 但**图标仍落在所选位置** ✓ |
| `main_btn_at_end` | bool | 方向（主窗按钮在前/在后） |
| `separate_main_btn` | bool | **分离** ✓ **仅"铺满 + 居中"可用** ✓（`separatedEffective()` 统一判据 ✓） |

### 6.2 布局与长度的**唯一口径**

- 12 位置 ✓：`layoutContent` 里 `setFitToWidth(true)` **+** `setFitToHeight(true)` ✓ 后按 `prefs.align` 设 `colBox/rowBox` 对齐 ✓
- 长度 ✓：跟随态 `length = fit ? min(content, avail) : avail` ✓；**贴边态 `edgeLength = fit ? min(content, edgeLen) : edgeLen`**
  —— **条与折叠热带共用它** ✓（`atScreenEdgeHot` / `expandedAtScreenEdge` 都传 `edgeLength` ✓）
- `visibleCount()` = 主窗/账号 + 测试按钮 + **`demoIconCount()`** ✓（长度必须与实际按钮数一致 ✓）

### 6.3 分离（`applyPinnedMain`）

- 生效时主窗按钮**不进簇** ✓，用 `StackPane.setAlignment` **钉端点** ✓（竖排 TOP/BOTTOM ✓ 横排 CENTER_LEFT/CENTER_RIGHT ✓）；
  测试按钮与它**同组**钉住 ✓
- ⚠️ 那组在 StackPane 里会**撑满整条** ✓ → 真正决定位置的是**组内对齐** ✓（横排漏设 → "上下两边都居中" ✗）

### 6.4 示例按钮与预览态

- `demoIconCount()` ✓：**唯一判据＝有没有真实平台账号** ✓（0 个 → 3 个 A/B/C ✓ 鼠标穿透**已去掉** ✓ 否则 Tooltip 不显示 ✗；
  悬浮"请登录账号后体验功能" ✓）
- 预览态 `demoMode`（= 正在看"侧栏设置页" ✓）：进＝`setSidebarDemo(true)` ✓（顺带 `ensureShown` 确保侧栏存在 ✓）、
  离开该页 / 点设置容器外＝false ✓；**只有预览态会拒绝 `hide()`** ✓，其他页面可自由显示/隐藏 ✓

### 6.5 窗口形态（**三开关要一起审** → 详见 `decisions.md` D-49）

`TOPMOST`（`SetWindowLong` 后**必须重申**）+ `NOACTIVATE|TOOLWINDOW` + **有 owner（`initOwner(主窗口)`）**；
**永不 `stage.toFront()`**、**不用 `SetWindowPos` 插层级**（都会破坏上面的组合）。

### 6.6 两种"矩形"口径与摆位换算（2026-10-18 实证，**摆位必须按它来**）

代码里同时存在两种矩形，混用就会产生"恒定小偏移"：

| 口径 | 来源 | 用在哪 |
|---|---|---|
| **可视矩形**（看得见的区域） | `SwNativeOps.getVisualRect` → DWM `DWMWA_EXTENDED_FRAME_BOUNDS` | 侧栏跟随 / 判最大化 / **取"上一个窗口"的目标矩形** |
| **窗口矩形**（含隐形边框） | `GetWindowRect`、`SetWindowPos` | 真正落位时（`setWindowRect`） |

- 两者差值＝**DWM 那圈看不见的边框**（Win11 每边约 7px）→ 新增 **`WindowActivationOps.frameDelta(hwnd)`** 返回 {左,上,右,下}
- **摆位统一做法**：目标矩形按**可视**取 → `WindowActivationOps.frameDelta(目标)` → 换算成窗口矩形 → `setWindowRect(x-dl, y-dt, w+dl+dr, h+dt+db, true)`
  （`AccOperatorCore.placeForSwitch` 已按此实现；日志会打 `窗口补偿 dl/dt/dr/db=…`）
- **`WindowActivationOps.waitWindowReady(hwnd, timeoutMs)`**：Electron 从托盘唤醒后**立刻**搬几何会逼出 Chromium 的**黑框占位窗口**，
  之后所有操作都落在黑框上 → 搬位前先等"可见且连续稳定（约 3×40ms）"。`placeForSwitch` 里 `if (!visibleBefore) waitWindowReady(target, 1500)`。

## 7. 补丁系统（防撤 / 多开 / 共存，2026-10-21~23 建成）

> 迁移自 `legacy_python/func_core/sw_func_core.py`；**缓存结构以旧版 `sw_cache.json` 为准**（不要自造字段，见 D-51）。

### 7.1 模块结构（`swcore/`）

| 类 | 职责 |
|---|---|
| `SwPatchCacheBuilder` | **扫描 → 缓存**。入口 `build(sw, mode, channels, skipCache[, allowScan], accessor[, cache])`；`platformRoot/platformNodeIfPresent`（平台层）、`setForceRescan/isForceRescan`、`MERGE_LOCK`（只保护 JSON 树合并） |
| `SwRuleResolver` | 5 类规则：`simple` / `custom`（可自定义）/ `jmp_offset`（目标特征码 + 4×`!!` 填相对偏移）/ `relation`（parents/children/friends）+ 版本兼容选择 |
| `SwHexUtils` | 特征码分词（`??` 任意字节、尾部 `...` 省略、`!!` 占位、wildcard 里 `?` = 序号）、对齐、预编译匹配、`bytesOf(ByteBuffer)` 同步缓存 |
| `SwPeImage` | 极简 PE 解析、`foaToRva`、`jumpOffset` |
| `SwAdapterChecker` | 逐渠道识别状态；`DetectionResult.status` 是**三态** `Boolean`（true/false/null=未知）；`identifyChannels(...)` → `ChannelsResult` |
| `SwOperatorCore` | 开关补丁（`switchDllCore`：`.bak` 备份 + 同进程先 `unmap`）、建/删/重建共存程序 |
| `SwPatchService` | 门面：`getSwPatchPlan`（多开+防撤）、`getCoexistPlan`（共存渠道+选中方案）、`getInstancePatchPlan`（某共存实例）、`ensureRevokeCache`、`toggle/createCoexist/deleteCoexist/rebuildCoexist`、`selectedCoexistMode`、`deriveOrdinal`、`resolveCoexistIndex` |

**JS 桥**（`JsBridge` + `js/bridge.js` 两处都要加）：`getSwPatchPlan / getCoexistPlan / getAccPatchPlan / scanPatches /
rescanPatches / scanCoexist / scanAccPatch / switchPatch / createCoexistAccount / deleteCoexistAccount / rebuildCoexistAccount / setCoexistMode`。

### 7.2 缓存结构（`SwCache.json`，与旧版同构）

```
{ "Weixin": { "anti-revoke": { "channels": { "<渠道>": { "precise_ver_adaptations": { "<版本>": [
      { "addr": "%dll_dir%/Weixin.dll", "wildcard": "Weixi?.dll",
        "patches": [ { "offset": 123, "original": "..", "modified": "..", "descript"?, "customizable"? } ] } ] } } } },
  "multirun": {...}, "coexist": {...} } }
```

- **平台节点是必需的**（旧版就有）。缺这一层会**跨平台串数据** → 症状是"莫名其妙的缓存命中"。
- `addr` 存**配置模板**（保留 `%dll_dir%` 之类），不是解析后的绝对路径。
- 三条闸门：全部规则弃用 → 删该版本缓存；任一失败 → **不写**（保留旧缓存）；全部成功 → 写入。
- 读取旧的扁平结构（mode 直接挂顶层）做兼容，写入时顺手清掉。
- `SwAccData` 里共存账号只记 `channel`；**序号 `ordinal` 不落库**，由 `exe_wildcard` 从账号名反推
  （`Weixi3.exe` + `Weixi?.exe` → `3`），解析不出时遍历所有渠道反查。

### 7.3 扫描与计划（**每个模式每步恰好一次扫描**）

- **只有显式动作才扫描**：`allowScan=true` 用于计划/扫描任务；`allowScan=false` 表示**纯读缓存**（连 `build` 都不调）。
- 触发点与对应模式：

| 动作 | 扫描的模式 |
|---|---|
| 进平台（页面加载） | 程序计划 = multirun + anti-revoke；共存表头 = coexist（两条任务并行，互不阻塞） |
| 刷新原生程序表 / 原生单行扫描 / 重新扫描 | multirun + anti-revoke |
| 刷新共存账号表 | anti-revoke + coexist（**不碰 multirun**） |
| 共存账号单行扫描 / 重新扫描 | 仅 anti-revoke |
| 共存账号行**查询** | 不扫描；扫描阶段用**原生文件**建缓存，查询阶段用 `patch_wildcard` 映射到 `Weixi1.dll` 等克隆文件 |

- `forceRescan` 语义：重新扫描必须"force + 取计划"在**同一轮**完成（分两次 = 两轮全量扫描）。
- 平台层不再有整平台串行锁；并发安全靠 `MERGE_LOCK` 只锁 JSON 合并。

### 7.4 界面（账号管理页三张表）

- **程序行补丁列**：`扫描 / 重新扫描`（最左）+ `多开` 组 + `防撤` 组；**不再有"共存"组**（归共存账号表头）。
- **共存账号行补丁列**：`扫描 / 重新扫描`（只作用于该行）+ `防撤` 组。
- **共存表头**：`+`（新建，无可用方案时禁用）+ `···`（悬停**自身宽度延伸**成方案分段按钮，单选；移开缩回；
  无方案时显示"无方案"）。
- **表常显**：空表也保留表头，正文一行"没有数据"；管理态表名左侧"眼睛"只切换**登录模式下是否显示这张表**
  （管理态永远显示）；表头右键同一开关。
- 每张表标题栏有**刷新按钮**，走组件契约 `opts.reload`（每张表自己提供重载方式，无表名分支）。
- 表格渲染**单一来源** `_renderCols()`（列顺序 ∩ 当前可见）：列头 / 数据行 / 空表占位 colspan 都用它；
  隐藏列不进 DOM；`setMode` 必须 `_rebuildHead()`。
- 补丁按钮点击用**捕获阶段**委托，避免连带选中整行；未适配（虚框）不可点、无 hover 变化。
- **所有补丁操作都走任务中心**：`扫描补丁适配 / 扫描共存方案 / 扫描共存账号 / 强制重扫` 都是 `TaskRegistry.submit(...)` 任务，
  前端点扫描时把目标表置为"扫描中…"并用 `patchBusy` 防重复点击。
- 日志：每个模式一行汇总（`[缓存] {平台} {模式} 本轮扫描：新扫描 N / 缓存命中 N / 弃用 N / 失败 N`，
  有失败用 WARN）；每个渠道的失败明细、每行"实例计划"都在 DEBUG。
- 补丁列"自适应宽度"：把 `.patch-groups` 临时 `nowrap` 读 `scrollWidth`，量完仍折行就每次 +24px 继续加宽。


#### 7.4.1 渠道启用/禁用（用户自选，2026-10-23~30 建成）

- **只在管理态可操作**：点渠道按钮 = 启用/禁用（悬浮时文字变 `-`/启用中、`+`/已禁用；宽度不变）。
  已启用**靠左**、已禁用**靠右 + 删除线**；组内渠道全禁用时**连组名一起隐藏**。
- **登录态**：被禁用的渠道**不渲染**，也不参与扫描；选中的是启用的才显示。
- **不扫描**：管理态的启用/禁用**只改开关 + 从缓存重读该模式**（毫秒级）。扫描是登录态/显式刷新的事。
- **存储**：`LocalSwConfig.<平台>.disabled_channels = { "anti-revoke": [...], "multirun": [...] }`（按模式隔离）。
  写入必须走 `updateSwSettings`（`putPOJO`）—— `saveAndCheckChanged` 会 `value.toString()` 把 Map 写成字符串。
- **关系传播**：启用子渠道 → 同时启用它的 `parents`；禁用父渠道 → 同时禁用它的 `children`。
- **扫描/识别分离**：`SwAdapterChecker.identifyChannels(scanChannels, checkChannels, …)` ——
  补扫某个渠道时**识别仍覆盖全部缓存渠道**，否则其它渠道会显示成"未知"。
- **关系独立缓存**：`channels.<ch>.relations = {parents|children|friends}`，由 `SwPatchCacheBuilder` 在扫描之外单独写入，
  **与有没有适配无关**；`getRelationsOfChannel` 优先读它，回退到 `patches` 里的旧写法。
- **登录态切换补丁时按关系联动**（照旧版）：启用 A → 关闭同组非 friend 非 parent、依次开启 parents、再开自己；
  关闭 A → 先关 children（失败忽略）、再关自己；**前置不可用 = 本渠道不可用**（拒绝并说明）。
- **tooltip** 显示 `前置 / 后置 / 可共存`；互斥是默认行为，不额外标注。

### 7.5 并行度与耗时实测（192MB `Weixin.dll`，2026-10-23）

- **三级并行**：模式串行 → 渠道并行（池 3）→ 规则并行（池 4）。
- 实测：1 条规则 807ms；7 条规则串行 2483ms / 4 线程 953ms；缓存预热后整表刷新约 1s。
- **内存带宽瓶颈**：把模式也并行、渠道池开 6 之后整体变慢（4.7s → 5.1s）→ 已回退。加线程救不了全文件扫描。
- 共存表头曾因"整平台串行锁"白等 4.8s；去锁后 0.2s；每步"每模式恰好一次扫描"已用真机日志逐一核对。

## 8. 启动期提权与工具链（2026-10-24 / 10-27）

### 8.1 打包版默认管理员运行（`boot/AdminBoot`，2026-10-24）

- 入口：`Launcher.main` 最前面调用 `AdminBoot.ensureElevated(args)`；**刻意不用 JNA**（全走 `whoami` / `reg` / `powershell` / `mshta` 系统命令）。
- 流程：已提权 → 顺手写 `HKCU…\AppCompatFlags\Layers` 的 `~ RUNASADMIN`（以后双击直接提权）；
  未提权且是打包启动器 → `powershell Start-Process -Verb RunAs` 重启自身并退出；用户取消 UAC → `mshta` 提示后退出。
- **`--dev` / 非 jar 运行不提权**（`gradle run` 不受影响）。
- 已知副作用：每次启动一次 UAC；提权后**从非提权资源管理器拖文件进窗口会被 UIPI 拦**（改用"浏览"按钮）；
  jpackage 17 不支持自定义 manifest（实测 `--resource-dir` 传 manifest 无效）。
- 背景：本机「联想电脑管家 / Huorong（`wsctrl11.exe`）」的文档保护**按进程映像拦截** —— 同一令牌下 `cmd`/`node` 能写 `%APPDATA%`，
  只有 **JVM** 报 `AccessDeniedException`。详见 `decisions.md` D-56 与 `lessons.md`「安全软件 / 提权」。

### 8.2 特征码维护 skill（`.dsh/skills/signature-maintenance/`，2026-10-27）

- 内容：`SKILL.md` + `scripts/diffsig.py`，子命令 `diff / extract / match / check / merge / locate`。
- 用途：从"原版 vs 已打补丁"的 dll 差异提炼**不含通配符**的 original/modified；判定已存特征能否覆盖新版本；
  产出可直接粘进 `scripts/original_remote_sw_v10.json` 的草稿。
- 4.1.15.13 基线：silence PASS；**multirun/default 失效**（4.1.9 键把 `FF 15 F9 CE 08` 的 RIP 相对 disp32 写死成具体字节，
  新版只差这 3 字节）；alert 多重命中；custom_alert 的 jmp_offset FAIL；bubble 7 条规则全被作者弃用。


