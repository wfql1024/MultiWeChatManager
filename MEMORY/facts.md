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
  - **单个实例启动**：`SwOperatorCore.launchOneInstance(sw, exe, accessor, ops[, skipKill])` —— **默认内化查杀**；`skipKill=true` 供"先杀一次、再连开 N 个"
  - **降权启动**：`SwNativeOps.createProcessWithoutAdmin` —— 非管理员直接 `CreateProcess`；管理员借 explorer 令牌（`CreateProcessWithTokenW`）；失败兜底 `explorer.exe` 代启（返回 `-1`）
- **原生账号登录**：`AccOperatorCore.loginOrigin`（入口：账号行"登录"/批量登录 → `main.js.loginAccounts` → `JsBridge.loginAccountsAsync`）
  1. **替换该账号的登录配置**（`operateAccConfig("use")` = 账号配置 → 平台配置）
  2. 开登录窗（含查杀互斥体）
  3. **预摆位**：开窗前按账号总数算好格子（`login_size` 优先，兜底 屏幕/6 × 屏幕/3），窗口一出现立刻挪到位；**失败/超时的格子空着、不重排**
  4. 全部打开并摆位后**才统一点击**"登录"（后台 `PostMessage`；比例取远程 `auto_click.login_btn.location`，默认 0.5/0.75）
  5. 等所有登录窗关闭（**20 秒**上限，收尾观察用；可取消）。**任何单个账号失败都不中断整批**
  - 前端只做 **2 秒防连点**；整条流程**登记为任务**（kind `login`）→ 右上角任务中心可见/可取消、自动进统计（见 §2.6）
  - **共存账号登录（待实现）**：共存账号 ID **本身就是 exe 名** → 直接按它启动即可（无需遍历 `ordinals`、无需问创建）
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

### 4.2 环境与编码

- JDK 17（`D:\SpaceDev\Env\Infrastructure\runtime\Java\jdk-17.0.2`）、Gradle 9.8、Git 2.56
- `run` / 打包都带 `-Dprism.lcdtext=false`（灰度抗锯齿，试验开关）
- **编码**：JVM 侧 `-Dfile.encoding/-Dsun.stdout.encoding/-Dsun.stderr.encoding=UTF-8`；终端侧需 UTF-8（`chcp 65001` + `[Console]::OutputEncoding`）；日志文件 UTF-8；`Launcher` 最早处装 JUL→SLF4J 桥
- **日志目录**：跟随 `RootConfig.user_data_path`（`AppPaths.resolveLogsDirEarly()`，在 `Launcher` 首行、早于任何 logger；读不出回落 APPDATA）；**测试**走 `build/test-logs`（`logback-test.xml` 只打控制台）

### 4.3 打包产物

`build/portable/`（便携版）、`build/exe/`（安装版，WiX 3.14）；版本号唯一来源 `AppVersion.java`（当前 `4.0.0.7000`）。
