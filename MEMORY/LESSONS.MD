# LESSONS.MD — 技术教训与经验结晶

> **本文件写"踩过的坑 + 结论"，供回查与避免重犯。**
> 变更过程 → `DEV_LOGS.MD` ｜ 当前状态 → 项目根 `AGENTS.md` ｜ 架构细节 → `docs/project_structure.md`
> 最后更新: 2026-10-05

---

## 〇、通用方法论

### 0.1 不猜，量出来 —— 离屏 WebView 实测

JavaFX WebView 与 Chromium 的布局细节不同，"看起来是 X"往往不是 X。**要确认 WebView 里的真实几何/样式，就用项目同款 JavaFX WebView 离屏渲染**：

1. 生成只含目标 DOM + 项目真实 CSS 的临时 HTML（CSS 内联 `<style>`，避免 file:// 相对路径问题）
2. 写个小 `Application`：`WebView` 放进 `Scene`，`stage.setX(-4000); setY(-4000); show()`（屏幕外，用户看不到），`eng.executeScript("...getBoundingClientRect()/getComputedStyle...")` 把结果 `System.out.println`
3. 关键坑：`javac` 必须 `-encoding UTF-8`（中文注释按 GBK 会报错）；`--module-path` 要带 `javafx-base/graphics/controls/media/web` 的 **win** jar（`javafx.web` 依赖 `javafx.media`）
4. 采样法最有效：`setInterval` 每 25ms 记录一次几何，把"轨迹"打出来，动画类问题一看就清楚
5. 校验完删除临时文件（放 `build/`，已被 gitignore）

> 今天靠它钉死了三桩"玄学"：名称列横线、切换闪一下、刚进平台从 0 涨上来。

### 0.2 单一事实来源 + 单一写入点

只要有"影子状态"（`_prevHeight` / `_prevWasCollapsed` / `_panelShownOnce` / `forcedLocalState`…），就一定会互相拉扯。**渲染的唯一依据 = 期望状态函数；状态变更一律"先落到事实来源（记录/本地态），再统一渲染"**；DOM 只允许一处写。

### 0.3 单一职责要贯彻到"判定权"

- 图标提取只判"软件路径存的值是不是程序"——"目录里该是哪个 exe"是**路径探测流程**的职责
- "平台是否启用"只**读**路径检查流程写下的绿框结果，不自己判断"填没填全"
- 一旦越界，就会出现"看起来能用、但两套规则长期打架"的隐性 bug

---

## 一、远程配置与加解密

- **源文件 → 加密产物**：`scripts/original_remote_global_<vN>.json` / `original_remote_sw_<vN>.json` → `gradle encryptRemoteConfigs` → `remote_configs/remote_<global|sw>_<vN>`；改版本号要同步 `RemoteConfigFetcher.BUILTIN_REMOTE_*_VERSION`，再提交推送（客户端按仓库 raw URL 下载）
- **加解密同源**：`config.CryptoUtils.encryptAndAppendKey`（工具在 `src/tools` 源集，不进应用产物），单测 `CryptoUtilsTest` 是安全网
- **候选 URL 永远要有兜底**：`JsBridge.downloadRemoteConfigs()` 的候选 = 用户配置 + 内置兜底（`mergeUrls()`）。曾只取用户列表 → 用户清空后日志 `候选URL: 0个`、远程配置永远下载失败
- **gitee 对 `remote_configs/remote_*` 返回 451**（平台判定违规，与网络无关）→ 候选列表里失败要能自动继续下一个源
- **代理只由界面复选框控制**：不做自动探测、不默认开启。历史现象 `SSLHandshakeException: Remote host terminated the handshake` 的根因是 **Java 默认不用 Windows 系统代理**（`java.net.useSystemProxies` 默认 false）
- **代理地址必须归一化**：`AppCore.splitHostPort` / `isValidPort` 允许 `http://127.0.0.1:7890`、`127.0.0.1:7890`、`127.0.0.1` + 端口分开填、`[::1]:7890`。**不能把含 `:` 的地址原样塞 `https.proxyHost`** —— JDK 会当 IPv6 加方括号，报 `URISyntaxException: Expected closing bracket for IPv6 address … proxy.https://[http://127.0.0.1]:7890/`
- **改代理立即生效**：`http(s).proxyHost/Port` 是 JVM 属性，`HttpClient` 的默认 `ProxySelector` 每次请求都读 → 无需重启；`applyProxyConfig` 回传 `requiresRestart` 只在运行期应用失败时提示

---

## 二、设置页布局与"分块保存"

- **一个保存按钮管所有校验 → 用户被无关校验挡住**（只想改本地目录却被"远程配置源测试失败"卡住）→ 拆成 代理 / 本地目录 / 远程配置源 三块，**每块只提交自己的字段**
- **后端天然支持部分提交**：`JsBridge.saveConfigData` 是 `if (data.has("x"))` 逐字段合并，缺省字段保持原值 —— 前端分块提交不需要任何后端改动
- **按钮可用性来自"本次会话的真实校验结果"**：不要用历史有效标记预置绿框；`updateBlockButtons()` 按块判定（目录块看 `input-ok`；远程源块要求 sw/global 各自测通）
- **视觉一致性靠变量**：板块介绍统一 `.config-desc`、标签统一 `--font-h3`、输入框统一 `padding/font/border-radius`、次级按钮统一尺寸、提示文字统一 `--font-xs`；间距归 `.config-divider` 管，`settings-section` 的 margin 归零
- **路径字符串要全链路规范化**：前端 `replace(/\\/g,'/')` + 后端 `Path.toString().replace('\\','/')`，`getActualDirVal`/`saveConfigData` 返回值一并规范化（否则弹窗/提示里会出现 `\` 混排）

---

## 三、最左栏（`#nav-sidebar`）

- **交互目标**：鼠标"静止"才展开 → `EXPAND_DELAY`(1000ms) + `MOVE_THRESHOLD`(6px)：微动不重置计时，明显移动重新计时，移出立即收起
- **`mouseleave` 会被吞**：点平台后账号列表加载卡顿，期间的 mouseleave 丢失 → 侧栏一直保持展开（只有再次进出才收回）。**两层兜底**：① 文档级 `mousemove`（capture）：指针在侧栏外移动且已展开 → `collapse()`；② 展开期间每 400ms 用 `document.elementFromPoint(lastX,lastY)` 校验是否还在侧栏内
- **别把只读的入口留在最左栏**：入口越少越稳（"统计"按钮已移除，页面与图标资源保留备用）

