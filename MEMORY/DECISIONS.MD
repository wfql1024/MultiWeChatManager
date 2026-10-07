# 决策点

## page-main 复制迁移
- **决定**: 从 page-manage/manage.js 完整复制 DOM+JS 到 page-main/main.js，先不动旧代码
- **原因**: 用户发现逐段理解和改写容易出错，完整复制再逐步调试更可靠，且不会破坏已实现的页面
- **日期**: 2026-07-04

## 侧栏精简
- **决定**: 移除"登录"和"管理"按钮，仅保留平台列表 + 统计 + 设置
- **原因**: page-main 已成为默认主页，原导航按钮不再需要
- **日期**: 2026-07-05

## 旧代码剥离
- **决定**: manage.js → .old/，page-manage HTML 块从 index.html 删除
- **原因**: main.js + page-main 已完全替代原管理页功能
- **日期**: 2026-07-05

## 版本号管理
- **决定**: AppVersion.java (`4.0.0.7000`) 为版本号唯一来源，build.gradle.kts 和打包脚本从此读取
- **原因**: 用户要求"一个地方决定版本号"
- **日期**: 2026-07-05

## 打包方案
- **决定**: 使用 jlink (精简 JRE) + jpackage (生成 .exe)，提供安装版和便携版
- **原因**: 用户需要自包含 EXE，用户无需安装 Java
- **日期**: 2026-07-05
- **关键配置**: 
  - jlink: `--compress 2 --strip-debug --no-header-files --no-man-pages`
  - jpackage: `--type exe --win-dir-chooser` (安装版), `--type app-image` (便携版)
  - JavaFX jars 从 Gradle 缓存引用，运行时由 jlink 嵌入

## 头像重构（2026-07-30）
- **决定**: 新增 `AvatarUtils.java` 统一头像获取逻辑，整合本地文件读取、URL 下载和 SVG 文字回退
- **原因**: 账号列表头像不显示，需与旧版 Python 行为一致，同时支持用户自定义数据目录
- **日期**: 2026-07-30

## appcore/acccore 架构（2026-07-31）

**决策**: 将 legacy_python 的 func_core + functions 包迁移为 Java appcore/acccore 两个包，参考 swcore 架构模式。

**结构**:
- `appcore` — 对应 `app_func_core.py` + `app_func.py`（AppConfigAccessor + AppCore + AppCoreConstants）
- `acccore` — 对应 `acc_func_core.py` + `acc_func.py`（AccConfigAccessor + AccInfoFuncCore + AccOperatorCore + AccOpsProvider + AccCoreConstants）

**关键设计**:
- appcore/acccore 直接用 `ConfigManager.getInstance()` 读写，不依赖 JsBridge 的 private `BridgeConfigProvider`
- 新增公开的 `SwConfigProvider`（实现 `SwConfigAccessor.Provider`），供所有包通过 `SwConfigProvider.newAccessor()` 获取配置访问器
- `AccOpsProvider` 提供 `toSwProvider()` 转换为 swcore 的 `AccountOpsProvider`，避免循环依赖

**原因**: 减少对 JsBridge 私有类的耦合，让核心包可独立编译和测试。

**注意**: 编译时遇到 BridgeConfigProvider 私有访问问题，已通过 SwConfigProvider 解决。

## 账号列表来源 = 磁盘扫描（2026-07-31）
- **决定**: 平台页账号列表以 `SwInfoFuncCore.getSwAllAccountsExisted`（磁盘扫描：数据目录子目录 − 排除目录 + 共存 exe）为来源，SwAccData.json 仅作详情补充
- **原因**: 让磁盘真实存在的账号（新增目录/共存 exe）自动出现，移除已删除残留记录
- **实现**: `JsBridge.getSwExistedAccounts` → `SwConfigProvider.newAccessor()` + `SwInfoFuncCore` facade；main.js 按 ID 合并详情

## 头像接入 acccore/AvatarUtils 管道（2026-07-31）
- **决定**: 账号列表头像走 `AccInfoFuncCore.getAvatarFromCache` + `getAccAvatarFromFile`（→ `AvatarUtils.getAvatarDataUrl`），异步逐行更新
- **原因**: 之前直接渲染 avatar_url 不显示；需统一"本地文件 → URL 下载 → SVG 回退"且不阻塞 UI

