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