---

## 四、设置区高度动画（窗帘）

- **面板与内容区必须同值**：`applyPanelHeight(h)` 同时设 `panel.maxHeight = h` 与 `content.maxHeight = h`。任何 `- N` 的"预留"都会让"动画路径"与"静态路径"两套语义不一致 → 表现为"闪一下 / 冲过头再弹回"（曾写死 `-20`，实测该项的固定差值其实是 0）
- **动画期间内容区要解除上限**（`content.maxHeight='none'`），否则高度涨不上去；动画结束（**`transitionend` 在 JavaFX WebView 不可靠，用 400ms setTimeout 兜底**）再恢复上限，否则内容永不溢出、滚动条不再出现
- **`transition:none` 快照与恢复 transition 必须在不同帧**：单 `requestAnimationFrame` 分离"快照帧"与"过渡帧"（`offsetHeight` 强制重排后改值）
- **收起时 `scrollHeight === 0`**：读真实高度必须先 `remove('collapsed')` 再读，然后快照回 0、再过渡
- **首帧没有"上一个高度"**：面板还没按平台显示过时不做动画（否则会看到 `16 -> 180 -> 200` 这种假动画）
- **只有"记录本身是收起"才值得播 0→H 的展开动画**（全局收起 → 切到强制展开的平台）；"仅本地收起"的残影不应触发动画
- **`_prevHeight` 取语义高度**（`parseInt(panel.style.maxHeight)`）而不是渲染高度（渲染高度含 padding/border，作为起点会多算一截）

---

## 五、设置区展开/收回与分割线拖动

- **唯一渲染依据**：`desiredCurtainState(swId)` = ① 全局记录（`settings_height`/`settings_expanded`）② 例外：未启用平台**每次渲染都强制展开**；`applyCurtainRender()` 是唯一 DOM 写入点；`setCurtainExpanded` / `setCurtainHeight` 都是"先写记录再渲染"，`_lastRender` 记录上一帧真实状态
- **未启用平台**：不写记录、也不留本地状态 —— 用户本次访问里可以临时收起（`applyCurtainRender(override)` 只影响这一次渲染），下次渲染依旧强制展开
- **完备性判定要在渲染前就确定**：进入平台时**同步**跑一遍三个路径的 `checkPath`（同步桥调用），否则会出现"先按记录渲染、200ms 后检查回来又强制展开"的闪烁；只有"启用 ↔ 未启用"真正变化时才重渲染（`swEnabledKnown`）
- **收起状态禁止拖动底部分割线**（高度为 0 时拖动会瞬间跳到最小高度、与鼠标脱节），并把拖动区光标切成 `default`
- **光标别用内联 style 逐点设置**：状态改动的代码路径太多会漏 → 用 **CSS 驱动**（`body.curtain-collapsed`）+ **MutationObserver 监听面板 `collapsed` 类**同步 body 类
- **把手是全宽 SVG**：`width:100%` + `preserveAspectRatio="none"` → **viewBox 宽度必须随元素宽度同步**（窗口 resize 也要调 `initHandleSvg()`），否则把手被非等比拉伸/压缩（"点一次把手才恢复"就是这个）
- **拖动交互**：拖动中 `transition:none` + 夹取 `min=100 / max=content.scrollHeight+40`；松手恢复 transition 并 `initHandleSvg()`；**只在松手时落库**（避免高频写盘）
- **内容区 `max-height` 是隐形锁**：`max-height:180px` 的 CSS 默认值会限制面板实际高度，自由高度动画前必须解除

---

## 六、账号区数据来源（定义清晰才好维护）

- **来源 = 磁盘扫描**：`JsBridge.getSwExistedAccounts(swId, 'origin'|'coexist')` → `SwInfoFuncCore.getSwAllAccountsExisted`（数据目录子目录 − 排除目录；共存 = 安装目录匹配 `executable_wildcards` 的 exe）
- **详情 = SwAccData**：`getSwDetailData(swId)` 注入 `display_name`（`AccInfoFuncCore.getAccOriginDisplayName`）
- **无效账号 = SwAccData − 原生 − 共存**：按自身类型并入原生/共存表（`invalid:true` → 灰字 + "失效"标签 + **永远置底**）
- **共存账号判定**：SwAccData 节点带 `linked_acc` → 共存；兜底看 id 是否 `.exe`
- **三个曾让共存表恒空的后端缺陷**：① 读错配置键（`exe_wcs` vs 常量 `EXECUTABLE_WILDCARDS`）② `accountOps` 传 null → `ensureCoexistAccFormatted` NPE ③ `inst_path` 可能是**目录**（WeChat/DouYinIM）却一律 `getParent()` → 抽 `resolveInstDir()`
- **平台数据维护按事件流**：进入平台 → `PlatformEnteredEvent` → 后台 `resolvePidAccountMap → associateCoexistAccounts → updateAccLoginData`；字段更新 → `AccountDataChangedEvent` → 前端**定向更新单元格**（不整表重渲染）

---

## 七、头像与名称的来源链

- **名称**：`remark（本地） > nickname > alias > 账号 ID`（`AccInfoFuncCore.getAccOriginDisplayName`）；**共存账号一律参考 `linked_acc`**（自身只认 remark）：`remark > 链接账号 nickname > 链接账号 alias > 链接账号 id > 自身 id`
- **头像**：本地文件 `{userDir}/{sw}/{acc}/{acc}.jpg` → URL 下载（以 `/0` 结尾）→ SVG 文字回退；共存头像链：自身本地文件 > 链接账号本地文件 > 链接账号头像 URL > 默认
- **异步接入**：`JsBridge.getAccAvatarAsync` 后台线程 + `Platform.runLater` 推送；SVG 回退**不降级替换**已有真实图片
- **名称就是名称**：曾因"下划线"误判去清洗过账号 ID 里的 `_`，实际用户要的是"去掉分割线"——**别替用户改数据**，显示层清洗要慎之又慎（现已撤销）