## 日志目录固定根配置位置（2026-07-31）
- **决定**: 日志目录固定 `AppPaths.getLogsDir()`（`%APPDATA%\JhiFengMultiChat\{ver}\{Dev?}UserFiles\logs`），不跟随用户自定义数据目录
- **原因**: 根配置确定日志位置；与 logback 实际写入一致（Launcher 先用该路径设属性）

## legacy_python 保持忽略（2026-07-31 确认）
- **决定**: `legacy_python/` 继续在 .gitignore 忽略，不纳入版本管理
- **原因**: 仅供迁移参考，体积大且不支撑项目运行

## 后台会话关闭 worktree 隔离（2026-07-31）
- **决定**: `.claude/settings.json` 设 `"worktree": {"bgIsolation": "none"}`，后台会话可直接编辑主目录文件
- **原因**: 用户偏好直接改主目录文件，不接受强制 worktree；该文件被 gitignore，仅本地生效

## EventBus 事件机制（2026-08-01）
- **决定**: 自建轻量 EventBus（`core` 包，观察者模式）解耦「数据更新」与「UI 刷新」
- **原因**: 痛点——之前任何数据更新只能在每个更新方法里触发整表重渲染（`renderAccountTable`），刷新又带动头像重拉等系列加载；且 `getSwAccountsLoginStatus` 为 god-method（配置/pid/写库/状态计算耦合）。EventBus 使新增数据需求 = 新增订阅者，不改既有代码
- **流A 进入自动维护**: 进入平台页发布 `PlatformEnteredEvent` → 后台自动维护登录态数据（PID/共存/互斥体回写 SwAccData）
- **流B 定向刷新**: 账号数据写库后发布 `AccountDataChangedEvent` → 定向推送 JS 仅刷新受影响行/格（toggle-hidden 已迁移，删除/批量等后续增量迁移）
- **选型比较**: ① EventBus 订阅方零依赖、最解耦、可扩展（选定）；② JsBridge 多槽 Consumer 订阅方须持 JsBridge 引用；③ JavaFX Property 有 FX 线程约束（耗时维护须甩后台）。三者中 EventBus 最契合「appcore/acccore 解耦 JsBridge」的既有方向
- **关键文件**: `core/EventBus.java`、`core/event/*.java`、`PlatformEventBootstrap.java`、`AccInfoFuncCore` 拆分三步

## 账号列表列定制（2026-08-16）
- **决定**: 账号列表重构为 7 列（勾选框/头像/展示名/快捷键/ID/平台内ID/昵称），参考 Windows 资源管理器交互
- **状态/操作列移除**: 用户决策——不保留独立"状态"/"操作"列；操作改为展示名列右端悬浮小按钮（隐藏按钮选中态 = 已隐藏），行右键菜单提供隐藏/删除；禁用保留展示名旁小标签
- **列头右键菜单**: 勾选显示列，勾选框/头像/展示名/快捷键 4 列必选锁定；默认显示 + ID，alias/nickname 默认隐藏；"所有列自适应大小"/"该列自适应大小"
- **列宽拖拽**: `table-layout: fixed` + colgroup + `.col-resizer` 竖线，拖拽调宽，最后可见列不加竖线
- **快捷键列**: 点击激活输入框，keydown 捕获组合键，保存 SwAccData.hotkey（走 saveAccount → 流B 定向刷新）
- **排序**: 去掉 " ↕" 字符，保留点击排序，当前列用 `.sorted` 高亮（主题色+加粗）
- **持久化**: 列显示/宽度存 `LocalGlobalConfig.json.account_columns`（全局偏好，不随平台）
- **原因**: 数据字段（alias/nickname/hotkey）SwAccData 已具备、getSwDetailData 已全量返回，纯前端即可完成；交互贴近 Windows 资源管理器习惯

## 四表架构与可复用组件（2026-08-16 第二轮）
- **决定**: 平台页从上到下四个表：原生程序/原生账号/共存账号/无效账号；表格封装为可复用组件 `JFC.AccountTable`（`js/components/account-table.js`），列定义驱动，后续不同标题/列组合的表直接实例化复用
- **标题行**: 常显，标题左端 + "已选 N 项"/批量按钮右侧（未选中隐藏），替代原选中才出现的浮动工具行
- **数据分类**: 原生账号 = `getSwExistedAccounts(swId,'origin')`（数据目录子目录）；共存账号 = `'coexist'`（共存 exe）；原生程序/无效账号暂无数据先空显示
- **固定列**: 勾选框（40px）/头像（56px）固定宽度不可拖拽/自适应；固定列间与右侧竖线移除；头像改圆角矩形（border-radius 6px）
- **快捷键录入修复**: ① `document mousedown` 提交替代 blur 同步提交（消除 DOM 竞态导致的"点击无反应"）；② Java Scene 级 EventFilter 兜底捕获（`notifyHotkeyCapture`）——WebView 收不到的带修饰键组合键由 Java 捕获推送回 JS；OS 级全局热键占用仍无法拦截（系统层行为）
- **列宽自适应**: 已定稿（2026-08-16 晚间）——下限 = 列名宽 + 余量（展示名列 = 4字符 + 按钮占位总宽），无上限；表格宽度恒 = 可见列宽总和（列宽独立、超宽横向滚动）；固定列绝对固定不参与

