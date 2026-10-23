# lessons — 技术教训 · 瓶颈 · 未解决的已知问题

> **用途**：踩过的坑（症状 → 根因 → 修法 → 预防）、连用户都受不了的多轮瓶颈、**尚未解决**的已知问题。
> **不写什么**：不写"现在是什么样"（去 `facts.md`）、不写为什么这么定（去 `decisions.md`）、不写过程流水（去 `dev_logs.md`）。
> **更新方式**：追加 —— 新条目**按主题**并入已有小节（不要另起"第 N 节"式编号）。
>
> **条目来源**：主体是 2026-07 ~ 10 开发过程中逐条积累的；其中三批是**迁入**的 ——
> ① 旧 `AGENTS.md` 第十一节的 50 条（2026-10-05 迁入）；② 分散在旧文档里的 **JavaFX WebView 交互"十七个坑"**（2026-10-05 起离屏实测）；
> ③ **Java API 陷阱**（2026-10-05 实测）。迁入后与后续新条目**按主题合并**，原有的 1~50 编号已取消。

---

## 方法论

- **不猜，量出来 —— 离屏 WebView 实测**：JavaFX WebView 与 Chromium 的布局细节不同，"看起来是 X"往往不是 X。做法：
  ① 生成只含目标 DOM + 项目真实 CSS 的临时 HTML（CSS 内联，避免 `file://` 相对路径问题）；
  ② 小 `Application`：`WebView` 放进 `Scene`，`stage.setX(-4000); setY(-4000); show()`（屏幕外）→ `executeScript` 取 `getBoundingClientRect()/getComputedStyle` 打印；
  ③ `javac` 必须 `-encoding UTF-8`（中文注释按 GBK 会报错）；`--module-path` 要带 `javafx-base/graphics/controls/media/web` 的 **win** jar（`javafx.web` 依赖 `javafx.media`）；
  ④ **采样法最有效**：`setInterval` 每 25ms 记录几何，把"轨迹"打出来，动画类问题一看就清楚；
  ⑤ 临时文件放 `tmp/`（**不要放 `build/`** —— `gradle clean` 会清空，曾因此丢过探针源码）。
- **单一事实来源 + 单一写入点**：只要有"影子状态"（`_prevHeight` / `_prevWasCollapsed` / `_panelShownOnce` / `forcedLocalState`…）就一定会互相拉扯 →
  **渲染的唯一依据 = 期望状态函数；状态变更一律"先落事实来源，再统一渲染"**；DOM 只允许一处写。
- **单一职责要贯彻到"判定权"**：图标提取只判"路径存的值是不是程序"；"目录里该是哪个 exe"归**路径探测流程**；
  "平台是否启用"只**读**路径检查写下的结果，不自己判断 → 越界就会出现"看起来能用、两套规则长期打架"的隐性 bug。
- **探针/测试造的数据必须与真实推导链一致**：曾给"隐藏行"只设 `hidden`，而 `main.js` 是按"是否在 `getSwExistedAccounts` 里"**推导**失效的 →
  该账号同时被判失效，颜色自然是 3 级，我却先怀疑 CSS。**造数据前先读一遍"这个状态真实是怎么来的"**；
  断言失败时先打印真实 DOM（class + computed）再判断是代码错还是测试错。
- **报告现象前先做"两态轮廓比对"再下结论**：曾把"圆角处露背景色"解释成几何必然、劝用户接受，真问题其实是**填充形状比空框小**。
- **别替用户改数据**：曾因"下划线"清洗过账号 ID 里的 `_`，而用户要的是"去掉分割线" → **显示层清洗要慎之又慎**（现已撤销）。
- **"如果…就…"式最高优先级指令 = 条件兜底，不是直接指令**：语义是"**先真正修好；修不好才用兜底**"。
  曾跳过"先修"直接执行兜底 → 被指出"说好的逐字呢"。正确顺序：先真正修复 → 确实做不到才启用兜底 → 并说明"兜底未启用/为何启用"。
- **动手做新组件前，先问一句"我们一直有现成的是什么样"**：任务面板的滚动条我默认写成"始终可见"，
  用户一句"复用我们一直有的设计，比如设置区域的滚动条" → 项目里早有同款（`main.css`：**默认隐藏、悬停才显示 4px 细条**）。
  → **同类 UI 先在 `main.css` 里找既有范式**（`.settings-form` / `.settings-sidebar` / `.sponsor-scroll` / `.ct-scrollbar` 等），
  照抄比自创样式省一轮返工，也保证观感统一。

---

## 远程配置与加解密

- **源文件 → 加密产物**：`scripts/original_remote_global_<vN>.json` / `original_remote_sw_<vN>.json` → `gradle encryptRemoteConfigs` →
  `remote_configs/remote_<global|sw>_<vN>`；改版本号要同步 `RemoteConfigFetcher.BUILTIN_REMOTE_*_VERSION`，再提交推送（客户端按仓库 raw URL 下载）。
- **加解密同源**：`config.CryptoUtils.encryptAndAppendKey`（工具在 `src/tools` 源集，不进应用产物）；单测 `CryptoUtilsTest` 是安全网。
- **候选 URL 永远要有兜底**：候选 = 用户配置 + 内置兜底（`mergeUrls()`）。曾只取用户列表 → 用户清空后日志 `候选URL: 0个`、远程配置永远下载失败。
- **gitee 对 `remote_configs/remote_*` 返回 451**（平台判定违规，与网络无关）→ 候选列表里失败要能自动继续下一个源。
- **代理只由界面复选框控制**（不做自动探测、不默认开启）：历史 `SSLHandshakeException: Remote host terminated the handshake` 的根因是
  **Java 默认不用 Windows 系统代理**（`java.net.useSystemProxies` 默认 false）。
- **代理地址必须归一化**：允许 `http://127.0.0.1:7890` / `127.0.0.1:7890` / 主机与端口分开填 / `[::1]:7890`。
  **不能把含 `:` 的地址原样塞 `https.proxyHost`** —— JDK 会当 IPv6 加方括号，报 `URISyntaxException: Expected closing bracket for IPv6 address …`。
- **改代理立即生效**：`http(s).proxyHost/Port` 是 JVM 属性，`HttpClient` 默认 `ProxySelector` 每次请求都读 → 无需重启；
  `applyProxyConfig` 回传 `requiresRestart` 只在运行期应用失败时提示。
- **HTTP 重定向**：`HttpClient` **默认不跟随**，必须 `.followRedirects(NORMAL)`。

---

## 设置页布局与"分块保存"

- **一个保存按钮管所有校验 → 用户被无关校验挡住**（只想改本地目录却被"远程配置源测试失败"卡住）→ 拆成 代理 / 本地目录 / 远程配置源 三块，**每块只提交自己的字段**。
- **后端天然支持部分提交**：`JsBridge.saveConfigData` 是 `if (data.has("x"))` 逐字段合并，缺省字段保持原值 → 前端分块提交不需要后端改动。
- **按钮可用性来自"本次会话的真实校验结果"**：不要用历史有效标记预置绿框；`updateBlockButtons()` 按块判定（目录块看 `input-ok`；远程源块要求 sw/global 各自测通）。
- **视觉一致性靠变量**：板块介绍 `.config-desc`、标签 `--font-h3`、输入框统一 `padding/font/border-radius`、次级按钮统一尺寸、提示 `--font-xs`；间距归 `.config-divider` 管。
- **路径字符串全链路规范化**：前端 `replace(/\\/g,'/')` + 后端 `Path.toString().replace('\\','/')`，`getActualDirVal`/`saveConfigData` 返回值一并规范化
  （否则弹窗/提示里会出现 `\` 混排）。

---

## 最左栏（`#nav-sidebar`）

- **交互目标**：鼠标"静止"才展开 → `EXPAND_DELAY`(1000ms) + `MOVE_THRESHOLD`(6px)：微动不重置计时，明显移动重新计时，移出立即收起。
- **`mouseleave` 会被吞**：点平台后账号列表加载卡顿，期间的 `mouseleave` 丢失 → 侧栏一直保持展开。两层兜底：
  ① 文档级 `mousemove`（capture）：指针在侧栏外移动且已展开 → `collapse()`；② 展开期间每 400ms 用 `document.elementFromPoint(lastX,lastY)` 校验。
- **别把只读的入口留在最左栏**：入口越少越稳（"统计"按钮已移除，页面与图标资源保留备用）。
- **z-index 体系**：主左栏 `100` > 次级左栏 `50` > 下拉面板 `40` > 默认 `0`；侧栏有 `position:relative` 会创建层叠上下文。
- **`position:fixed` 子元素的 z-index 受父层叠上下文限制**：父容器若设了 `z-index`，子的 z-index 只在父内部有效
  → 下拉面板的 `#mg-dropdown-layer` 设 `40` 后子面板 `z-index:80` 无效，必须把 layer 也调到 `40`。