---

## 八、平台图标（程序图标）

- **尺寸**：`FileSystemView.getSystemIcon(File, w, h)` 在 Windows 支持任意尺寸（实测 48/64/128/256），公开 API、**不需要 `--add-exports`**；默认无参重载只给 16×16（这就是"模糊"的根源）
- **只认程序**：`isFile() && .exe` 才提取；`inst_path` 是目录就什么都不做（拼 `executable` 属于路径探测流程的职责）
- **缓存**：`{用户数据目录}/{swId}/{swId}.png`（如 `Weixin/Weixin.png`）；有图且 `inst_path` 未变 → 直接用；缺图或路径变了（比对 `icon_src_path`）→ 重新提取覆盖；**提取失败什么都不做**，保留原图
- **旧路径的坑**：`sun.awt.shell.ShellFolder.getIcon(true)` 需要 `--add-exports java.desktop/sun.awt.shell=ALL-UNNAMED`，且返回**惰性图片**（`getWidth(null)` 得 -1）→ 必须 `new ImageIcon(img)` 包一层才能拿到真实尺寸

---

## 九、占位列与列宽（`table-layout: fixed`）

- **列宽取自 `<col>`**：隐藏列只给 th/td 加 `display:none` 是不够的 —— 声明的列宽总和 > 表格宽度时浏览器会**重新分配**，于是"最右列怎么拖都改不动"。修复：隐藏列的 `<col>` 同时 `width:0px` + 隐藏类
- **表格宽度 = 可见列宽总和 + 占位列**：`table.style.width` 绝不用容器宽填充（fixed 布局会按比例拉伸真实列）
- **占位列（`_filler`）不是列**：不进 `columns`、不参与排序/显隐/列菜单；宽度 = 容器可视宽 − 可见列宽总和（≥0）。它的价值：① 所有真实列右侧都有邻居 → 拖拽热区不再压在表格边界 ② 占位单元格属于该行 → **整行悬浮/选中感应区天然覆盖容器宽**
- **取整**：拖拽宽度与总和都 `Math.round`，避免小数宽度让"总和+占位列"超出容器 1px 冒出横向滚动条
- **列配置持久化**：写嵌套 `account_columns.<表id>`；`saveGlobalConfig` 是**顶层浅合并** → 先读出 `account_columns` 再合并本表，否则清掉其它表配置；列定义变化（删列/加列）要能识别"陈旧列名"并整份作废回默认

---

## 十、行高

- 行高不齐的根因常常是**某一列多/少了一个元素**：账号表与程序表统一为 32px 头像列 + `tbody tr[data-acc-id] { height: 44px }` 兜底最小高度
- **`td` 千万不能设 `display:flex`**：它就不再是 table-cell，浏览器插入**匿名 table-cell** 包住它，td 自己的 padding/border 画在内层 → 该列底边与同行错位（表现为"名称下面多一条横线"）。要 flex 就在内层加一个 `div`
- 内层 flex 容器**不要 `overflow:hidden`**（会把绝对定位/超高的按钮上下边框裁掉），并用 `min-height` 保证按钮放得下

---

## 十一、行悬浮与选中着色

- **`tr` 背景覆盖不到表格右侧空白** → 用绝对定位色块层（`.acc-row-highlight` / `.acc-row-sel`），`z-index:-1`，容器 `.acc-table-scroll { z-index:0; isolation:isolate }` 形成层叠上下文
- **色块必须用不透明等效色**（`--bg-row-hover` / `--bg-row-selected`）：半透明叠在容器上会二次变深、深浅主题下表现不一致
- **选中行不再显示悬浮色**（遇 `.selected` 直接隐藏悬浮层）；移除 `tr.selected` 背景与 `tr{transition:background}`，避免半透明叠加
- 悬浮按钮：**在文档流内**才会"挤占文字 → 名称以 `…` 结尾"（用户要的观感）；背景要不透明，否则看起来发虚

---

## 十二、交互反馈的归位

- **标题只是标题**：曾用 `flashTitle()` 临时把平台标题替换成提示（"已隐藏/已显示/已删除/尺寸已获取"）——**这是借标题当通知区**，已整套移除（两份实现 + 8 处调用）
- 状态变化优先靠**就地可见的变化**表达：按钮文案（显示/隐藏）、行内标签（失效/禁用/隐藏）、行置底、行消失
- 真要提示，放在**该功能所属区域内部**（如字段旁的小红字），不要跨区域"借用"别的控件

---

## 十三、工程习惯（省时间的小事）

- **改代码的批量脚本必须识别行尾**：项目 JS 是 **CRLF**，脚本按 `\n` 匹配会 0 命中（今天踩过：9 处替换全落空）
- **PowerShell 里写含引号/中文的替换脚本容易炸** → 用 Node 脚本文件（`write` 工具写，避免 shell 引号地狱）
- **`.bat` 保持 LF 行尾**（历史原因），改完要检查 CRLF 计数为 0
- **`javac` 记得 `-encoding UTF-8`**；`--module-path` 别漏 `javafx.media`
- **反射调 JDK 内部 API 记得三件套**：`--add-exports`（`build.gradle.kts` 的 `applicationDefaultJvmArgs` + `run` jvmArgs、`scripts/package-exe.bat` 的 `--java-options`）、异常兜底（失败只降级不崩）、惰性加载处理
- **内存文件只做"精确替换/追加"**，不要用截断式脚本改写（曾把 TODOS.MD 截断过一次）
- **文档分家**：变更过程 → `DEV_LOGS.MD`；教训 → 本文件；当前状态/约定 → 根 `AGENTS.md`；架构细节 → `docs/`。判断标准：**"这是现在是什么样，还是曾经发生了什么？"**

---

## 十四、JavaFX WebView 与前端交互的十七个坑（2026-10-05 起实测）
> 结论都来自离屏 WebView 实测（`build/_probe/`），不是查文档猜的。做前端交互前先按这几条对照一遍。