## 滚动条体系与布局锁定（2026-08-16 晚间）
- **滚动条方案**: JavaFX WebView 原生滚动条不可靠（overlay 鼠标悬停才显示、纵向需手动触发、带上下箭头、不随深浅主题）→ **统一用自定义 overlay 滚动条**（DOM 元素 `attachCustomScrollbar`，挂滚动容器父级避免随内容滚动、rAF 驱动位置、显示条件=内容溢出+鼠标在内容区/滚动条上、5px 胶囊、不占位不撑高）。"原生能实现才用原生"——走过弯路：曾回归原生滚动条（设置区域需手动触发又改回自定义）
- **高度链锁定**: 内容撑宽/撑高（flex/grid `min-width:auto`/`min-height:auto`）是横向/纵向滚动条不出现的统一根因 → `#page-main .manage-layout` 改 **flex column** + `.manage-detail-area` `flex:1; min-height:0; min-width:0; overflow:hidden` + 表容器链 `min-width:0`。弯路：grid `1fr` 被 `#page-main` 高特异性规则覆盖、block 布局破坏纵向
- **列宽规则**: 表格宽度恒 = 可见列宽总和（px，绝不填充容器，否则 `table-layout:fixed` 按比例拉伸列导致列宽联动）；固定列强制 defWidth 不读持久化
- **整行悬浮高亮**: JS 高亮层 `.acc-row-highlight` 统一负责（mousemove 委托匹配任意 tr 含空行）；**移除 `tr:hover` 背景**——与高亮层叠加会导致列区域/剩余区域颜色不一致
- **分割线**: 设置/账号区域分界 + 窗帘把手用 `--divider-solid`（背景+半透明混合的**不透明等效色**，深 `#2c2c2c`/浅 `#d4d4d4`），避免半透明重叠区两次叠加变深
- **设置区域滚动条根因**: `animatePanelHeight` 动画期间 `content.style.maxHeight='none'`（教训 #37 让面板能撑高）但**动画后未恢复** → content 高度=内容高永不溢出。修复：动画结束（setTimeout 兜底，JavaFX transitionend 不可靠）恢复 `content.maxHeight = targetHeight`
- **规则文件统一 AGENTS.md**: 项目 `CLAUDE.md` → `AGENTS.md`（DSH/CC 通用约定，DSH 默认候选 `["AGENTS.md","CLAUDE.md"]`）；全局 `~/.dsh/AGENTS.md`（DSH 全局仅认此名，不读 `~/.claude/CLAUDE.md`）——用户决策

## 开发者工具源集与加密单一实现（2026-10-04）

- **背景**: 远程配置加密原本是 Python 脚本（`legacy_python/scripts/encrypt_data.py`），需要与 Java 侧解密联动；用户日常既要开发软件、又要维护两份远程配置 JSON
- **决定**: 新增 **`src/tools/java` 源集**承载开发/发布工具，配 `JavaExec` 任务 `encryptRemoteConfigs`；工具**复用** `config.CryptoUtils` 的加密实现，而不是在脚本里重写一套
- **原因**:
  - 加密格式是对外契约（已发布产物必须永远可解），实现只能有一份；`CryptoUtils` 现在同时提供 `encryptAndAppendKey`/`decryptResponse`，并有测试锁定格式
  - `src/tools` 独立源集 → 工具能用项目类与依赖、能进编译检查，但**不进应用 jar/安装包**（区别于塞进 `src/main`）
  - 单文件 `java scripts/X.java` 方案被否：无法 `import com.jfmultichat.config.CryptoUtils`，会导致加密逻辑双份、易漂移