- **`overflow:hidden` 会裁剪 `absolute` 子元素**（即使设了 z-index）→ 下拉面板必须挂 body 层用 `position:fixed` + `getBoundingClientRect()` 定位。

---

## 设置区窗帘（高度 / 展开收回 / 分割线 / 把手）

- **唯一渲染依据**：`desiredCurtainState(swId)` = ① 全局记录（`settings_height`/`settings_expanded`）② 例外：**未启用平台每次渲染都强制展开**；
  `applyCurtainRender()` 是唯一 DOM 写入点；`setCurtainExpanded`/`setCurtainHeight` 都是"先写记录再渲染"；`_lastRender` 记录上一帧真实状态。
- **未启用平台**：不写记录、不留本地状态 —— 本次访问可临时收起（`applyCurtainRender(override)` 只影响这一次渲染），下次渲染依旧强制展开。
- **完备性判定要在渲染前就确定**：进入平台时**同步**跑一遍三个路径的 `checkPath`（同步桥），否则"先按记录渲染、200ms 后检查回来又强制展开"会闪；只有"启用 ↔ 未启用"真变化才重渲染（`swEnabledKnown`）。
- **面板与内容区必须同值**：`applyPanelHeight(h)` 同时设 `panel.maxHeight` 与 `content.maxHeight`。任何 `- N` 的"预留"都会让"动画路径"与"静态路径"语义不一致 → "闪一下 / 冲过头再弹回"（曾写死 `-20`，实测该处固定差值其实是 0）。
- **内容区 `max-height` 是隐形锁**：CSS `.manage-settings-content { max-height:180px }` 会限制面板实际高度 → 自由高度动画前必须解除（`max-height:none`），否则涨不上去。
- **动画期间内容区要解除上限**，动画结束再恢复（否则内容永不溢出、滚动条不再出现）；**`transitionend` 在 JavaFX WebView 不可靠 → 用 400ms `setTimeout` 兜底**。
- **`transition:none` 快照与恢复 transition 必须在不同帧**：单 `requestAnimationFrame` 分离"快照帧"与"过渡帧"（`offsetHeight` 强制重排后改值）；双 RAF 不一定更好（可能引入延迟）。
- **收起时 `scrollHeight === 0`**：读真实高度必须先 `remove('collapsed')` 再读，然后快照回 0、再过渡。
- **首帧没有"上一个高度"**：面板还没按平台显示过时不做动画（否则会看到 `16 -> 180 -> 200` 这种假动画）；只有"记录本身是收起"才值得播 0→H 的展开动画。
- **`_prevHeight` 取语义高度**（`parseInt(panel.style.maxHeight)`）而不是渲染高度（渲染高度含 padding/border，作为起点会多算一截）。
  （反过来，**判断"当前是不是收起/多高"用 `getBoundingClientRect().height` 更可靠**：它返回实际渲染高度，`style.maxHeight` 可能是空串或被 CSS 覆盖。）
- **inline style 残留会污染状态恢复**：收起动画设了 `panel.style.maxHeight='0px'` 却未清除 → 切平台时 `classList.remove('collapsed')` 盖不住 inline style，面板卡在高度 0。
  → `applyCurtainState` **展开时显式置 `''`、收起时显式设 `'0px'`**。
- **收起状态禁止拖动底部分割线**（高度 0 时拖动会瞬间跳到最小高度、与鼠标脱节），并把拖动区光标切成 `default`；拖动中 `transition:none` + 夹取 `min=100 / max=content.scrollHeight+40`，**只在松手时落库**（避免高频写盘）。
- **光标别用内联 style 逐点设置**（代码路径太多会漏）→ 用 **CSS 驱动**（`body.curtain-collapsed`）+ **MutationObserver 监听面板 `collapsed` 类**同步 body 类。
- **把手是全宽 SVG**：`width:100%` + `preserveAspectRatio="none"` → **viewBox 宽度必须随元素宽度同步**（窗口 resize 也要调 `initHandleSvg()`），否则被非等比拉伸（"点一次把手才恢复"就是这个）。
- **把手与面板容器一体化**：面板 + SVG 把手包在 `#manage-curtain-container`（`position:relative`）里，把手 `position:absolute; bottom:-20px` 自动跟随容器底部
  → 移除所有 JS 手动定位（`getBoundingClientRect`、`style.top`、RAF 跟随循环）。把手造型：`position:absolute; bottom:0; transform:translate(-50%,50%)` 半露、`width:36px; border-radius:10px`、仅 `∧`/`∨` 符号、hover 变主题色。
- **跨平台切换 = 同一页面内的高度变化动画**：先记录 A 平台当前高度 `_prevHeight`，切到 B 后直接调已验证的 `animatePanelHeight(savedH, null, _prevHeight)`。
  **已验证可复用的动画函数就直接复用，不要重写**；不引入新分支、不手动控 transition、不复刻展开/收回逻辑。
- **平台状态持久化**：展开/收起按平台独立存 `LocalSwConfig.<swId>.settings_expanded`（`updateSwField` 写、`getSwConfig` 读），切平台先读后应用。

---

## 账号数据来源 · 名称链 · 头像链

- **来源 = 磁盘扫描**：`JsBridge.getSwExistedAccounts(swId, 'origin'|'coexist')` → `SwInfoFuncCore.getSwAllAccountsExisted`
  （数据目录子目录 − 排除目录；共存 = 安装目录里匹配 `executable_wildcards` 的 exe）。
- **详情 = SwAccData**：`getSwDetailData(swId)` 注入 `display_name`（`AccInfoFuncCore.getAccOriginDisplayName`）。
- **无效账号 = SwAccData − 原生 − 共存**：按自身类型并入原生/共存表（`invalid:true` → 灰字 + "失效"标签 + **永远置底**）。
- **共存账号判定**：SwAccData 节点带 `linked_acc` → 共存；兜底看 id 是否 `.exe`。
- **三个曾让共存表恒空的后端缺陷**：① 读错配置键（`exe_wcs` vs 常量 `EXECUTABLE_WILDCARDS`）② `accountOps` 传 null → `ensureCoexistAccFormatted` NPE
  ③ `inst_path` 可能是**目录**（WeChat/DouYinIM）却一律 `getParent()` → 抽 `resolveInstDir()`。
- **平台数据维护按事件流**：进入平台 → `PlatformEnteredEvent` → 后台 `resolvePidAccountMap → associateCoexistAccounts → updateAccLoginData`；
  字段更新 → `AccountDataChangedEvent` → 前端**定向更新单元格**（不整表重渲染）。
- **名称链**：`remark（本地） > nickname > alias > 账号 ID`；**共存账号一律参考 `linked_acc`**（自身只认 remark）：
  `remark > 链接账号 nickname > 链接账号 alias > 链接账号 id > 自身 id`。
- **头像链**：本地 `{userDir}/{sw}/{acc}/{acc}.jpg` → URL 下载（以 `/0` 结尾）→ SVG 文字回退；
  共存：自身本地 > 链接账号本地 > 链接账号 URL > 默认。异步接入选 `JsBridge.getAccAvatarAsync`（后台线程 + `runLater` 推送）；**SVG 回退不降级替换已有真实图片**。

---

## 平台图标（程序图标）

- **尺寸**：`FileSystemView.getSystemIcon(File, w, h)` 在 Windows 支持任意尺寸（实测 48/64/128/256），公开 API、**不需要 `--add-exports`**；无参重载只给 16×16（"模糊"的根源）。
- **只认程序**：`isFile() && .exe` 才提取；`inst_path` 是目录就什么都不做（拼 executable 属路径探测流程的职责）。
- **缓存**：`{用户数据目录}/{swId}/{swId}.png`；有图且 `inst_path` 未变（比 `icon_src_path`）→ 直接用；缺图或路径变了 → 重新提取覆盖；**提取失败什么都不做**，保留原图。
- **旧路径的坑**：`sun.awt.shell.ShellFolder.getIcon(true)` 需要 `--add-exports java.desktop/sun.awt.shell=ALL-UNNAMED`，且返回**惰性图片**（`getWidth(null)` 得 -1）→ 必须 `new ImageIcon(img)` 包一层。

---

## 表格（列宽 / 占位列 / 行高 / 悬浮选中）