1. **`window.confirm()` 恒返回 `false`**（`alert()` 也什么都不做）——JavaFX 没装 confirm handler 时既不弹窗也不返回 true。
   曾经的"删除账号"确认全部走 `confirm()` → **点删除永远静默取消**，而且用户看不到任何提示。修法：自建 HTML 弹窗（`JFC.modal.confirm`），可主题化、可键盘操作、不打断 WebView 焦点。
2. **`keydown` 里 `event.key` 是空字符串**（`event.code` 也是空的），只有 `keyCode`/`which` 正确：a→65、1→49、空格→32、F5→116、Ctrl+A→65、Esc→27、Enter→13。
   → 所有 `event.key === 'Enter'/'Escape'/'ArrowX'` 判断在这台 WebView 里**全部失效**（快捷键录不进普通字符、标题框 Enter/Esc 不生效、退格删不掉字，根因都是它）。
   修法：统一走 `JFC.keys`（keyCode 为主、`key` 作浏览器兜底），键名与 Java 侧 `JsBridge.keyNameOf` 对齐。
3. **同一个单元格上反复挂 `stopPropagation` 的 click 监听会累积**：单元格若"只重建本格内容"就一直存活，第 N 次进入编辑后，这个格子自己的点击被自己挡住（tbody 的委托收不到）→ 表现为"点了没反应"。
   修法：不要在单元格上挂这类监听（委托里判断 `e.target.tagName === 'INPUT'` 就够了）。
4. **不要在 `mousedown` 阶段重建整表 DOM**：编辑提交若在 document 的 mousedown 阶段 `render()`，用户这一下点击所在的元素会被换掉 → 后续 click 落空（"点别处要按两次才生效"）。
   修法：同步只还原本格，**保存与整表重排延后一拍**（`setTimeout(…, 0)`）。
5. **`closest()` 只接受选择器字符串** —— 传元素会抛 `SyntaxError`，而监听器里的异常不会中断别的代码、只让**这一个处理器的第一行静默死掉**（叠加"编辑器里异常看不见"就极难发现）。
   实际踩坑：`if (ev.target.closest(cell)) return;`（想判断"点在编辑格内部"）→ 整个"点击框外结束编辑"的逻辑**从来没生效过**，表现为"点了框外编辑态还在"。
   修法：用 `cell.contains(ev.target)`。**排查这类"点了没反应"时，先把 WebView 的 console 打开看有没有未捕获异常**（本项目探针默认静默 console，教训：验证时别把 console 也一起静音）。
6. **原生表单控件会"先画一帧原生外观，再套你的样式"**：`input[type=checkbox]` 在 JavaFX WebView 里表现为**先出现纯方形、随后才变圆角/主题色**（用户实测到的"渲染异步"）。
   修法：别让原生控件承担视觉 —— 用 `<label>` + **透明 input（只当状态载体）** + 自绘 `<span>`（边框/圆角/勾），从第一帧就是最终样子。
7. **中文"模糊"的锅不在字体，在抗锯齿模式**：JavaFX（含 WebView 内文本）**默认就是 LCD 次像素抗锯齿**。
   实测（离屏截图像素统计，5 个字体分区 × 4 种 JVM 开关）：
   | 配置 | 边缘对比度 | 彩色边缘占比（LCD 特征） |
   |---|---|---|
   | 默认 | 51.3 | **97.0%** |
   | `-Dprism.lcdtext=true` | 51.3 | 97.0%（=默认值，无变化） |
   | `-Dprism.lcdtext=false` | **53.5** | **0.0%** |
   | `-Dprism.text=t2k` | 51.3 | 97.0% |
   **四个字体分区（宋体 / 等宽+雅黑 / 本机默认 / 雅黑基线）的边缘对比度完全相同（51.3/50.2）**，只有墨量（字重/字形）差异
   → 换字体解决不了"发虚"，深色底 + 中文复杂笔画在 LCD 下会有彩色条纹；要"干净"就 `-Dprism.lcdtext=false`（灰度 AA）。
8. **几何居中 ≠ 视觉居中**：旋转 45° 的"勾"（L 形）用 `translate(-50%,-50%)` 几何居中后，**墨迹中心仍偏下 1.25px**
   （测量值），要按实测补偿 `calc(-50% - 1.25px)`。凡是**不对称图形**（勾、箭头、折角）都必须用像素实测校正，不能只靠数学居中。
   **反过来也有教训**：我曾把"圆角处露出背景色"解释成几何必然、劝用户接受，其实当时的真问题是**填充形状比空框小**；
   用户指正后放大圆角也没问题。**报告现象前先做"两态轮廓比对"再下结论**（`CheckboxProbe` 现在就有这一步：两态形状像素差 15/999，全是抗锯齿）。
9. **别指望 `font-family` 列表能"按字符集分字体"**：等宽族缺中文时，WebKit 走的是**系统 CJK 回退**，
   列表里排在后面的中文字体根本轮不到（实测中文墨块 131 ≈ 回退字体；雅黑应为 175）。
   `@font-face + unicode-range` 在 JavaFX 这个 WebKit 版本里**也不生效**：把中文专用字体放列表最前，英文会被它一起吃掉。
   → 要"中文一种字体、英文另一种"，只能**显式分段**：由 JS 按字符集把文本拆成多个 `<span>`，各自指定 `font-family`。
   **鉴定"某元素到底用了哪个字体"的可靠办法**：离屏渲染同一个字，比**墨块数**（同字号同字重下 雅黑 175 / 宋体 146 / 等宽回退 131）；
   像素指纹逐像素比对对字重、字号、亚像素位置过于敏感，容易得出"全不相同"的假结论。
10. **JavaFX WebView 的 `contenteditable` 基本不可用**：为了"编辑态也中文雅黑 + 英文等宽"，我把名称编辑框从 `<input>` 换成
    `contenteditable` div（配 `scriptSplitHtml` 分段 + 按字符偏移恢复光标 + 组字期间不动 DOM + 纯文本粘贴）——
    **用户实测结果：连正常输入/修改都不行**（不只是光标跳），只能回退成 `<input>` + 统一一种字体。
    → 教训：**别为了"字体/样式上的小收益"替换掉成熟的原生控件**（`<input>` 的输入、输入法、选区、撤销都是浏览器实现好的）；
    另外这类交互**离屏探针验证不了**（`window.getSelection()` 在无窗口焦点的窗口里恒空，`requestFocus()` 也没用），必须真机试。
    想在编辑态做到"中文一种、英文另一种"，目前唯一可行的是 `contenteditable` —— 但代价已实测为不可接受。