- **约定**: 新增此类工具一律放 `src/tools/java` + 注册 Gradle 任务；版本号提升只改 `RemoteConfigFetcher.BUILTIN_REMOTE_*_VERSION`
- **验证**: `gradle test` 全绿（CryptoUtilsTest 6 + 既有用例）；`gradle jar` 中无 tools 包；与历史 Python 产物兼容性有测试与实测双重证据

---

# 决策记录（2026-10-05 汇总）

## D-01 设置区域"窗帘"改为全局统一（记录即唯一事实来源）

- **决策**：高度与展开/收起态各只存一份（`LocalGlobalConfig.json` 的 `settings_height` / `settings_expanded`），所有平台共用
- **理由**：原先按平台各存一份，用户必须在每个平台重复调高度；改全局后"拖一次，处处生效"
- **配套**：状态变更一律"先写记录，再按记录渲染"；渲染只有一个写入点（`applyCurtainRender`），彻底消除多路径互相拉扯

## D-02 "未启用平台"每次渲染都强制展开，且不写记录

- **判定**：三个路径项（`inst_path`/`data_dir`/`dll_dir`）是否**全是绿框** —— 绿框由路径检查流程判定并记录，窗帘侧**只读**
- **行为**：未启用平台每次渲染强制展开；用户在本次访问里可临时收起（只影响这一次渲染），**不写记录、不留本地状态**
- **理由**：设置不全的平台强制展示设置区，方便用户补全；同时不许它污染全局记录

## D-03 平台图标：64×64 提取 + PNG 缓存到平台目录

- **决策**：`{用户数据目录}/{swId}/{swId}.png`；有图且 `inst_path` 未变 → 直接用；缺图或软件路径变了 → 重新提取覆盖；**提取失败什么都不做**（保留原图）
- **理由**：图标提取（Windows Shell + 磁盘 IO）不该每次进平台都跑；缓存到用户数据目录可随数据迁移、可手工替换
- **尺寸**：`FileSystemView.getSystemIcon(file, w, h)`（Windows 支持任意尺寸，实测 48/64/128/256）

## D-04 单一职责：把"判定权"还给对应流程

- 图标提取只判"软件路径存的值是不是程序"，**不**负责"目录里该是哪个 exe"（那是路径探测流程的事）
- "平台是否启用"只**读**路径检查流程的绿框结果，**不**自己判断"填没填全"
- 理由：判定权一旦出现两份，规则就会长期打架且难以察觉

## D-05 移除"借标题当通知"的整套模式

- **决策**：删掉 `flashTitle()` 的两份实现与全部 8 处调用；平台标题只表示平台名称
- **替代**：状态变化靠就地可见的变化表达（按钮文案、行内标签、置底、行消失）；真要提示就放在该功能所属区域内部
- **理由**：标题是标识不是通知区，跨区域借用控件会破坏语义、也让"标题"这一处出现多个写入者

## D-06 无效账号并入原生/共存表（不再单列一张表）

- **决策**：无效账号 = SwAccData − 原生 − 共存，按自身类型并入对应表，`invalid` 行灰字 + "失效"标签 + **永远置底**
- **理由**：少一张表 = 少一套列配置/滚动条/标题行；用户视角就是"这个平台的账号（含失效的）"

## D-07 账号表末尾加"占位列"

- **决策**：`_filler` 内部列（不在 `columns` 里，不参与排序/显隐/列菜单），宽度 = 容器可视宽 − 可见列宽总和
- **理由**：① 所有真实列右侧都有邻居 → 列宽拖拽热区不再压在表格边界；② 占位单元格属于该行 → 整行悬浮/选中感应区天然覆盖容器宽

## D-08 行悬浮/选中用"绝对定位色块层 + 不透明等效色"

- **决策**：色块层 `z-index:-1` + 容器 `isolation:isolate`；色值用**不透明等效色**（`--bg-row-hover` / `--bg-row-selected`）；选中行不叠悬浮色
- **理由**：`tr` 背景覆盖不到表格右侧空白；半透明色叠加会二次变深、跨主题不一致

## D-09 文档分家（本日确立）

- **决策**：根 `AGENTS.md` 只写"项目当前状态的全局视图"（身份/技术栈/结构/命令/约定/指针，≤300 行）；变更过程 → `MEMORY/DEV_LOGS.MD`；踩坑教训 → `MEMORY/LESSONS.MD`；架构细节 → `docs/project_structure.md`
- **理由**：AGENTS.md 每次会话都被注入上下文，混入大量历史会挤占空间、稀释重点；拆开后可按需读取
- **判断标准**："这是现在是什么样，还是曾经发生了什么？"

