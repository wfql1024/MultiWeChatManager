# AGENTS.md — JhiFengMultiChat（极峰多聊）

> **本文件是"热记忆"**：只写**每次动手都必须遵守/使用**的东西（规矩、命令、硬约束、验证）。
> 现在是什么样 → `MEMORY/facts.md`｜为什么这么定 → `MEMORY/decisions.md`｜踩过的坑 → `MEMORY/lessons.md`｜过程与证据 → `MEMORY/dev_logs.md`｜架构细节 → `docs/project_structure.md`。
> ⚠️ **本文件与 `MEMORY/` 的内容规范严格遵循顶级 `~/.dsh/AGENTS.md`**（跨项目记忆规范）——不在此重复其内容。

**一句话**：Windows 桌面端多平台聊天管理器（Java 17 + JavaFX 17，界面由内嵌 WebView 渲染 HTML/CSS/JS）。

> 🔴 **本条严格遵循全局 `~/.dsh/AGENTS.md` 的「素材流（工作流）· 1. 平时（每轮对话末尾）」——必须逐字执行，不得以任何理由跳过。**
> 回复用户**之前**先向 `MEMORY/tmp/{当天日期}.md` 追加一张素材卡（`## HH:MM:SS — 主题` + 做了什么/证据/候选去向/状态，时间实取）；
> 当天文件不存在就新建；**"整理凝练"之后同样要做**（历史上多次出现"整理完就忘了继续写卡"，用户已当面指出两次）。

---

## 命令（精确可复制）

| 场景 | 命令 |
|---|---|
| 开发运行 | `gradle run --no-daemon --args="--dev"` |
| 仅编译 | `gradle compileJava --no-daemon` |
| 单元测试 | `gradle test --no-daemon` |
| 远程配置加密发布 | `scripts\publish-configs.bat` |
| 打包 | `scripts\package-exe.bat` |
| 前端语法检查 | `node --check <js 文件>` |
| 一键验证（编译+测试+JS 检查） | `scripts\verify.bat` |

JDK `D:\SpaceDev\Env\Infrastructure\runtime\Java\jdk-17.0.2`｜Gradle `D:\SpaceDev\Env\Infrastructure\runtime\gradle-9.8.0\bin\gradle.bat`

---

## 边界

### Always（放手做）
- **一次只动与任务相关的文件** —— 不做顺手的清理、重构、"改进"
- 需要"反复怎么做"的流程 → **写成 `scripts/` 下的脚本**，不要写成文档段落或 skill
- 拿不准用户的意图 → 先说明假设并问，不要自行扩展目标

### Ask（先问再做）
- 装依赖、改打包脚本、改公开接口或配置字段名
- 删除文件；移动 / 改名文件（**尤其只改大小写**）
- 扩大范围（顺手改别的功能）、一次性大批量重构（文档/记忆体系等）
- 任何可能不可逆的操作

### Never（绝不做）
- **自行提交**（提交必须由用户明确指示）；`force push`；提交密钥/凭据
- **顺手改记忆文件**（`MEMORY/` 的 `facts/decisions/lessons/dev_logs`）—— 平时**只追加 `MEMORY/tmp/{日期}.md` 素材卡**，
  整理由用户发起（D-44 约定 7）
- 删测试、或为了让测试变绿而改测试
- 把 `build/` 当工作目录（构建产物目录，`gradle clean` 会清空）—— 临时文件放项目根 `tmp/`
- 在项目根生成日志文件
- 静默用 shell 批量替换文件内容（改文件一律用编辑工具）

---

## 硬约束与不变量

- **单一写入点**：一个状态的渲染只允许一个写入点；状态先落事实来源再渲染
- **长耗时流程必须走任务中心**：`TaskRegistry.submit(...)` 登记 + 流程内 `TaskContext.checkpoint()/phase()/metricSet()`（见 `MEMORY/facts.md` §2.6）；
  **不许**在核心业务方法里写计时/写盘（统计与任务中心同源，由任务边界统一记账）
- **新增 JS 桥方法必须两处都做**：`JsBridge` 里加方法 **+** `js/bridge.js` 加同名包装（前端只认 `JsBridge`；
  漏一处 `bridge.js` 会**静默跳过**、不报错）