11. **"同色边框 + 背景"是两层几何，圆角处会露缝**：勾选框要"填满"，正确做法是
    `background-clip: border-box` + **`border-color: transparent`**（由背景独占整块形状），
    而不是把 border 也设成同色 —— 后者是"内填充（padding box 内圆角）+ 外边框（外圆角）"两层，
    圆角处会看到缝/黑点。**验证办法**：数"形状内部既非填充色也非勾色"的像素（`CheckboxProbe` 的"内部镂空检查"），一整块填充应为 0。
    ⚠️ **2026-10-06 又在按钮上犯了一次**（`background: primary` + `border-color: primary`），用户："填充用整块填充，不要还搞边框+内部，每次都能看到中间有空隙"。
    → **凡是"要填满"的元素（勾选框、按钮、滑块、色块…），一律：border 要么不加、要么透明；绝不用同色 border 去凑形状。**
12. **给"选择器组"加样式前，先逐条确认组里每个选择器都该改**：我把"昵称列用雅黑"写进了
    `.manage-text-cell, .manage-alias-cell, .manage-nickname-data-cell` 共用组 →
    程序表的名称/版本/路径（同属 `.manage-text-cell`）也一起变雅黑，属于用户肉眼发现、我探针没覆盖的回归。
    **规则：一处样式只影响一类元素时，就单独写一条规则，不要图省事塞进共用选择器组。**
13. **"如果…就…"式最高优先级指令 = 条件兜底，不是直接指令**：用户写"**如果**你没办法调试好，就当前状态让填充框边长+1"，
    语义是"**先真正修好；修不好才用 +1 兜底**"。我跳过"先修"直接执行了兜底 → 被指出"说好的逐字呢"。
    **执行这类指令的正确顺序**：先按指令里的目标做真正的修复 → 只有在确实做不到时才启用兜底 → 并在回复里说明"兜底未启用/为何启用"。
14. **探针/测试的"数据"必须与真实的数据推导链一致，否则会得出假 FAIL 并误导排查方向**：
    ① 我给"隐藏行"造的数据只设置了 `hidden`，但 `main.js` 是**按"是否在 `getSwExistedAccounts` 列表里"推导失效**的
    → 那个账号同时被判成失效，实测颜色自然是 3 级，我却先怀疑 CSS；
    ② 另一个"普通行"账号在**前面的步骤里被点了隐藏按钮**，真的变成隐藏行。
    → 造数据前先读一遍"这个状态在真实代码里是怎么来的"；断言失败时先用 DIAG 打印真实 DOM（class + computed 值）再判断是代码错还是测试错。
15. **"禁用"的菜单项要保留它的动作标识**：右键菜单里把"删除"对正常账号改成禁用时，我写成了
    `<div class="acm-item danger disabled" title="…">删除</div>` —— **漏了 `data-row-action="delete"`**，
    结果：① 探针用 `[data-row-action]` 查不到它（看起来像"菜单项根本没渲染"）② 事件绑定循环也覆盖不到它。
    正确写法：禁用项**照样带动作标识**，只在点击处理里 `if (classList.contains('disabled')) return;`。
    **通用规则**：UI 的"禁用"属于**行为层**判断，不要让它改变元素的结构/标识（否则选择器、事件绑定、测试全会漏）。
16. **"按钮点了没反应"比"弹个窗说明原因"更糟**：批量删除最初对"全选正常账号"直接静默 return，
    用户明确指出"这样用户会疑惑为啥点不了"。正确做法：**流程照常走（照弹确认框）**，文案里说明哪些会被跳过，
    "不作为"只发生在**执行层**（真正删除时过滤掉不能删的）。

---

## 十五、快捷键录入的交互定稿（2026-10-05）

- **松手即确认**：所有键松开的那一刻提交并退出输入框（此前是"点别处才提交"，点别处若顺手选中行会触发重渲染 → 未提交的录入随 DOM 一起丢）
- **无效即回退**：只有修饰键（Alt+Shift）或普通键多于一个（Alt+A+B）→ 恢复原键值，**不保存也不清空**（`_renderHotkeyCell` 曾无条件把本地值写成空 → 视觉上"快捷键丢了"）
- **Backspace = 清空并退出**；Esc = 放弃；Enter = 忽略（不当热键，避免"回车确认"的习惯把热键改成 Enter）；Tab 算普通键（可录成 Tab）
- 预览用已按下的普通键 + 当时修饰键拼装，松键顺序不影响结果

---

## 十六、Java API 陷阱（本项目实际踩到的）

- **静态 `init` 被当实例方法调用 → 单例拿到"未初始化的实例"**：`ConfigManager.getInstance()` 原本写
  `ConfigManager mgr = new ConfigManager(); mgr.init(false); instance = mgr;`，而 `mgr.init(false)` 解析到的是**静态** `init` ——
  它自己 new 并初始化了**另一个**实例赋给 `instance`，紧接着又被这个**未初始化**的 `mgr` 覆盖。
  只要 `getInstance()` 是首个入口（应用正常启动不会，Launcher 先显式 `init` 过；**独立探针/工具会**），
  拿到的实例 `userDataPath == null` → `getUserDir()` 直接 NPE（2026-10-05 由 `AccFilesProbe` 首次暴露并修复）。
  **教训**：单例初始化只保留一条路径（`getInstance()` 内直接 `init(...)`）；**静态方法不要通过实例引用调用**（编译器不报错，语义却是全局的）。
  这类 bug 只在"非正常入口"暴露 → 独立探针本身就是一种非正常入口，价值就在这里。