---

# 决策记录（2026-10-05 晚 ~ 10-06 凌晨 汇总）

## D-10 刷新入口与页面进度条

- **决策**：标题栏刷新按钮（SVG）→ `JFC.router.refresh()`；**冷却门只放在 `refresh()` 内部**（`REFRESH_COOLDOWN_MS=2000`，返回 true/false），按钮同时禁用 2s；页面加载进度条最小显示 400ms
- **理由**：冷却属于"刷新能力"本身，放路由层才能被所有入口（按钮/单击当前平台）共用；进度条太短会闪

## D-11 平台图标 SVG 化 + 单击/双击策略

- **决策**：平台图标改用内联 SVG（Lucide，`TITLE_ICON_PX=16`）；点击策略 = 点别的平台立即切换；**点当前平台单击=刷新**（等 `MULTI_CLICK_GUARD_MS=250` 确认无后续点击）；当前平台双击/多击不响应（路径预留）
- **理由**：PNG 在高分屏发虚；"点当前平台刷新"要在双击窗口后才能判定，否则会把双击误当两次刷新

## D-12 一律用 `JFC.modal.confirm/custom`，禁用 `window.confirm`

- **决策**：自建模态（`JFC.modal`），不再用 `window.confirm`/`alert`
- **理由**：JavaFX WebView 里 `window.confirm()` **没有 handler 时恒返回 false**、`alert()` 是空操作 —— 表现是"删除点了却总是静默取消"，极难自查

## D-13 名称列就地编辑：单一渲染点 + 保存延后一拍

- **决策**：单元格 HTML 只由 `nameCellInnerHtml()` 产出（渲染与编辑结束回填共用）；提交后**延后一拍**（`setTimeout 0`）再 `saveAccount` + 整表重排；`_editFinish` 一律指向 `cancelEdit`
- **理由**：① 两处各写一份 HTML 必然漂移；② 提交常发生在 `mousedown` 阶段，此刻重建 tbody 会让用户这一下点击落空（实测"要点第二次"）；③ 切换编辑目标时"只清状态不还原 DOM"会留下输入框

## D-14 勾选框自绘（label + 透明 input + `.acc-check-box`）

- **决策**：原生 `input[type=checkbox]` 只当状态载体（透明），可见方块自绘
- **理由**：原生控件在 WebView 里**先画一帧原生外观再套样式**（用户看到的"先方后圆"闪烁）；视觉交给原生就必然有一帧错样

## D-15 程序表快捷键存 `LocalSwConfig.<sw>.hotkey`

- **决策**：原生程序表（平台自身）的快捷键写平台配置，**不写 `SwAccData`**
- **理由**：程序行不是账号；往 SwAccData 写会留下一条"以路径为键"的节点，下次加载被当成**失效账号**冒出来

## D-16 版本号读 Windows 文件版本资源（JNA），退化值用产品版本

- **决策**：`SwVersionHelper.getFileVersion` 先读文件版本资源（`VerQueryValue` / `dwFileVersionMS|LS`）；当 `x.0.0.0`（x≥1000）这种明显退化的版本时改用 **productVersion**；最后才回退文件名正则
- **理由**：旧 Java 实现只从文件名抠版本 → `WeChat.exe` 这类抠不到，版本列长期空白；而旧 Python 一直是读文件版本资源（属"迁移漏掉的旧行为"）

## D-17 账号头像文字兜底 = 名称末尾 4 个字符宽（中文算 2 宽）

- **决策**：账号表兜底取"名称末尾 4 字符宽"；**原生程序表与侧栏仍取首字符**
- **理由**：账号名多为中文（末尾更可辨识），程序名多为英文（首字母更有信息量）

## D-18 中文字体 = 微软雅黑；字号统一 14px、名称列 15px；中英字体由 JS 拆段

- **决策**：中文一律微软雅黑、英文保持等宽；表内字号 14px、名称列 15px；"中文雅黑 + 英文等宽"由 **JS 按字符集拆成 `.cjk-run`/`.lat-run` 两个 span** 实现
- **理由**：实测本 WebKit **做不到**在一个元素内按字符集分字体（等宽族缺中文时走**系统 CJK 回退**，列表后面的雅黑根本不生效；`@font-face + unicode-range` 在此版本也不生效，放最前会把英文一起吃掉）

## D-19 勾选框勾选态 = 一整块填充（不是"内填充 + 同色边框"）