- **弹窗**一律 `JFC.modal.confirm/custom`（`window.confirm` 在本 WebView 恒 false、`alert` 是空操作）
- **配置**：写嵌套对象必须"先读出来再合并"；JSON `null` = 删除该字段；热路径不要反复直接读配置（远程配置已有配置层缓存）
- **日志**：文件与控制台 UTF-8；日志目录跟随 `user_data_path`，且必须在**任何 logger 之前**解析；级别原则 = 研究期用 `DEBUG`、成熟功能 `INFO` 并尽量合并条数
- **WebView 右键**：Java 侧关掉了自带菜单 → DOM 的 `contextmenu` 由 `mousedown(button===2)` **合成**（这是有意为之，勿"修回去"）
- **补丁扫描只在显式动作时发生**：`allowScan` 参数决定，**不许**用任何跨任务/跨会话的静态标记；
  每个界面动作**每个模式恰好一次扫描**（对照表见 `MEMORY/facts.md` §7.3），纯查询路径不得进扫描流程
- **`SwCache.json` 结构以旧版真实文件为准**（平台 → 模式 → channels → precise_ver_adaptations → 版本）；
  **不许自造字段**，失败结果不落盘
- **表格加列只加定义**：列头/数据行/空表 colspan 全部走 `_renderCols()`（可排列顺序 ∩ 当前可见），
  隐藏列不进 DOM；`setMode` 必须重建列头；表刷新走组件契约 `opts.reload`

> 其余不变量（PID/HWND 只存内存、表格列规则、"创建实例必查杀"、登录失败不中断整批…）都在 [`MEMORY/facts.md`](MEMORY/facts.md) 对应功能块里。

## 窗口唤起 / 平台适配（2026-10-14~15 定，违反必踩坑）