- **`Map.of(k, null)` 一定抛 NPE**（`Map.of` 不接受 null 键/值），而它常常被写成"把这个字段清掉"的意图。
  因为外面通常套着 `try/catch`，症状是**"某些逻辑从来没生效过"**而不是报错。本项目一次扫出 **8 处**（2026-10-05 全修）：
  `AccOpsProvider.ensureCoexistAccFormatted` ×3、`AccOperatorCore`（清 pid+has_mutex）、`AccInfoFuncCore.unlinkHwndOfAccount`、
  `AccInfoFuncCore.deleteAvatarForAcc`（文件删了但返回 false、`avatar_url` 没清）、
  `SwConfigAccessor.getSwSettingAsString`（每次调用必 NPE，`SwInfoFuncCore`/`SwOperatorCore` 两个调用方受害）、`SwHexUtils` 空结果占位。
  替代写法：`Collections.singletonMap(k, null)`（允许 null）或 `HashMap`（多个键）；**要"删字段"就显式写 `remove` 语义**。
  写这类代码前先问一句："这个 map 的 value 里会不会是 null？"

- **"旧版有、新版漏了"的功能要对着旧实现核一遍**：平台版本号在原 Java 实现里只从**文件名**正则抠（`WeChat_8.0.47.61.exe` 能抠、`WeChat.exe` 抠不到 → 版本列长期空白），
  而旧版 Python 一直是调 `win32api.GetFileVersionInfo` 读**文件版本资源**。迁移时漏掉的不是"新功能"，而是**旧行为**。
  教训：迁移/重写时，凡是"看起来简单"的函数（版本号、路径、转义）都要和旧实现逐行对一遍。

---

---

# 关键技术教训（自 AGENTS.md 第十一节迁入，2026-10-05）

## 十七、关键技术教训（旧 AGENTS.md 第十一节 迁入，1~50 条）

> 注：本节条目**自带一套 1~50 的编号**（迁移时原样保留），与上面各章的编号无关。
> 原先的标题写作"## 十一、关键技术教训"，与"## 十一、行悬浮与选中着色"重号，2026-10-06 改为本章序号"十七"。

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
14. **构建脚本** → 两个都是**走 Gradle**（2026-10-06 实测源码更正）：
    `run.bat` = `gradle run --no-daemon`；`build-run.bat` = 先 `gradle compileJava compileTestJava`（**编译失败就直接中止、不进入运行**）再 `gradle run`。
    所以 `run.bat` 同样会编译/复制资源 —— Gradle 的任务链 `run → classes → compileJava + processResources` 自动决定做哪些；
    区别只在 `build-run.bat` 把编译**显式提前**、失败即止（更稳），`run.bat` 交给 Gradle 一把梭。
    （旧记录写的"`run.bat` 仅运行、不触发编译"是**错的** —— 前端改动之所以重启就能生效，正是因为 Gradle 的 `processResources` 自动把 `src/main/resources/**` 复制进 `build/resources/main`，而页面是走类路径 `getResource("/web/index.html")` 加载的。）