- **决策**：勾选态 `background-clip: border-box` + **`border-color: transparent`**，尺寸/圆角与空框外沿完全一致（16px 含 1px 边框、4px 圆角）
- **理由**：同色 border + background 是**两层几何**（padding box 内圆角 + 外圆角），圆角处会露缝 —— 用户看到的"镂空/四个黑点"就是这个。验证办法：数"形状内部既非填充色也非勾色"的像素，应为 0

## D-20 表格文字三级色（`--text-level1/2/3`）

- **决策**：1 级最重（深色=纯白 / 浅色=纯黑）→ 3 级最轻（深色=深灰 / 浅色=浅灰）；**普通行**名称列=1 级、其它列=2 级；**隐藏行**（`tr.hidden-row`）整行=2 级；**失效行**（`tr.invalid-row`）整行=3 级（CSS 顺序上失效优先）
- **理由**：三档把"重要程度"直接映射到明度；令牌**只作用于表格内容**，不动其它 UI 的 `--text-primary/secondary/muted`

## D-21 三张表的名称列完全统一

- **决策**：三张表名称列都用 `key='display_name'` → 复用同一个 `.manage-nickname-cell`（可编辑 / 1 级色 / 15px / 字重 600 / 中英分段）；程序表用 `showRowActions:false` 去掉"隐藏/重置/删除"悬浮按钮
- **理由**：组件层本来就复用（同一个 `AccountTable`），之前"没统一"只是**列 key 不同**导致走了通用文本列分支；账号语义的行操作按钮对程序行无意义

## D-22 原生程序名称链 = `origin_exe.remark` > 平台名称；`origin_exe` 不是账号

- **决策**：程序名 = `SwAccData.<sw>.origin_exe.remark`（原生账号 remark）优先，否则平台名称（本地 remark > 远程 alias > swId）；`origin_exe` 作为**固定 id** 的"程序自己的备注"节点，**所有遍历账号的地方必须排除它**
- **理由**：用户给出的四级链实际已包含平台名称三级链 → 简化为两级；不排除 `origin_exe` 会让它变成"失效账号"冒出来，或让"取第一个账号"的退化路径写错节点

## D-23 `_alias` 不再持久化

- **决策**：远程别称（alias）改为**按需取**（`getRemotePlatformInfo`）；加载配置时 `delete config._alias`，下次保存即从 `LocalSwConfig.json` 清掉
- **理由**：它是内存缓存，却因保存整个 `swConfigData[sw]` 被写进了本地配置文件（用户在看配置时发现）；远程别称本来就能从远程配置取

## D-24 删除 / 重置的语义与副作用（都清头像文件）

- **决策**：**删除** = 配置节点整体移除；**重置** = 清空节点内容、**保留空节点**（列表照常加载、初始化流程会重填属性）；两者都调用 `AccInfoFuncCore.deleteAccountAvatarFiles()` 清除 `{userData}/{sw}/{acc}/` 下的头像文件
- **理由**：留空节点才能让"重置"表现为回退到自动识别而不是"账号消失"；头像文件不清会留下孤儿文件（用户明确要求一并清除）
- **边界**：只清图片（jpg/jpeg/png/bmp/gif），**非图片文件保留**，目录空了才删目录（绝不递归删别的）；平台图标 `{sw}.png` 不受影响

## D-25 批量删除只对失效账号生效（但确认框照常弹）

- **决策**：批量删除**照常弹确认框**，文案按选中情况说明（全正常 / 有跳过 / 全失效三种），用户仍可确认；**执行层**才过滤掉正常账号
- **理由**：最初写成"一个失效账号都没有就静默 return" → 用户指出"这样用户会疑惑为啥点不了"。**按钮点了没反应比弹窗说明原因更糟**

## D-26 右键菜单三项齐全，不能做的**显示为禁用**

- **决策**：行右键菜单 = 隐藏 / 重置 / 删除；正常账号的"删除"**显示但禁用**（带悬停提示）
- **理由**：隐藏会让人以为"没这功能"；禁用 + 提示才说清"有这功能但现在不能做"。**注意禁用项仍要带 `data-row-action`**（否则选择器/事件绑定/测试全会漏）

## D-27 中文抗锯齿：`-Dprism.lcdtext=false` 试验开关（**待用户最终定夺**）