- **纯视觉效果一律用 `transform`，绝不让元素脱离文档流**（2026-10-07 连踩三次）：`transform: translateX()` 是**绘制阶段**位移、**不参与布局** → 行高、列宽、`border-collapse` 折叠边框、`vertical-align` 全不受影响。
  反面做法（改 `position:absolute`）：① 折叠边框是相邻单元格**共享**的，动一个会让边框重新分配、行高跟着变；② 脱离流后行高只能靠测量值硬撑，而单元格 `height` 只是**最小高度** → 必然差几像素；
  ③ 绝对定位让 `vertical-align` 失效、基线跑偏，`height:100%` 更会按更大的包含块算（列头被拉成整表高）。
  **判断标准**："我要的效果会不会让浏览器重新排版？" 会 → 改用 transform/opacity；真需要改流，就**松手后一次性重排**（列换序的两阶段模型就是这么分工的）。
- **列宽取自 `<col>`**：隐藏列只给 th/td 加 `display:none` 不够 —— 声明的列宽总和 > 表格宽时浏览器会**重新分配**，于是"最右列怎么拖都改不动"。修复：隐藏列的 `<col>` 同时 `width:0px` + 隐藏类。
- **表格宽度 = 可见列宽总和 + 占位列**：`table.style.width` 绝不用容器宽填充（fixed 布局会按比例拉伸真实列）。
- **占位列（`_filler`）不是列**：不进 `columns`、不参与排序/显隐/列菜单；宽度 = 容器可视宽 − 可见列宽总和（≥0）。价值：① 所有真实列右侧都有邻居 → 拖拽热区不再压在表格边界 ② 占位单元格属于该行 → **整行悬浮/选中感应区天然覆盖容器宽**。
- **取整**：拖拽宽度与总和都 `Math.round`，避免小数宽度让"总和 + 占位列"超出容器 1px 冒出横向滚动条。
- **列配置持久化**：写嵌套 `account_columns.<表id>`；`saveGlobalConfig` 是**顶层浅合并** → 先读出 `account_columns` 再合并本表，否则清掉其它表配置；列定义变化（删/加列）要能识别"陈旧列名"并整份作废回默认。
- **行高不齐常因某列多/少一个元素**：账号表与程序表统一 32px 头像列 + `tbody tr[data-acc-id] { height:44px }` 兜底最小高度。
- **`td` 千万不能设 `display:flex`**：它就不再是 table-cell，浏览器插入**匿名 table-cell** 包住它，td 的 padding/border 画在内层 → 该列底边与同行错位（"名称下面多一条横线"）。要 flex 就在内层加 `div`；内层 flex 容器不要 `overflow:hidden`（会裁掉绝对定位/超高按钮的边框），用 `min-height` 保证按钮放得下。
- **行悬浮/选中着色**：`tr` 背景覆盖不到表格右侧空白 → 用绝对定位色块层（`.acc-row-highlight`/`.acc-row-sel`），`z-index:-1`，容器 `.acc-table-scroll { z-index:0; isolation:isolate }` 形成层叠上下文；
  **色块必须用不透明等效色**（`--bg-row-hover`/`--bg-row-selected`），半透明叠在容器上会二次变深、深浅主题不一致；**选中行不再显示悬浮色**；移除 `tr.selected` 背景与 `tr{transition:background}`。
  悬浮按钮要**在文档流内**才会"挤占文字 → 名称以 `…` 结尾"（用户要的观感），背景要不透明，否则发虚。
- **给"选择器组"加样式前，先逐条确认组里每个选择器都该改**：曾把"昵称列用雅黑"写进 `.manage-text-cell, .manage-alias-cell, .manage-nickname-data-cell` 共用组 →
  程序表的名称/版本/路径（同属 `.manage-text-cell`）也一起变雅黑（用户肉眼发现、探针没覆盖的回归）。**一处样式只影响一类元素时，就单独写一条规则。**

---

## 交互与反馈

- **"禁用"的菜单项要保留它的动作标识**：把"删除"对正常账号改成禁用时写成 `<div class="acm-item danger disabled">` 却**漏了 `data-row-action="delete"`** →
  ① 探针按 `[data-row-action]` 查不到（像"没渲染"）② 事件绑定循环也覆盖不到。正确：禁用项**照样带动作标识**，只在点击处理里 `if (classList.contains('disabled')) return;`。
  **通用规则：UI 的"禁用"属于行为层判断，不要让它改变元素的结构/标识。**
- **"按钮点了没反应"比"弹窗说明原因"更糟**：批量删除最初对"全选正常账号"直接静默 return → 用户疑惑为什么点不了。正确：**流程照常走（照弹确认框）**，文案说明哪些会被跳过，"不作为"只发生在**执行层**。
- **交互反馈要归位**：曾用 `flashTitle()` 把平台标题临时换成提示（"已隐藏/已显示/已删除"）—— 这是**借标题当通知区**，已整套移除（两份实现 + 8 处调用）。
  状态变化优先靠**就地可见的变化**：按钮文案、行内标签、行置底、行消失；真要提示就放在**该功能所属区域内部**，不要跨区域借用别的控件。
- **`overflow:hidden` 裁剪绝对定位子元素** → 下拉面板要挂 body 层（`position:fixed` + `getBoundingClientRect()` 定位）；
  窗帘把手在面板内部时：展开态 `overflow:visible`、收起态 `overflow:hidden`。
- **CSS 伪元素与 HTML 内容冲突**：`::after { content:'▼' }` 与 HTML 里的 `▼` 同时存在 → 双图标。只用一种方式（HTML 文字 + `::before` 背景方块）。
- **SVG `pointer-events:none` 会阻止 click**：需绑在内部 `pointer-events:auto` 的子元素（如热区 `rect`）上。
- **WebView 拦截鼠标** → 用透明 Region 覆盖层绕过。
- **`location` listener 二次触发** → `suppressLinkIntercept` 标志。
- **窗口 maximized 时拖拽** → `DRAG_THRESHOLD=4` 阈值。
- **`getEl` 作用域隔离**：复制出的页面与原始页面有相同 DOM ID，`document.getElementById` 恒返回第一个 → `getEl` 改为
  `querySelector('#page-main #' + id) || document.getElementById(id)`，优先在目标页面内找；**`bind()` 也必须走 `getEl`**，否则事件绑到原始页面元素。
- **跨页面联动用 `document.getElementById`**：主侧栏 `#nav-platform-list` 不在 `#page-main` 内，不能走 scoped `getEl`。

---

## JavaFX WebView 的坑（前端交互实测）

> 结论都来自离屏 WebView 实测，不是查文档猜的；做前端交互前先对照一遍。

1. **`window.confirm()` 恒返回 `false`**（`alert()` 也什么都不做）—— 未装 confirm handler 时既不弹窗也不返回 true。
   曾把"删除账号"确认全走 `confirm()` → **点删除永远静默取消**且无任何提示。修法：自建 HTML 弹窗（`JFC.modal.confirm`），可主题化、可键盘操作、不打断 WebView 焦点。
2. **`keydown` 里 `event.key` 是空字符串**（`event.code` 也空），只有 `keyCode`/`which` 正确：a→65、1→49、空格→32、F5→116、Ctrl+A→65、Esc→27、Enter→13。
   → 所有 `event.key === 'Enter'/'Escape'/'ArrowX'` 判断在这台 WebView 里**全部失效**（快捷键录不进普通字符、标题框 Enter/Esc 不生效、退格删不掉字）。
   修法：统一走 `JFC.keys`（keyCode 为主、`key` 兜底），键名与 Java 侧 `JsBridge.keyNameOf` 对齐。
3. **同一单元格反复挂 `stopPropagation` 的 click 会累积**：单元格若"只重建本格内容"就一直存活，第 N 次进入编辑后点击被自己挡住（tbody 委托收不到）→ "点了没反应"。
   修法：不要在单元格上挂这类监听（委托里判断 `e.target.tagName === 'INPUT'` 就够）。
4. **不要在 `mousedown` 阶段重建整表 DOM**：编辑提交若在 document 的 mousedown 阶段 `render()`，用户这一下点击所在的元素会被换掉 → 后续 click 落空（"点别处要按两次"）。
   修法：同步只还原本格，**保存与整表重排延后一拍**（`setTimeout(…, 0)`）。
5. **`closest()` 只接受选择器字符串**（传元素抛 `SyntaxError`），而监听器里的异常不中断别的代码、只让**这一个处理器的第一行静默死掉**。
   实际踩坑：`if (ev.target.closest(cell)) return;` → "点击框外结束编辑"的逻辑**从来没生效过**。修法：`cell.contains(ev.target)`。
   **排查"点了没反应"时，先打开 WebView console 看有没有未捕获异常**（探针默认静默 console —— 验证时别把 console 也一起静音）。
6. **原生表单控件会"先画一帧原生外观，再套你的样式"**：`input[type=checkbox]` 表现为**先出现纯方形、随后才变圆角/主题色**。
   修法：别让原生控件承担视觉 —— `<label>` + **透明 input（只当状态载体）** + 自绘 `<span>`，从第一帧就是最终样子。