15. **Java varargs 与 JS bridge 不兼容** → JavaFX WebView 的 Netscape JSObject 桥无法将 JS 参数映射到 Java `String...` varargs（JVM 方法描述符多一个 `[String` 槽位导致反射匹配失败）。必须用固定参数，pathKeys 用 JSON 字符串传递
16. **路径中的反斜杠导致 JS JSON.parse 静默失败** → Windows `File.getParent()` 返回 `\` 路径 → Jackson 序列化为 `\\` → 嵌入 JS 单引号字符串时 `\\` 被解析为 `\` → JSON 中出现非法转义 → `JSON.parse` 抛 SyntaxError 被空 catch 吞掉。修复：所有路径在存入 PathEntry 前统一经 `normalizePath()` 处理
17. **"纯视觉效果"一律用 `transform`，绝不让元素脱离文档流**（2026-10-07 血泪三次）
    - 想做"拖动预览/滑动让位"这类**只改观感、不改结构**的效果，就用 `transform: translateX()`：它是**绘制阶段的位移**，
      **不参与布局** → 行高、列宽、`border-collapse` 折叠边框、单元格 `vertical-align` 全都不受影响。
    - 反面做法（我连踩三次）：把元素改成 `position: absolute` "脱离流好自由移动" ✗ ——
      ① 表格里 `border-collapse: collapse` 的边框是**相邻单元格共享**的，动一个边框会让折叠边框重新分配、行高跟着变；
      ② 脱离流后行高只能靠**测量值**硬撑，而表格单元格的 `height` 只是**最小高度** → 必然差几像素；
      ③ 绝对定位还会让 `vertical-align` 失效、文字基线跑偏；`height: 100%` 更会按更大的包含块算（列头被拉成整表高）。
    - 判断标准一句话：**"我要的效果会不会让浏览器重新排版？"** 会 → 想办法改成 transform/opacity 之类的合成属性；
      真需要改流，就在**松手后一次性重排**（本项目列换序的两阶段模型就是这么分工的）。
17. **路径规范化统一** → `SwPathDetective.normalizePath()` 统一处理：去引号、`\`→`/`、盘符大写、去末尾分隔符。所有 PathEntry 构造点必须调用
18. **ConcurrentHashMap 不允许 null 值** → 多线程合并结果时用 `Collections.synchronizedMap(new LinkedHashMap<>())`
19. **overflow:hidden 裁剪绝对定位子元素** → 下拉面板在 `position:absolute` 时被父容器 `overflow:hidden` 裁剪。解决方案：面板用 `position:fixed` 挂在 body 层，通过 `getBoundingClientRect()` 定位
20. **CSS 伪元素与 HTML 内容冲突** → `::after { content:'▼' }` 与 HTML 中的 `▼` 文字同时存在导致双图标。只用一种方式（HTML 文字 + `::before` 背景方块）
21. **用户数据目录命名** → 字符串常量必须用 PascalCase：`UserFiles`/`DevUserFiles`（非 `user_files`/`dev_user_files`）
22. **fixed 定位子元素的 z-index 受父容器层叠上下文限制** → `position:fixed` 元素的父容器若也设了 `z-index`（创建独立 stacking context），子元素 z-index 只在父容器内部有效，无法与父容器外元素比较。下拉面板的 `#mg-dropdown-layer` 设为 `z-index:40` 后子面板的 `z-index:80` 无效，必须将 layer 也调到 `40`
23. **侧栏 z-index 体系** → 主左栏 `100` > 次级左栏 `50` > 下拉面板 `40` > 默认 `0`。侧栏有 `position:relative` 创建层叠上下文
24. **overflow:hidden 裁剪 absolute 子元素** → 父容器 `overflow:hidden` 会裁剪 `position:absolute` 的子元素（即使设了 `z-index`）。下拉面板不能放在有 `overflow:hidden/auto` 的容器内，必须挂到 body 层；窗帘把手在面板内部时，展开态用 `overflow:visible`、收起态用 `overflow:hidden`
25. **CSS 路径规范化贯穿全链路** → 前端 `replace(/\\/g, '/')` + 后端 `Path.toString().replace('\\','/')` 双保险；设置页 `getActualDirVal()`、`getDefaultUserDir`、`saveConfigData` 返回值全链路规范化
26. **窗帘把手设计** → `position:absolute; bottom:0; transform:translate(-50%,50%)` 锚定面板底边半露出；`width:36px; border-radius:10px` 圆角胶囊流线型；仅方向符号 `∧`/`∨`；hover 变主题色
27. **路径检查必须先判存在** → `checkPath` 中 `Files.exists()` 为 false 时直接返回「路径不存在」（红色），不进入 `isValidSwPath` 详细检查逻辑（r_concat/l_concat/r_contain/l_contain）
28. **下拉面板缓存合并策略** → 每次打开面板重新探测，但新结果与旧缓存合并（同路径覆盖更新、新路径追加、旧独有保留），避免 DLL 路径依赖软件路径时因缓存清空丢失旧结果
29. **inline style 残留污染状态恢复** → 收起动画设置 `panel.style.maxHeight='0px'`（inline），完成后未清除。切换平台时 `classList.remove('collapsed')` 无法覆盖 inline style → 面板卡在高度 0。修复：`applyCurtainState` 展开时 `panel.style.maxHeight=''`，收起时显式设 `'0px'`
30. **collapsed 时 scrollHeight=0 导致展开动画无效** → 面板 `max-height:0` 时 `scrollHeight` 返回 0，过渡目标为 0 无动画。修复：先 `remove('collapsed')` 读真实 `scrollHeight`，快照到 0，再 rAF 过渡到真实高度
31. **SVG pointer-events:none 阻止 click 事件** → SVG 设 `pointer-events:none` 后 click handler 无法触发，需绑在内部 `pointer-events:auto` 的子元素（如热区 rect）上
32. **平台状态持久化** → 设置面板展开/收起状态按平台独立存储在 `LocalSwConfig.json.{swId}.settings_expanded`（boolean），用 `updateSwField` 写入、`getSwConfig` 读取；切换平台时先读后应用
33. **AppEnv 运行环境判断** → `AppEnv.java`：先读 JVM 系统属性 `run.mode`（支持 DEV/TEST/PROD），再自动检测 code source 路径是否以 `.jar` 结尾 → PROD:DEV；`Launcher` 中 `--dev` 参数改为设 `run.mode=DEV` 系统属性
34. **路径检查详细提示** → `SwAdapterChecker.checkSwPathDetail()` 返回 `{valid, reason}` 含中文提示：r_concat→"缺少关键文件「{file}」", l_concat→"应在「{text}」文件夹内", r_contain→"未找到含「{text}」的文件", l_contain→"上级目录应包含「{text}」"
35. **跨平台动画复用原则** → 不同平台之间切换时的高度过渡，视觉效果上完全可以转化为"同一页面内的高度变化动画"。先记录 A 平台当前高度 `_prevHeight`，切换到 B 后直接调用已验证的单页面动画函数 `animatePanelHeight(savedH, null, _prevHeight)`，从 `_prevHeight` 平滑过渡到 `savedH`。不引入新条件分支、不手动控制 transition、不复刻展开/收回逻辑。**已验证可复用的动画函数，就直接复用，不要重写。**
36. **把手与面板容器一体化** → 将面板和 SVG 把手包裹在 `#manage-curtain-container`（`position:relative`）中，把手 `position:absolute; bottom:-20px` 自动跟随容器底部，移除所有 JS 手动定位代码（`getBoundingClientRect`、`style.top`、`startFollow/stopFollow` RAF 循环）
37. **内容区 max-height 是高度上限的隐形锁** → CSS `.manage-settings-content { max-height: 180px }` 会限制面板实际高度。自由高度动画前必须将内容区设为 `max-height: none`，否则面板涨不上去
38. **transition: none 快照与 transition 恢复必须在不同帧** → 单 `requestAnimationFrame` 保证快照帧与过渡帧分离；双 RAF 不一定更好（可能引入额外延迟）
39. **`getBoundingClientRect().height` 比 `parseInt(style.maxHeight)` 更可靠** → 前者返回实际渲染高度（含 padding/border），后者可能为空字符串或受 CSS 覆盖
40. **纯复制迁移法** → 从旧代码中完整复制 DOM + JS 到新位置，保持 ID/逻辑完全相同，再通过实际效果逐步调试。不会破坏原本已实现的页面和逻辑，远比"理解后重写"更可靠。例如 page-main 复制自 page-manage，main.js 复制自 manage.js
41. **`getEl` 作用域隔离** → 复制出的页面与原始页面存在相同 DOM ID，`document.getElementById` 始终返回 DOM 中第一个匹配。修复：`getEl` 改为 `querySelector('#page-main #' + id) || document.getElementById(id)`，优先在目标页面内查找
42. **`bind()` 也要走 `getEl`** → `bind(id, evt, fn)` 内部必须用 `getEl(id)` 而非 `document.getElementById(id)`，否则事件绑定到原始页面元素而非副本页面
43. **JS Bridge 注入时序** → `DOMContentLoaded` 时 JS Bridge 尚未注入（Java 端 `injectJsBridge()` 在页面加载完成后才执行）。页面初始化如需调用桥方法，应由 `MainWindow.injectJsBridge()` 末尾主动 `executeScript` 触发，而非依赖 `DOMContentLoaded`
44. **跨页面联动使用 `document.getElementById`** → 主侧栏 `#nav-platform-list` 不在 `#page-main` 内，不能走 scoped `getEl`。跨页面的元素查询直接用 `document.getElementById`
45. **`_handleAsync` 第三参必须是字符串** → `bridge.js` 的 `_handleAsync(type, cbId, jsonStr)` 仅当 `typeof jsonStr === 'string'` 才 `JSON.parse`。Java 端 `pushToJs` 若直接嵌入 JSON 对象字面量，JS 侧 `data` 为 null（回调拿到 null）。修复：`pushToJs("..._handleAsync('avatar',"+cbId+","+ MAPPER.writeValueAsString(payload) +")")` — 把 JSON 字符串再编码为 JS 字符串字面量（对 SVG data URL 内单引号也安全）
46. **Logback 未定义属性 → `${name}_IS_UNDEFINED` 目录** → `${jfmultichat.logdir}` 必须加默认值回退 `${jfmultichat.logdir:-logs}`（`<file>` 与 `<fileNamePattern>` 两处）；否则任何绕过 Launcher 的入口（IDE 直接跑 MainApp、测试、回归）都会在 cwd 生成 `jfmultichat.logdir_IS_UNDEFINED/`
47. **logdir 属性需在首次 `LoggerFactory.getLogger()` 前设置** → Launcher 将 `System.setProperty("jfmultichat.logdir", AppPaths.getLogsDir().toString())` 放在 main 首行；`AppPaths`/`AppEnv`/`AppVersion` 均无 Logger，可在 pre-init 安全读取路径
48. **后台会话 worktree 隔离可关闭** → `.claude/settings.json` 设 `"worktree": {"bgIsolation": "none"}` 后后台会话可直接编辑主目录文件（需用户授权；该文件被 gitignore，仅本地）
49. **日志目录固定根配置位置** → 设置页打开/显示日志目录用 `AppPaths.getLogsDir()`（`%APPDATA%\JhiFengMultiChat\{ver}\{Dev?}UserFiles\logs`），不随用户自定义数据目录；与 logback 实际写入位置一致
50. **`Map.of` 不允许 null 键/值** → 写账号数据回写时 `Map.of(PID, pid, ...)` 因未运行账号 pid 为 null 直接 NPE（`ImmutableCollections$MapN` 构造器 `Objects.requireNonNull`）。必须用 `HashMap`；`ConfigManager.updateAccount` 对 null 值会移除该键（未运行账号不存 pid，语义正确）。同理对 `JsonNode.get(key)` 结果先判空再 `.asBoolean`