- **决策**：`build.gradle.kts` 的 `run` 任务加 `-Dprism.lcdtext=false`（灰度 AA），作为可一行回退的试验
- **理由**：实测 JavaFX 默认就是 LCD 次像素抗锯齿（彩色边缘占比 97%），深色底 + 中文复杂笔画会发虚；关掉后边缘对比度 51.3 → **53.5**、彩色边缘 **0%**。**字体换不换几乎无差别**（四个字体分区边缘对比度一致）
- **未决**：用户比对后保留/去掉；若保留，打包脚本 `scripts/package-exe.bat` 的 `--java-options` 也要加

## D-28 离线验证方式：`build/_probe` 探针（本项目长期做法）

- **决策**：交互/渲染类改动一律用 `build/_probe/*.java` 离屏探针验证 —— 真实 `index.html` + 桩桥（`StubBridge` 记录调用）+ 驱动脚本执行断言；必要时做**离屏像素统计**（ASCII 位图 / 颜色分类 / 形状轮廓比对）；Java 侧逻辑用直连探针（如 `AccFilesProbe`）跑真实代码
- **理由**：模型读不了图、也不该让用户当测试机；探针能把"偏移 1.25px""内部镂空 0""LCD 彩色边缘 97%"这类结论量化下来，还能在非正常入口暴露真 bug（例：`ConfigManager.getInstance()` 的静态 `init` 误用就是探针 NPE 才挖出来的）
- **边界**：离屏环境拿不到 DOM 选区（`window.getSelection()` 恒空，`requestFocus()` 无效）→ 光标/输入法这类交互**必须真机验证**，别在探针里下结论
- **现状提醒（2026-10-07）**：探针源码放在 `build/_probe/`，而 `build/` 会被 `gradle clean` 整个清空、且不进版本控制 → **已全部丢失**。下次要用探针，建议把源码改放 `tmp/`（gitignore）或纳入版本控制

## D-29 平台页分"登录态 / 管理态"两种形态（2026-10-06 用户定）

- **决策**：同一页两种形态，右上角二元滑块按钮切换；`'login'` 为**默认**；模式是**会话内变量**（不写配置、不按平台记忆、切平台不改）；登录态下：设置区域隐藏（**不动记录**，切回按记录恢复）、失效/隐藏账号不显示、按钮只剩"登录 / 批量登录"、原生程序表保留
- **例外**：未设置完备的平台会被强制展开设置区 → **同时强制进入管理态**；该强制**写进会话变量**（之后切到正常平台仍保持管理态）
- **理由**：登录才是高频动作、管理是"设置好就不再进"的形态；模式不入档可避免"临时看一眼登录态"污染用户配置

## D-30 列定义属性化 + 默认值（`sortable` 默认开）（2026-10-06 用户定）

- **决策**：列的一切行为都由列定义属性驱动（`mandatory` / `pinned` / `sortable` / `sortType` / `loginOnly` / `remark: fixed` …），代码里**不再按 key 特判**；构造时补默认值 —— **`sortable` 默认 `true`**（"几乎每列都能排序"，不该要求每列重复声明），只有明确不合适的列写 `sortable: false`（当前：勾选框 / 头像）
- **三表差异**收口为 `rowKind`（`'acc'` / `'prog'`）+ `rowActionsOf(kind, mode, ctx)` 一处来源（名称单元格 / 右键菜单 / 批量按钮共用）
- **理由**：漏写属性导致过真实缺陷（"快捷键列不能排序"、"名称列点不动且没三角"是 `pinned` 与"不参与交互"混为一谈）

## D-31 列换序 = 两阶段，落点只认**初始槽位**（2026-10-06 用户设计）

- **决策**：阶段一只动列头那一行（列头临时绝对定位 + 显式像素 `left/width/height`），被拖列纯客户端位移跟手、其余列按实时顺序滑动，**tbody 不动**；阶段二松手写回顺序 + 持久化 + **重建列头** + 整表重刷
- **关键**：落点判定用**拖动开始时**的累积区间（初始槽位），**绝不用实时布局** —— 否则宽度悬殊时会"交换后指针又落在新区间"→ 无限横跳（用户实测并给出方案）；拖动触发是"移动 >4px"而不是"按住多久"（按住判定会把慢速点击误判成拖动、吞掉排序）
- **实现约束（踩了三次才定）**：阶段一的位移**只能用 `transform`**，元素**必须留在表格流里** ——
  改成绝对定位脱离流会牵动 `border-collapse` 折叠边框、把行高交给"测量值 vs 最小高度"去博弈，实测列头行被撑大几像素