7. **中文"模糊"的锅不在字体，在抗锯齿模式**：JavaFX（含 WebView 内文本）**默认就是 LCD 次像素抗锯齿**。实测（离屏截图像素统计，5 个字体分区 × 4 种开关）：
   | 配置 | 边缘对比度 | 彩色边缘占比（LCD 特征） |
   |---|---|---|
   | 默认 | 51.3 | **97.0%** |
   | `-Dprism.lcdtext=true` | 51.3 | 97.0%（= 默认值，无变化） |
   | `-Dprism.lcdtext=false` | **53.5** | **0.0%** |
   | `-Dprism.text=t2k` | 51.3 | 97.0% |
   四个字体分区（宋体 / 等宽+雅黑 / 本机默认 / 雅黑基线）的边缘对比度**完全相同**（51.3/50.2），只有墨量差异 → 换字体解决不了"发虚"。
8. **几何居中 ≠ 视觉居中**：旋转 45° 的"勾"（L 形）几何居中后**墨迹中心仍偏下 1.25px**（实测），要 `calc(-50% - 1.25px)`。
   凡**不对称图形**（勾、箭头、折角）都必须像素实测校正。
9. **别指望 `font-family` 列表能"按字符集分字体"**：等宽族缺中文时 WebKit 走**系统 CJK 回退**，列表里排后面的中文字体根本轮不到；
   `@font-face + unicode-range` 在 JavaFX 这个 WebKit 版本里**也不生效**（中文放最前会把英文一起吃掉）。
   → 只能**显式分段**：JS 按字符集把文本拆成多个 `<span>` 各自指定 `font-family`。
   **鉴定"某元素用了哪个字体"的可靠办法**：离屏渲染同一个字比**墨块数**（同字号同字重：雅黑 175 / 宋体 146 / 等宽回退 131）；逐像素指纹对字重、字号、亚像素位置过于敏感，容易假结论。
10. **JavaFX WebView 的 `contenteditable` 基本不可用**：为"编辑态中文雅黑 + 英文等宽"把名称编辑框换成 `contenteditable div`（配分段 + 按字符偏移恢复光标 + 组字期不动 DOM）→ **用户实测连正常输入都不行**，只能回退 `<input>` + 统一字体。
    → **别为"字体/样式上的小收益"替换掉成熟的原生控件**（输入、输入法、选区、撤销都是浏览器实现好的）；这类交互**离屏探针验证不了**（`window.getSelection()` 在无窗口焦点的窗口里恒空），必须真机试。
11. **"同色边框 + 背景"是两层几何，圆角处会露缝**：要"填满"的正确做法是 `background-clip: border-box` + **`border-color: transparent`**（由背景独占整块形状）。
    ⚠️ **2026-10-06 又在按钮上犯了一次**（`background: primary` + `border-color: primary`），用户："填充用整块填充，不要还搞边框+内部，每次都能看到中间有空隙"。
    → **凡是"要填满"的元素（勾选框、按钮、滑块、色块…）一律：border 要么不加、要么透明；绝不用同色 border 凑形状。** 验证办法：数"形状内部既非填充色也非勾色"的像素，一整块填充应为 0。

---

## JS ↔ Java 桥

- **Java varargs 与 JS bridge 不兼容**：Netscape JSObject 桥无法把 JS 参数映射到 Java `String...`（方法描述符多一个 `[String` 槽位 → 反射匹配失败）→ 必须用固定参数，pathKeys 用 JSON 字符串传。
- **boolean 可能被序列化为字符串** → JS 端用 `=== true` 严格比较。
- **`_handleAsync` 第三参必须是字符串**：`_handleAsync(type, cbId, jsonStr)` 仅当 `typeof jsonStr === 'string'` 才 `JSON.parse`。
  Java 端 `pushToJs` 若直接嵌 JSON 对象字面量，JS 侧 `data` 为 null → 必须把 JSON **再编码为 JS 字符串字面量**（对 SVG data URL 里的单引号也安全）。
  ⚠️ 同理：**异步回调签名是 `function(type, data)`** —— 写成单参数会把 `type` 字符串当结果（表现为"活干完了却提示失败"）。