---

## 十八、Windows 句柄 / 进程 API 的坑（2026-10-07 实测，互斥体查杀与降权启动）

1. **`DuplicateHandle(DUPLICATE_SAME_ACCESS)` 必须给"目标进程"**：复制到本进程要传 `GetCurrentProcess()`；
   传 `null` 只在 `DUPLICATE_CLOSE_SOURCE`（关闭源句柄）时才合法 → 传错就是"扫了 30 万条、命中 0 条"。
   关闭**别的进程**的句柄，标准技巧正是 `DuplicateHandle(源进程, 句柄, NULL, NULL, 0, false, DUPLICATE_CLOSE_SOURCE)`。
2. **不要用 `NtQueryObject(ObjectBasicInformation)` 预探名字长度**：本机（Win11 26340 / JDK 17）这条调用
   **恒返回 `STATUS_INFO_LENGTH_MISMATCH(0xC0000004)`**，据此提前 `return null` 会把**每个**句柄都当失败跳过。
   正确做法：直接给足缓冲查 `ObjectNameInformation` / `ObjectTypeInformation`，真不匹配时按返回长度扩容重试。
3. **`NtQueryObject` 对某些对象类型会阻塞**（管道/同步对象）→ 枚举句柄这条链路**别轻易上多线程**：
   一旦某次调用卡住，整批都被拖住。更划算的是"减少要枚举的 PID"（见 4）。
4. **性能：别重复扫描已知干净的 PID**。多开 N 个实例后，同平台 PID 会累积（每个实例自带几百个句柄），
   逐个复制+查名的成本线性膨胀（实测 5 个 java 子进程 ≈ 931ms）。用一个**全局共享的"已查杀 PID"容器**
   （`ConcurrentHashMap<pid, 时刻>` + TTL）跳过它们 → 同样的调用降到 **0ms**。TTL 是为了防"程序之后又重建互斥体"时漏杀。
5. **`CreateProcess*` 的 `lpApplicationName` 不要用正斜杠**：本项目内部路径统一规范化成 `/`，直接喂进去**实测失败**；
   调用前 `replace('/', '\\')`。
6. **降权启动：先判断自己是不是管理员**
   - 管理员 → 借 explorer 令牌（`GetShellWindow` → `GetWindowThreadProcessId` → `OpenProcessToken(TOKEN_DUPLICATE)`
     → `DuplicateTokenEx(SecurityImpersonation, TokenPrimary)` → `CreateProcessWithTokenW`）→ 子进程中完整性；
   - **非管理员 → 直接 `CreateProcess`**（子进程继承中完整性令牌，本来就是普通权限）；
     此时去用 explorer 令牌会 **`ERROR_PRIVILEGE_NOT_HELD(1314)`**，因为普通进程没有 `SeImpersonatePrivilege`；
   - 令牌法失败兜底：`explorer.exe <exe>` 代启（explorer 是普通权限）；
   - 判定手段：`OpenProcessToken(GetCurrentProcess())` + `GetTokenInformation(TokenElevation)`；
     验证手段：让子进程跑 `whoami /groups`，看 "Mandatory Label"（父 High / 子 Medium）。
7. **`CreateProcessWithTokenW` 对"超长 + 内嵌引号"的命令行会报 `E_INVALIDARG(0x80070057)`**：
   把复杂命令写进 `.bat` 再 `cmd /c <bat>` 更稳（应用自身只传 exe 路径，不受影响）。
8. **"空集合"与 `null` 的语义必须分开**：`findHandles(pids=[])` 若和 `null` 一样被当成"不限制进程"，
   就会去扫**全部**系统句柄（30 万条、几分钟）—— 这是缓存全部命中（候选为空）时踩到的真事故。
   约定：**空集合 = 没有目标（立刻返回）；`null` = 不限制**。