- **阶段一的范围**：列头 + **该列所有内容单元格**一起位移（用户验收后保留），表头与内容始终对齐；松手才真正重排（重建列头 + 整表重刷）
- **约束**：固定列（勾选框/头像/名称）不可拖、但**照样可排序**

## D-32 PID / HWND 只存内存，不落配置文件（2026-10-06 用户定）

- **决策**：`pid` / `hwnd` 讲究实时性，写进文件下次读出来就是过时的 → 新增 `AccRuntimeStore`（内存 Map，生命周期随进程）；Java 侧读写全改内存并**顺手清掉配置里的历史遗留值**；前端用 `accRuntimeMap`（内存）+ 桥 `getAccRuntimeMap` + 事件推送刷新；两列只在登录态出现、**非必显**（默认显示、可自由隐藏、持久化）
- **属于个性化设置的照旧入档**：列显隐 / 列宽 / 列顺序 / "登录模式下隐藏列名"都写 `account_columns.<表id>`（用户 2026-10-06 明确纠正过我"别把个性化也当成不该入档的数据"）

## D-33 多开 = 查杀互斥体 + 降权启动（2026-10-07 用户定、已真机验证）

- **决策**：点"登录"（程序表那一行）= ①查杀该平台**全部**互斥体与文件锁（`mutex_handle_wildcards` + `config_handle_wildcards`）②以**普通用户权限**启动平台程序 → 每次点击都应新开一个登录窗口
- **实现**：`WinHandleOps`（纯 JNA：`NtQuerySystemInformation` 枚举句柄 → `DuplicateHandle` + `NtQueryObject` 取名字 → `DUPLICATE_CLOSE_SOURCE` 关闭，**不依赖外部 handle.exe**）；`SwNativeOps.createProcessWithoutAdmin` 按**自身是否管理员**分路（非管理员直接启动；管理员借 explorer 令牌；失败兜底 explorer 代启）
- **理由**：聊天软件以管理员身份启动会有一堆副作用；多开必须与"用户手动双击"同权限

## D-34 平台项点击策略：双击 = 启动，三击 = 取消（2026-10-07 用户定）

- **决策**：统一窗口 `CLICK_WINDOW_MS = 250`；单击当前平台 = 刷新；单击别的平台 = **等窗口后切换**（让双击来得及撤销它）；**双击 = 启动该平台程序且不切换**；**三击及以上 = 取消双击效果**
- **实现要点**：连击计数记在**模块变量**里，不能用 `e.detail`（切平台会重建侧栏 DOM，第二次点击的 `detail` 会从 1 重来 → "在 A 双击 B"永远识别不到）
- **代价（用户已知并接受）**：单击切平台有约 250ms 延迟

## D-35 通知：成功走 toast（自动淡出、无关闭按钮），失败才弹窗（2026-10-07 用户定）

- **决策**：`JFC.toastSuccess/Error` **去掉 × 按钮**、退场用 `toast-out` 渐隐（0.3s 后自动移除）；启动成功用 toast，**失败仍用 `JFC.modal`**（需要用户注意）
- **理由**：成功提示不该要用户手动关闭；失败是需要处置的信息

## D-36 程序表"登录"带 `× __` 实例数量输入框（2026-10-07 用户定）

- **决策**：`×` 是**独立静态前缀元素**（不在 input 里，所以删不掉），后面是可输入数字（**1 位、1~9**），空白灰显 `1`（字体字号与实际输入一致，只淡在颜色）；留空 = 开 1 个；样式与相邻按钮**同字号/同行高/同 padding**（高度自然一致）
- **后端**：`launchPlatformProgram(swId, count)` 循环 count 次「查杀 → 启动」（每个新实例都会建自己的互斥体，所以下一个必须再杀一次）；上限 20 保护

## D-37 "已查杀 PID"全局缓存（2026-10-07 用户提的方案，已实测）

- **决策**：全局共享 `KILLED_PID_AT`（`ConcurrentHashMap<pid, 时刻>`，**10s TTL**）；`killHandlesByName` 先剔除缓存命中的 PID（不进句柄枚举），关闭成功后登记
- **实测**：5 个各持互斥体的子进程 —— 第 1 次 931ms → 第 2 次 **0ms**（清缓存对照 254ms）
- **为什么带 TTL**：万一程序之后又重建互斥体（罕见），永久跳过会漏杀 → 表现为"点登录没开新窗口"
- **暂不上多线程**：`NtQueryObject` 对某些对象类型会阻塞，卡一次会拖住整批；缓存已消掉最大开销