- **路径里的反斜杠会让 JS `JSON.parse` 静默失败**：Windows `File.getParent()` 返回 `\` → Jackson 序列化成 `\\` → 嵌进 JS 单引号串时被解析成 `\` → JSON 非法转义 → `JSON.parse` 抛错被空 catch 吞掉。修复：所有路径入库前统一 `normalizePath()`。
- **桥注入时序**：`DOMContentLoaded` 时 bridge 尚未注入（Java 端在页面加载完成后才 `injectJsBridge()`）→ 页面初始化要调桥方法，应由 `MainWindow.injectJsBridge()` 末尾主动 `executeScript` 触发。

---

## 配置与路径

- **配置拆分**：代理 / 远程 URL 存 `RootConfig.json`（不随数据迁移移动）；软件偏好存 `LocalGlobalConfig.json`。
- **配置实时读取**：`JsonConfigStore.getData()` 每次自动 `reload()` 从磁盘解析；读写锁保证并发安全；`reloadInternal()` 不持锁供 `getData()` 调用。
  （→ 反过来说：**热路径不要反复直接读配置**，远程配置已在配置层做了长期缓存。）
- **`saveConfigData()` 里 `updateGlobalConfig` 必须在所有字段收集完毕后调用**，不能提前（否则丢字段）。
- **配置文件名 / 目录名**：双驼峰 PascalCase（`RootConfig.json`、`RemoteSwConfig.json`）；用户数据目录用 `UserFiles`/`DevUserFiles`（非 `user_files`）。
- **`Map.of(k, null)` 一定抛 NPE**（`Map.of` 不接受 null 键/值），而它常被写成"把这个字段清掉"的意图；因为外面套着 `try/catch`，症状是**"某些逻辑从来没生效过"**。
  本项目一次扫出 **8 处**（2026-10-05 全修）：`AccOpsProvider.ensureCoexistAccFormatted` ×3、`AccOperatorCore`（清 pid+has_mutex）、`AccInfoFuncCore.unlinkHwndOfAccount`、
  `AccInfoFuncCore.deleteAvatarForAcc`（文件删了却返回 false、`avatar_url` 没清）、`SwConfigAccessor.getSwSettingAsString`（每次调用必 NPE，两个调用方受害）、`SwHexUtils` 空结果占位。
  替代：`Collections.singletonMap(k, null)` 或 `HashMap`；**要"删字段"就显式写 `remove` 语义**。写之前先问："这个 map 的 value 会不会是 null？"
- **`ConcurrentHashMap` 不允许 null 值** → 多线程合并结果用 `Collections.synchronizedMap(new LinkedHashMap<>())`。
- **`AppEnv` 运行环境判断**：先读 JVM 属性 `run.mode`（DEV/TEST/PROD），再自动检测 code source 路径是否以 `.jar` 结尾 → PROD:DEV；`Launcher` 的 `--dev` 改为设 `run.mode=DEV`。
- **路径检查必须先判存在**：`checkPath` 中 `Files.exists()` 为 false 直接返回"路径不存在"（红），再进 `isValidSwPath` 详细检查（r_concat/l_concat/r_contain/l_contain）；
  详细提示用 `SwAdapterChecker.checkSwPathDetail()` 返回 `{valid, reason}`。
- **路径规范化统一入口**：`SwPathDetective.normalizePath()`（去引号、`\`→`/`、盘符大写、去末尾分隔符）；**所有 PathEntry 构造点都必须调用**。
- **下拉面板缓存合并策略**：每次打开重新探测，但新结果与旧缓存**合并**（同路径覆盖更新、新路径追加、旧独有保留），避免 DLL 路径依赖软件路径时因清空缓存丢旧结果。
- **内存映射查询**：用 `VirtualQueryEx` + `GetMappedFileNameW`（`Kernel32Ext` 扩展）遍历进程内存区域，等价 Python `psutil.Process(pid).memory_maps()`；
  `GetMappedFileNameW` 返回 NT 路径需经 `convertNtPathToWin()` 转盘符路径。日志标签：模块列表 `[路径内存映射-MEMMAP]`、匹配 `[路径内存映射-MATCHED]`（DEBUG 级）。

---

## Gradle / 工具链（2026-10-22 实测）

- **VS Code 的 Gradle 扩展没有 gradle home 设置**：`java.import.gradle.home` 是 Java 扩展的键，Gradle 扩展不读；
  它找不到项目 wrapper 就回退自带 tooling-api（9.8.1）并联网下载 → 内网/代理环境下 10s 超时。
  **解法是给项目加 wrapper 并把 distributionUrl 指向本地 zip**（本机安装目录直接打包）。
- **Gradle 的 JVM 不认 Windows 系统代理**（`127.0.0.1:7890`），`~/.gradle/wrapper/dists` 里只会留下空 `.part`。
- **zip 必须有目录项**：`Compress-Archive` 打的包 Gradle 解压报 `NoSuchFileException`，改用 `tar.exe -a -c -f` 才通过。
- 探针可以直接用扩展自带的 tooling-api jar 跑（`tmp/probe/ToolingProbe.java`），不必等编辑器的界面。

## 工程习惯（省时间的小事）

- **改代码的批量脚本必须识别行尾**：项目 JS 是 **CRLF**，脚本按 `\n` 匹配会 0 命中（曾 9 处替换全落空）。
- **PowerShell 里写含引号/中文的替换脚本容易炸** → 用 Node 脚本文件（用编辑工具写，避免 shell 引号地狱）；**改文件优先用编辑工具，不要 shell 批量替换**。
- **`.bat` 保持 LF 行尾**（历史原因），改完检查 CRLF 计数为 0；**UTF-8 BOM** 问题曾靠 Bash `cat >` 写规避。
- **`javac` 记得 `-encoding UTF-8`**；`--module-path` 别漏 `javafx.media`。
- **反射调 JDK 内部 API 记得三件套**：`--add-exports`（`build.gradle.kts` 的 `applicationDefaultJvmArgs` + `run` 的 jvmArgs、`scripts/package-exe.bat` 的 `--java-options`）、异常兜底（失败只降级不崩）、惰性加载处理。
- **内存文件只做"精确替换/追加"**，不要用截断式脚本改写（曾把 `todos.md` 截断过一次）。
- **构建脚本都走 Gradle**（2026-10-06 实测更正）：`run.bat` = `gradle run --no-daemon`；`build-run.bat` = 先 `gradle compileJava compileTestJava`（编译失败即止）再 `gradle run`。
  所以 `run.bat` 同样会编译/复制资源（Gradle 任务链 `run → classes → compileJava + processResources` 自动决定）；
  **前端改动重启就生效**，正是因为 `processResources` 把 `src/main/resources/**` 复制进 `build/resources/main`，而页面走类路径 `getResource("/web/index.html")` 加载。
  （旧记录写的"`run.bat` 仅运行、不触发编译"是**错的**。）
- **纯复制迁移法**：从旧代码完整复制 DOM + JS 到新位置、保持 ID/逻辑完全相同，再按实际效果逐步调试 —— 远比"理解后重写"可靠（`page-main` 复制自 `page-manage`，`main.js` 复制自 `manage.js`）。
- **"旧版有、新版漏了"的功能要对着旧实现核一遍**：平台版本号在新实现里只从**文件名**正则抠（`WeChat_8.0.47.61.exe` 能抠、`WeChat.exe` 抠不到 → 版本列长期空白），而旧版 Python 一直调 `win32api.GetFileVersionInfo` 读**文件版本资源**。
  迁移时漏掉的往往不是"新功能"，而是**旧行为** → 凡"看起来简单"的函数（版本号、路径、转义）都要和旧实现逐行对一遍。
- **静态 `init` 被当实例方法调用 → 单例拿到"未初始化的实例"**：`ConfigManager.getInstance()` 曾写 `new ConfigManager(); mgr.init(false);`，而 `init` 是**静态**的
  —— 它自己 new 并初始化**另一个**实例赋给 `instance`，紧接着又被这个**未初始化**的 `mgr` 覆盖。只要 `getInstance()` 是首个入口（独立探针/工具会）就 `userDataPath == null` → `getUserDir()` NPE。
  **教训：单例初始化只保留一条路径；静态方法不要通过实例引用调用**（编译器不报错，语义却是全局的）。这类 bug 只在"非正常入口"暴露 → 探针的价值正在这里。
- **后台会话 worktree 隔离可关闭**：`.claude/settings.json` 设 `"worktree": {"bgIsolation": "none"}` 后后台会话可直接编辑主目录文件（该文件被 gitignore，仅本地）。

---

## 日志系统

- **日志文件编码必须显式写 `<charset>UTF-8</charset>`**：logback 不写就用**系统默认**（中文 Windows = GBK）→ VSCode 里满屏乱码。文件与控制台两个 encoder 都要写。
  反过来读**历史**日志时：`Get-Content -Encoding Default`（= ANSI/GBK）；**用 UTF-8 去匹配中文会一条都搜不到**（用纯 ASCII 的时间戳搜就能绕开）。
- **日志目录属性的设置时机比位置重要**：logback 在**第一次 `LoggerFactory.getLogger()`**（往往是某类 `static final Logger` 的**类加载**）就把文件**定死**了 → 之后再 `System.setProperty("jfmultichat.logdir", …)` 完全无效。
  → 必须**入口第一行**、任何 logger 之前算出最终目录（`AppPaths.resolveLogsDirEarly()`：读 `RootConfig.user_data_path`，读不出回落 APPDATA）；`--dev` 也要在它**之前**处理（Dev/Prod 是两个 RootConfig）。
- **没有入口就没有属性**：`gradle test` 不经过 `Launcher` → 属性为空 → `${jfmultichat.logdir:-logs}` 回退成**相对路径** → 日志写进**进程工作目录**（= 项目根）。
  两手一起堵：给所有 Test 任务设 `systemProperty("jfmultichat.logdir", …)` + `src/test/resources/logback-test.xml`（**只打控制台**）。
- **`logback.xml` 的属性必须给默认值回退**：`${jfmultichat.logdir:-logs}`（`<file>` 与 `<fileNamePattern>` 两处都写），否则任何绕过 `Launcher` 的入口会在 cwd 生成 `jfmultichat.logdir_IS_UNDEFINED/`。
- **JUL 不装桥就不会跟 logback 同编码**：JavaFX / JDK 内部走 `java.util.logging`，它用自己的 `SimpleFormatter` + 系统默认编码 → 控制台头几行固定乱码。
  项目本来就依赖 `jul-to-slf4j`，只差没装桥 → 入口最早处 `SLF4JBridgeHandler.removeHandlersForRootLogger() + install()`（顺带让 JUL 也受 logback 级别管）。
- **控制台乱码要"两边"都对**：JVM 发 UTF-8（`-Dfile.encoding` + `-Dsun.stdout.encoding`/`-Dsun.stderr.encoding`，JDK 18+ 叫 `stdout.encoding`）**且**终端按 UTF-8 解（`chcp 65001` + `[Console]::OutputEncoding`）。
  只改一边照样乱码。VS Code 里想"覆盖内置 profile"要用**同名**（`"PowerShell": {...}`）—— `terminal.integrated.defaultProfile.windows` 只接受**内置名**。
- **日志级别的判断标准（用户 2026-10-11）**：**正在研究/排查的功能点用 DEBUG**（好找：把对应包或 logger 调 DEBUG 就能集中看）、**成熟功能用 INFO 并尽量合并条数**。

---

## Windows 句柄 / 进程 API

- **`DuplicateHandle(DUPLICATE_SAME_ACCESS)` 必须给"目标进程"**：复制到本进程要传 `GetCurrentProcess()`；传 `null` 只在 `DUPLICATE_CLOSE_SOURCE` 时合法 → 传错就是"扫 30 万条、命中 0 条"。
  关闭**别的进程**的句柄，标准技巧正是 `DuplicateHandle(源进程, 句柄, NULL, NULL, 0, false, DUPLICATE_CLOSE_SOURCE)`。
- **不要用 `NtQueryObject(ObjectBasicInformation)` 预探名字长度**：本机（Win11 26340 / JDK 17）这条调用**恒返回 `STATUS_INFO_LENGTH_MISMATCH(0xC0000004)`**，
  据此提前 return 会把**每个**句柄都当失败跳过。正确做法：直接给足缓冲查 `ObjectNameInformation` / `ObjectTypeInformation`，真不匹配时按返回长度扩容重试。
- **`NtQueryObject` 对某些对象类型会阻塞**（管道/同步对象）→ 见下文"句柄与窗口匹配的性能"：**别整条链路加锁/串行硬等，而是给单次查询加超时**（原先"别上多线程"的建议已被更新）。
- **性能：别重复扫描已知干净的 PID**：多开 N 个实例后同平台 PID 累积（每个实例自带几百句柄），逐个复制+查名的成本线性膨胀（实测 5 个 java 子进程 ≈ 931ms）。
  用**全局共享的"已知无互斥体 PID"容器**跳过它们（实测 931ms → 0ms）。⚠️ **该容器已改为软件生命周期长期有效**（早期版本带 10s TTL，现已去掉）。
- **`CreateProcess*` 的 `lpApplicationName` 不要用正斜杠**：项目内部路径统一规范化成 `/`，直接喂进去**实测失败** → 调用前 `replace('/', '\\')`。
- **降权启动：先判断自己是不是管理员**
  - 管理员 → 借 explorer 令牌（`GetShellWindow` → `GetWindowThreadProcessId` → `OpenProcessToken(TOKEN_DUPLICATE)` → `DuplicateTokenEx(SecurityImpersonation, TokenPrimary)` → `CreateProcessWithTokenW`）；
  - **非管理员 → 直接 `CreateProcess`**（子进程继承中完整性令牌，本来就是普通权限）；此时用 explorer 令牌会 **`ERROR_PRIVILEGE_NOT_HELD(1314)`**（普通进程没有 `SeImpersonatePrivilege`）；
  - 兜底：`explorer.exe <exe>` 代启（explorer 是普通权限）；
  - 判定手段：`OpenProcessToken(GetCurrentProcess())` + `GetTokenInformation(TokenElevation)`；验证手段：让子进程跑 `whoami /groups` 看 "Mandatory Label"（父 High / 子 Medium）。
- **`CreateProcessWithTokenW` 对"超长 + 内嵌引号"的命令行会报 `E_INVALIDARG(0x80070057)`** → 把复杂命令写进 `.bat` 再 `cmd /c <bat>` 更稳（应用自身只传 exe 路径，不受影响）。
- **"空集合"与 `null` 的语义必须分开**：`findHandles(pids=[])` 若和 `null` 一样被当成"不限制进程"，就会去扫**全部**系统句柄（30 万条、几分钟）—— 缓存全部命中（候选为空）时踩到的真事故。
  约定：**空集合 = 没有目标（立刻返回）；`null` = 不限制**。

---

## 句柄与窗口匹配的性能（用日志时间戳定位，不靠猜）

- **`NtQueryObject(ObjectNameInformation)` 在命名管道句柄上会阻塞**：实测某 WeChat 进程里 1200 个候选句柄中的一个卡了 **13.4 秒**（同一段代码前两轮只要 120/250ms → "时快时慢"）。
  → 名字查询必须**带超时**（用 **cached 线程池**：线程被卡住时会自动再开一个，不拖累整轮；超时的句柄直接跳过）。类型查询（`ObjectTypeInformation`）不阻塞，可内联。
- **COM 的 `CoCreateInstance` 不要放在热路径**：UIA 每次查询都重建 `IUIAutomation` → 单次 ~235ms；改 **ThreadLocal 复用**（只释放 element）→ 毫秒级。
- **UIA 只能当"兜底"，且要整条规则一起兜**：Win32 类名先扫（1ms 级），**只有整条规则一个都没命中**时才用 UIA 类名重扫 —— 否则每个窗口都要付 UIA 的代价（窗口一多就是几秒）。
- **轮询"等窗口出现"时，只对**新出现**的窗口做规则匹配**：否则每轮轮询都把所有已有窗口重跑规则（含 UIA 兜底）—— 新进程先冒出来的往往是一堆辅助窗口，全都不匹配，纯浪费。记一个 `seen` 集合：匹配过但不匹配的窗口不再重复匹配。
- **缓存"登记了"≠"生效了"**：`KILLED_PID_AT` 一开始**只登记不过滤**（读时没查它）→ 看日志才发现每轮仍打印全量 pid、候选句柄随实例数线性膨胀。**加缓存要连着"读取侧过滤"一起验**。
- **测量方式**：性能问题别靠猜 —— 在关键步骤打**耗时日志**（查杀耗时 / 规则匹配 / 扫已存在窗口 / 启动 / 等新窗口），配合用户日志里的**精确时间戳**，一次就能定位（本次三个瓶颈都是这么找出来的）。

---

## 文档与记忆体系维护（2026-10-12 实测）

- **手写的逐节链接索引必然腐烂**：`memory.md` 曾有 100+ 条手写 wikilink，维护成本随条目线性增长、收益递减 → 很快停在某一版（还漏了新条目）。
  → 索引只保留**台账**（文件分工 + 整理记录）；逐节检索交给 grep 与 IDE 大纲。
- **"现况"与"历史"混在一个文件里，早晚互相污染**：`facts.md` 里 400+ 行是历史、且与 `dev_logs.md` 有大量**同名小节** →
  规则：描述"现在"的文件（`facts.md`）**只允许就地重写**、不留旧版本；描述"过去"的文件（`dev_logs.md`）**只追加**。
- **同一文件内的重复识别法**：同一主题出现两批（无编号批 + 编号批）时，**逐对读两边**判断谁是超集 →
  删子集，并把子集里**真正独有**的细节**回填**超集（本次仅 2 处：两个测试用例名）。
- **编辑工具是删除操作的安全网**：`edit` 要求 `old_string` **精确匹配**（不匹配直接报错、绝不误删）→ 大段删除可以放心做；
  但**锚点越长越容易转写错**（本次 40 行长锚点失败一次）→ **优先短锚点、逐条删除**。
- **只改大小写的改名在 Windows 上会被 git 静默忽略** → 必须"两次 `git mv`"（先改成临时名，再改成目标名），并用**字节数**核对零丢失。
- **命名与编号纪律**：记忆文件全小写 `.md`；标题不要塞冗长的中文数字序号；**"自 xxx 迁入"这类来源说明写在文件头部**，
  不要挂在小节标题上 —— 否则它后面那些并非迁入的内容会被一并错误归类（用户实测指出）。

## 任务中心与统计（2026-10-12 实测，含 3 次返工）

- **桥方法必须加在"真正被暴露为 `javaObject` 的那个类"上** ✗→✓：我把 `setTaskBadge` 加在 `MainWindow`，
  而前端调的是 `JFC.bridge.*` → 落到 **`JsBridge`** → 那里**没有这个方法** ✗；而 `bridge.js` 的
  `typeof window.javaObject[method] === 'function'` 检测不到时**只打 console、不报错** ✗ → **静默失效、极难发现**
  → **规矩**：新增桥方法 = `JsBridge` 里加方法 + `bridge.js` 加同名包装 **两处都做**，并核对方法名。
- **JavaFX：`managed=false` 的子节点在 StackPane 里 `width/height` 恒为 0** ✗：容器**不给不受管理的子节点做布局** →
  哪怕设了 `setPrefSize(18,18)` 也**什么都画不出来** ✗（角标"三次不显示"的第 2 个真因）
  → 需要显示的子节点一律 `managed(true)`；要精确摆位用**对齐 + 边距**，或 `translate`（纯渲染位移，不进布局）。
- **标题栏在最顶部时，负的"上边距"会把元素顶出窗口边界被截断** ✗：角标原本 `Insets(-6,-6,0,0)` → 顶部被切掉一小块。
  → 贴顶元素的**上边距 ≥ 0**（左右可以负值溢出）。
- **UIA 的 `ElementFromHandle` 是跨进程 COM 调用，会长时间甚至无限期阻塞** ✗（用户怀疑 → 实测确认）：
  目标进程 UI 线程忙/刚启动未就绪时，**调用方线程被卡住**；它原先跑在**流程线程**上 ✗ → 一次阻塞把整个任务
  （**连取消响应一起**）拖死 ✗，症状正是"平台没有历史窗口、首次开窗就卡住"。
  → **修法**：COM 调用放**独立线程池** + `Future.get(800ms)` 超时 + **连续 3 次超时熔断 60 秒**（这段时间只用 Win32 匹配）。
  → **通用教训**：**任何跨进程/原生调用都不许裸跑在流程线程上**，一律"线程池 + 超时 + 熔断"。
- **子步骤不要设置任务阶段** ✗：`killAllMutexesNow`（上层流程的子步骤）里调了 `TaskContext.phase("查杀互斥体")` →
  把上层正在显示的 "账号 3/10：开窗" **覆盖**掉 → 界面**一直卡在"查杀互斥体"**不动 ✗。
  → **阶段由上层流程独占**；子步骤只做检查点。
- **"一直没动静"的阶段要能秒级动**：等窗口/等关闭期间没有任何 `phase()` 调用 → 界面看着像死了 ✗。
  → `phaseSuffix()`（只改显示、不动统计键、不重置计时）+ 前端**每秒拉取** + **指纹比对**决定是否重画
  （重画会打断点击 ✗，所以只在"状态/阶段/进度"真的变了才重画）。
- **取消会跳过循环之后的代码** → 统计不能在循环后一次性上报 ✗：中途取消时异常直接弹回任务边界，后面的代码**不执行** ✗
  → 用**覆盖式** `metricSet`（每轮开头记轮次、每次成功记时长）→ 取消也能留下正确值 ✓。
- **统计口径不能"摆算式"**（用户批评："算都懒得算了是吧"）✗：展示 `Σ时长` 与 `Σ数量` 让用户自己除 → 毫无价值；
  → 必须给**算好的数**（总平均 / 末次 / 最短 / 最长），并以**用户确认过的定义**为准（本次返工两次）。
- **一次改动里叠了两个 bug 会互相掩护** ✗：角标第 1 次是"桥方法加错类"、第 2 次是"`managed=false` 没尺寸"，
  两次都被误判为"样式问题" → 排查时**要按数据流逐段验证**（前端有没有调 → 调用到了吗 → 值对吗 → 布局给了尺寸吗）。

---

## Electron / UIA / 托盘（2026-10-14~15 踩过的坑）

- **Electron 窗口"出来了但卡住"＝被外部强制操作搞的** ✗
  症状：侧栏点 QQNT → 窗口出现，但界面冻住不刷新。
  根因：我在"托盘消息之后"又做了外部操作 —— ①`beforePlace` 里**第二次发托盘消息**（托盘是**切换**语义 → 一发唤出、再发又切回去/切进坏状态）②`afterWake` 的 `raiseToTop`+`SetForegroundWindow` ③**`placeForSwitch` 对它的 `SetWindowPos` 摆位**（这条最致命：每次切窗都搬运几何）。
  修法：Electron 平台**只发那一条托盘消息，然后什么都不做** ✗；用 `PlatformAdapter.allowExternalPlacement()=false` 让侧栏跳过摆位。
  预防：**"复用它自己的通道"时，别在它后面加任何"帮助"** —— 帮助就是破坏。依据 [CSDN：自建任务栏 qq关闭后再打开窗口，窗口卡死解决办法](https://misuseds.blog.csdn.net/article/details/166489064)。
- **托盘图标是「切换」语义** ✗ —— 同一图标连点两次 = 开了又关/切进坏状态；**窗口已可见时绝不能再点托盘**。凡是"唤醒动作"，先判可见性再决定发不发。
- **微信自绘标题栏：UIA 既无几何、`Invoke` 也是空操作** ✗
  `BoundingRectangle` 与 `ClickablePoint` 扫 20~34 号下标**全空**（探针实证）；`InvokePattern.Invoke()` 返回成功但窗口状态不变（`false→false`）。
  → 该场景只能用"**真实点击**"（用户三方案实测：标题栏**双击×2** 最自然无副作用；最大化×2 会**污染还原尺寸**、最小化有飞出飞回动效，二者退役）。
  **反例对照**：Win11 任务栏是**原生 XAML** → 托盘图标**有几何且支持 Invoke** ✓ → 托盘唤出成立。**判断依据＝"是不是原生/标准控件"**，不是"是不是同一家公司"。
- **同一应用多开时，托盘图标名字可能完全一样** ✗（微信多开全是 `name=微信`，实测；老 QQ 则带账号号 `QQ: 617689998`）→ 托盘唤出**无法指定账号**；该场景改用"作用在指定 hwnd 上"的方案（双击×2 天然按账号精确）。
- **列控件别设数量上限** ✗ —— 我用了 60 条上限，结果**最大化/最小化/关闭按钮全被截断**（实际在 #159/#162/#165），白绕一大圈。要过滤就**按类名/名字过滤**，别按条数截断。
- **UIA 属性下标不能"按顺序推"就当事实用** ✗ —— `24=AutomationId`、`30=ClassName` 是项目实测过的，可用；而 `25`(矩形)/`26`(可点)/`28`(ControlType) 我按序推的读出来是 0/垃圾 → **要用就现场校准**（`probeRectIndices` 扫一段下标，只按 RECT 形状安全读，绝不把未知指针当字符串解 ✗）。
- **探针必须自己跑，且快照要逐轮更新** ✗ —— 我让用户一轮轮点，被明确纠正（"你自己用探针吧"）；另外我的 uid 探针用**初始快照**比较，导致 uid=4..12 全部**假报"唤出同一个窗口"** → 每轮都要重新快照。
- **改文件只用编辑工具** ✗ —— 我曾用 pwsh 脚本批量替换，把 `return` 的字符串拼接**一起改坏**（`hit`/`before`/`after` 全没参与、判定串写死），用户拿到**无效日志**白测一轮。**shell 只用来读结果/跑命令**。
- **Java 字符串里不能再嵌双引号** ✗ —— 同一个坑犯了 5 次以上（编译报"需要 ')'"/非法字符）。写文案一律用 `「」`。
- **`findMainWindowOfPid` 的两个反面** ✗：①只认**可见**窗口 → 应用收进托盘后就找不到主窗；②改成"隐藏兜底"后又被**托盘宿主窗口**骗走（它自报的矩形竟比真主窗更大）→ 必须**排除辅助窗口类名**（`*MessageWindow*`/`IME`/`SoPy*`/`Sogou*`/`MSCTF*`）。
- **托盘图标矩形查不到 ≠ 代码错** ✗ —— `Shell_NotifyIconGetRect` 要求 `NOTIFYICONIDENTIFIER` 给 `uID` **或** `guidItem`；GUID 注册的图标用 hwnd+uID **注定查不到**（微信就是这种，且窗口收进托盘后再测仍查不到）。此时应立刻转 UIA 路线，别在旧 API 上硬耗。
- **D-46（登录按钮点击主次）的新可用件** ✓：`UiaOps.invokeButtonExact` / `buttonScreenRect` 已就绪 → **登录按钮可先试 UIA `Invoke`，失败再退回比例坐标**；但注意"`Invoke` 可能是空操作"（微信实证）→ 兜底不能省。

- **素材卡的时间必须"实取"，绝不许估算；而且格式必须齐全** ✗（2026-10-16 用户立规 ✓）
  症状：我凭印象把卡片写成 `## 02:30（10-15）`，实际当天是 **10-16** ✗；而且从 14 号起把卡片**拼进了 13 号的文件** ✗（规范是一天一文件 ✓）。
  根因：把"记忆卡片"当成随手笔记 ✗ —— 时间靠估、文件靠顺延；甚至写下"拿不到时间就不写日期"这种**错的**话 ✗。
  **正确规矩（用户定）**：一天一文件 ✓；标题 `## HH:MM:SS — 主题` ✓；写卡前 `Get-Date -Format 'yyyy-MM-dd HH:mm:ss'` ✓；
  **本机取不到就联网取**（HTTP 响应 `Date` 头 / 授时接口 ✓）—— **不允许估算、不允许省略、不允许"凑合写"** ✗（记素材的前提就是格式齐全 ✓）。
  日期记错的补救＝**直接重命名文件** ✓ + 改内部文件标题 ✓。
  预防：**"能用命令行拿到的事实，一律不要靠脑子"** ✓（时间、行数、是否存在、进程 pid/句柄…）。

## 侧栏 / JavaFX / Win32（2026-10-17~19，都是"看起来是 A、其实是 B"的坑）

- **"布局不生效"往往是因为容器**没有**撑满** ✓：`ScrollPane` 只开 `fitToWidth` → 竖排 VBox 高度＝内容高 ✗
  → 容器对齐没有作用空间 ✗ → 12 个位置"看起来都挤在一头" ✓ 只��� **fitToWidth + fitToHeight 都开** ✓
- **同一个量出现第二处算法＝必然不一致** ✓（本轮"长度"在代码里有 3 处：跟随态 / 贴边条 / 折叠热带 ✗）
  症状：改一处、漏两处（"自适应时条没铺满但感应区铺满了" ✗）→ **立刻收敛成一个变量** ✓
- **状态判定要看"数据"，不要看"我处在哪个 UI 模式"** ✓：示例按钮该看"有没有真实平台账号" ✓
  绑在 `demoMode` 上 ✗ → 才会"设置页有、别处没有、再点又没了" ✓
- **任何"开"都要有对应的"关"** ✓：预览态只在"点导航"时关 ✗ → 整页退出不触发 ✗ → 侧栏再也关不掉 ✓
- **`setMouseTransparent(true)` 会把 Tooltip 一起屏蔽** ✗（鼠标事件进不来 ✓）→ 要提示就别透明 ✓
- **样式表"只放颜色"的覆盖表必须与规则表同时加载** ✓ —— 浅色时只加载覆盖表 ✗ → 浅色下**一条规则都没有** ✓
  （圆角/间距/按钮尺寸全丢 → "圆角不一样、位置也不一样" ✓）且**别在覆盖表里写规则** ✗
- **`SetWindowLong(GWL_EXSTYLE, …)` 会清掉 `WS_EX_TOPMOST`** ✗ → 之后必须 `SetWindowPos(HWND_TOPMOST)` ✓
- **无 owner 的顶层窗口一定进 Alt+Tab** ✗ → 附属窗口要 `initOwner(主窗口)` ✓
- **被拥有的窗口一被激活，owner 会被一起提到前台** ✗ → 侧栏**永不 `toFront()`** ✓
  （否则"切平台窗 → 闪一下 → 又回主窗口" ✓ 用户实测 ✓）
- **"不一致"先找画面里不对称的东西** ✓（用户说的是"两行分段按钮宽度不等" ✓ 我却去改文字颜色 ✗）
- **别在 bug 上一直补** ✓（用户原话）：先写"**谁决定什么**"（数据驱动 ✓ 模式只做显示策略 ✓），再写代码 ✓

## 矩形口径 / 症状形状（2026-10-18 实证）

- **同一概念两种口径必须核对**：`getVisualRect`（DWM 可视区）与 `GetWindowRect`/`SetWindowPos`（窗口矩形，含 Win11 约 7px 隐形边框）
  混用 → 表现是"切过去后侧栏恒定往里偏一点"。修法：目标按**可视**取，落位前用 `WindowActivationOps.frameDelta(hwnd)` 换算成窗口矩形。
- **症状的形状就是线索**：**恒定小偏移 ≈ 隐形边框**（7~8px 量级、每边一致）；**逐次累积 ≈ 反推/漂移**（如"从侧栏反算窗口位置"）。
  先看"偏移是恒定还是累积"，比逐行读代码快。
- **"设置写进去了" ≠ "渲染真的用到它"**：本轮三次同一类错 ——
  ①容器对齐要靠**容器撑满**才有空间（`setFitToWidth` + `setFitToHeight` 都要开）
  ②样式表要**先有规则再有颜色**（浅色只加载覆盖表 → 一条规则都没有）
  ③同一段有"竖排/横排"两分支时必须两路都按同一语义写（横排漏设 → 上下两边都居中）。
  → 改完一条设置，追一遍它到底经由哪条**渲染/命中**路径生效。
- **flex/布局属性会影响命中测试**：把 `setFitTo*` 打开后，收起态的 ScrollPane 会占满整个热带 → 热带"看不见也摸不到"；
  收起时必须关 fit 并 `setMouseTransparent(true)`。
- **`setMouseTransparent(true)` 会连带屏蔽 Tooltip**（鼠标事件进不来）→ 要提示就别透明。

## 记忆整理纪律（2026-10-19 用户定）

- **整理要按"一天一个 tmp 文件"逐日进行**：上下文不够时**一次只整理一天**，分多次完成，**不许遗漏**任何卡片。
- **每张卡的"候选去向"就是清单**：整理时逐条核对去向（facts / decisions / lessons / dev_logs / AGENTS），
  做到"卡片里说要去哪，就真的进了哪"（本轮 `frameDelta`/可见层就漏过一次，用户当场发现）。
- 整理完在 `index.md` 台账写清"来源是哪几天、归置到哪些文件"，方便下次核账。


## 补丁系统 / 表格（2026-10-21~23，症状都不像它真正的原因）

1. **扫描恒失败**：`searchPatternDicts` 用 `aligned.size() != 2` 判断对齐结果，但 `convertAndAlign` 返回的是 **token 列表**
   （长度 = 特征码字节数）→ 永远判失败、缓存永远是空的。**移植时要先对齐"函数返回值的语义"，不是只看签名。**
2. **缓存少一层平台节点**：旧版 `SwCache.json` 是 `{平台: {模式: …}}`，我写成了 `{模式: …}` → **跨平台串数据**，
   症状是"一进就缓存命中 5 个"。缓存结构**照抄旧版真实文件**，不要凭记忆。
3. **失败结果不要缓存**：曾经记住扫描失败的渠道，结果挡住"配置改进 / 撤销补丁 / 重装"后的恢复 —— 属于过度优化。
4. **重新扫描跑两轮**：先 `force` 跑一轮、再普通跑一轮 = 两轮全量扫描（5.6s → 3.8s 的差距）。
5. **共存路径白扫多开**：`getSwPatchPlan` 会顺带扫 multirun；共存表刷新/共存单行只需要 anti-revoke。
   扫描入口要按"这次到底为谁服务"拆开。
6. **只读缓存也调 `build`**：会打印"缓存命中 5"，让人误以为又扫了一遍。只读路径就不要进构建流程。
7. **跨任务的静态标记一定会越界**：`SCANNED`（平台+模式+版本）看似省扫描，实际挡掉"再试一次"的语义 →
   改成参数 `allowScan`，生命周期跟着调用走。
8. **内存带宽瓶颈**：192MB 全文件扫描加线程不加速（模式并行 + 池 6 反而 4.7s → 5.1s）。
   **并发度要实测，不要凭"多线程更快"的直觉。**
9. **整平台串行锁**让共存表头白等 4.8s（它自己的活只要 0.1s）。锁的粒度要贴着**被保护的数据**，不是贴着平台。
   并发安全改成"扫描并行 + 只锁 JSON 合并"。
10. **表头只在建表时生成一次** → 模式切换后登录态专列（pid/hwnd）与内容错位。列头必须随模式/可见性重建；
    列头与行必须来自同一个 `_renderCols()`。
11. **列宽自适应按文字测宽**：补丁列是按钮组，按 `innerText` 测宽必少算 → 永远两行。
    要量真实布局（`nowrap` + `scrollWidth`），并加"仍折行就继续加宽"的兜底。
12. **委托到 `tbody` 的点击必须用捕获阶段**才能先于行点击，否则点按钮会连带选中整行。
13. **事件委托传参要一次传全**：`data-patch-action` 分支只传了 `{action}`、漏了 `accId` → 单行扫描按钮静默失效。
14. **hover 驱动的 UI 不要在交互中重绘 DOM**：选择方案后重绘表头会丢 `:hover` → 按钮立刻缩回。
15. **调试用的假数据会写进配置**：临时插的"方案2"被当成当前渠道存进了 `coexist_mode` → 整行未知。
    假数据要能一键清理，写配置前要校验值真实存在。
16. **比较器方向搞反**：`compareVersionDesc(a,b) < 0` 表示 a > b；用它当"v ≤ target"就会选到**最旧**的适配版本，
    症状是"以前能扫到，现在扫不到"。
17. **布尔参数经 JS 桥要按字符串传**（`"true"/"false"`），避免 JSObject 转换的坑。
18. **mmap 同进程立刻重读要先 `unmap`**；撤销补丁写回 `original`；`finally` 里不要 force 落半截补丁。
19. **`...` 只有开头才是"前补"，尾部是"省略"**；分词器不要顺手把 `!!` 里的 `!` 剥掉（占位符要能原样回到结果里）。
20. **组装结果时不要把源字段覆盖回原值**：缓存条目组装时又写了一遍 feature 的原始 `addr`，
    把解析后的地址覆盖掉了（目录条目带尾斜杠、与 `dst` 不一致）。**派生值算完就不要再被原始值覆盖。**
21. **识别结果是三态**：`DetectionResult.status` 是 `Boolean`，`null` = 未知（文件不存在/没适配），
    不能当 `false` 用 —— 界面上"未知"必须显示虚框且不可点，与"未开启"是两回事。
22. **性能：逐字节 `parseInt`/`String` 比较是杀手**：特征码匹配先**预编译成基本类型数组** + 多字节锚点，
    15.9s → 9.07s；此外同一个工具函数有两份实现时，**另一份也常常在热路径上**，别忘了。
23. **任务上下文是 `ThreadLocal`**：丢进线程池的 worker 里要**手动传 `TaskContext`**，否则 checkpoint/统计全丢。
24. **清空显示但没人回填 = 永远"扫描中…"**：把某表的计划置空却不再触发加载，那一列就永远转圈。
    谁清空，谁负责安排回填（或把"未加载"与"进行中"用不同状态区分）。

## 未解决的已知问题

1. **打包版 SSL 握手失败**（`handshake_failure`）：打包产物访问远端配置源失败，开发运行正常。
   线索：疑似 jlink 裁掉了某个安全 provider / cacerts 路径 → 排查入口 `AppCore.applyProxySetting()`、`RemoteConfigFetcher`。
2. ~~登录完成后的 pid/hwnd 未写入 `AccRuntimeStore`~~ → **2026-10-12 用户裁定：不算问题、不做**。
   理由：**hwnd 会从登录窗变主窗**，且流程**并不知道登录的是哪个号**（共存尤其如此；原生也可以先用 A 的配置唤起登录窗、再切 B 登录）
   → 那是**页面刷新**该干的事，不是登录流程该干的。详见 `decisions.md` **D-32** 附注。
3. **补丁状态探测未接**（builtin / freely 判定）：现状是保守判定，不影响正确性 → 见 `decisions.md` D-40。
4. **抗锯齿试验开关保留与否**：`run`/打包带 `-Dprism.lcdtext=false`（灰度 AA）→ 见 `decisions.md` D-27，待用户定夺。
5. **点击策略待改主次**：现为**比例坐标**点击登录按钮；用户 2026-10-12 定"**UIA 控件名优先、比例兜底**"，尚未实现 → 见 `decisions.md` **D-46**。