- **窗口状态一律用几何判定**（`isEffectivelyMaximized`：可视矩形 ≥95% 监视器且四边贴合），**不用 `showCmd`**；正常态基准取 `GetWindowPlacement().rcNormalPosition`
- **侧栏（及一切跟随逻辑）禁止定时器/轮询/JavaFX 监听** —— 用户明确："不要搞多少 ms 这种，用钩子就好好用钩子"。事件只来自 `WinEventWatcher`（`WINEVENT_SKIPOWNPROCESS` 已刻意去掉），恢复异步用 `armPendingPlace` 等下一个钩子事件
- **Electron 平台（QQNT 等）禁止一切"外部强制"** ✗：`SetWindowPos` / `ShowWindow` / `SetForegroundWindow` / 尺寸抖动 / 二次唤醒 —— 会把窗口推进"**出来了但卡住**"；正解只有一条：发对托盘消息 `PostMessage(host, WM_APP+1, uid, WM_LBUTTONDOWN)` 之后**什么都不做**（依据 [CSDN 那篇 Electron 卡死分析](https://misuseds.blog.csdn.net/article/details/166489064)）。适配器用 `allowExternalPlacement()=false` 否决侧栏摆位
- **托盘图标是「切换」语义** ✗ —— 绝不连发两次（连发＝又切回去/切进坏状态）；窗口已可见时不要再碰托盘
- **多开同名托盘图标无法区分账号**（微信多开全是 `name=微信`）→ 单图标才用托盘唤出，多图标/任务栏自隐藏一律走"作用在指定 hwnd 上"的方案（微信＝标题栏双击×2）
- 平台适配器约定：`com.jfmultichat.platform.adapt.{平台id}Adaptation`（别名仅 `QQ→QQNT`），钩子 `activate/beforePlace/afterPlace/allowExternalPlacement`
- **验证/探针自己跑** ✗ 不让用户一轮轮点；探针源码放 `tmp/probe/`（`tmp` 已 gitignore），用 `scripts/probe-run.bat <类名> [参数]`

---

## 记忆素材卡（硬规矩，2026-10-16 用户立）

- **一天一个文件** ✗：`MEMORY/tmp/{YYYY-MM-DD}.md`（**不许**把新一天的卡片追加到旧文件上）
- **标题必须是 `## HH:MM:SS — 主题`** ✓（秒不能省、日期不写进标题 —— 日期由文件名承载 ✓）
- **写卡前先取真实时间** ✓：`Get-Date -Format 'yyyy-MM-dd HH:mm:ss'`；
  若本机时间取不到 → **联网取**（HTTP 响应 `Date` 头 / 授时接口）✓ ——
  **绝不估算、绝不省略日期或秒** ✗；格式必须齐全 ✓（日期记错的补救＝**直接重命名文件** ✓ + 改内部标题 ✓）
- **能用命令行拿到的事实一律不要靠脑子** ✓：时间、行数、文件是否存在、进程 pid/句柄…
- 卡片字段固定四项 ✓：`做了什么 / 结论` → `为什么 / 证据` → `候选去向` → `状态`

---

## 侧栏交互契约（2026-10-17~19 定，违反必返工）

- **位置 = 四边 × 起始/居中/末尾 = 12 个** ✓；**长度 = 铺满/自适应** ✓；**方向 = 主窗按钮在前/在后** ✓
- **铺满 = 长条延伸到该边整条** ✓，但**图标仍落在所选位置** ✓ —— 对齐靠"**容器撑满 + 容器对齐**" ✓：
  `ScrollPane.setFitToWidth(true)` **且** `setFitToHeight(true)` ✓（只开一个 → 竖排没有对齐空间 → 三端都挤一头 ✗）
- **长度只有一处算法** ✓：跟随态 `length` / 贴边态 `edgeLength`（**条与感应热带共用它** ✓）
  —— 同一个量出现第二处算法，就一定会不一致 ✓
- **示例按钮判据 = 有没有真实平台账号** ✓（`demoIconCount()` 唯一一处 ✓ 与"在哪页/是否预览"无关 ✗）
- **只有"侧栏设置页"强制显示侧栏** ✓（进＝开 ✓ 离开/点设置外＝关 ✓）；其他页面可自由显示/隐藏 ✓
- **分离**：仅"铺满 + 该边居中"可用 ✓（否则可见但禁用 ✓）；主窗按钮**钉端点** ✓ 平台图标**居中** ✓
- **测试台按钮**：默认隐藏 ✓ 三击空白处切换 ✓ **不落盘** ✓ **与主窗按钮相邻** ✓（隐喻：开始菜单旁的搜索框 ✓）
- **主题 = 同一套组件、只改颜色** ✓：规则只在 `sidebar.css` ✓、浅色表**只放颜色变量** ✓、**两张必须同时加载** ✓；
  启动时按配置**应用一次** ✓（标题栏 + 侧栏 + 页面 `data-theme` 同步 ✓）
- **窗口形态三开关要一起审** ✓：`TOPMOST`（**`SetWindowLong` 之后必须重申** ✓）+ `NOACTIVATE|TOOLWINDOW` ✓ +
  **有 owner**（不进 Alt+Tab ✓）；且**永不 `toFront()`** ✗（会激活侧栏 → 连带 owner 抢占平台窗前台 ✗）

---

## 验证纪律（重要）

- **默认不自动验证**：简单改动改完即可 —— 给用户一份"请亲验清单"，由用户真机验收
- **只有用户明确设定"循环修改 + 验证"目标时**，我才自己反复跑验证（编译/测试/探针）
- 需要跑时用 `scripts\verify.bat`（编译 + 测试 + JS 检查一条龙）
- 改渲染/交互类 → 真机验证（离屏探针拿不到 DOM 选区，光标/输入法类**必须**真机）

---

## 指针

- 事实（功能手册：要改 X 去哪）：[`MEMORY/facts.md`](MEMORY/facts.md)
- 决策（含 `状态: 待定`）：[`MEMORY/decisions.md`](MEMORY/decisions.md)
- 坑 / 瓶颈：[`MEMORY/lessons.md`](MEMORY/lessons.md)
- 过程与证据：[`MEMORY/dev_logs.md`](MEMORY/dev_logs.md)
- 素材库（每轮追加、未归档）：`MEMORY/tmp/{YYYY-MM-DD}.md`｜整理台账：[`MEMORY/index.md`](MEMORY/index.md)
- 架构细节：[`docs/project_structure.md`](docs/project_structure.md)
- 废弃归档：`MEMORY/.old/`、`scripts/.old/`、项目根 `.old/`
