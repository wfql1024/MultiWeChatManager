# 待办

## 登录页面
- 占位状态，未实现

## 统计页面
- 占位状态，未实现

## 数据库层
- SQLite + DAO，未开始

## 平台图标提取
- ExtractIconExW 完善

## 二进制补丁引擎
- 从 Python 迁移，待评估合法性

## 安装版图标
- logo.ico 已生成，需确认 jpackage --icon 生效

## SSL 握手
- [x] 2026-10-04 定位并修复开发版根因：**Java 默认不使用 Windows 系统代理**，直连 GitHub raw 被 RST（`SSLHandshakeException: Remote host terminated the handshake`）→ 界面勾选"使用代理"即可（勾选/修改立即生效，见 AGENTS.md 十二）
- [ ] 待验证：打包版（jlink 精简运行时）是否同样只需勾选代理；若仍失败再检查 jlink 模块是否含 `java.net.http` / `jdk.crypto.ec`
## utils 包
- [x] StringUtils.java — 字符串工具
- [x] PathUtils.java — 路径工具
- [x] FileUtils.java — 文件工具（JsonUtils, DictUtils, MD5）
- [x] ImageUtils.java — 图像处理（downloadImage）
- [x] ColorUtils.java — 颜色工具
- [x] Parser.java — 逻辑表达式解析器
- [x] SystemUtils.java — 系统工具（全部 Stub）
- [ ] LoggerUtils.java — 日志工具（Printer, Logger）— 待移植

## Handle 操作
- [ ] SwNativeOps.findHandlesByPidsAndWildcards — Stub（需 JNA NtQuerySystemInformation）
- [ ] SwNativeOps.closeHandles — Stub（需 JNA DuplicateHandle）
- [ ] 调研结论：Java 无原生 Handle 操作，需仿照 pywinhandle.py 用 JNA 重写（约 300-500 行）
- [ ] 需扩展 NtdllExt 接口：NtQueryObject、NtDuplicateObject、NtClose

## AvatarUtils
- [x] `getAvatarDataUrl(sw, acc, avatarUrl)` — 本地文件 / URL 下载 / SVG 回退三路逻辑
- [x] `downloadAvatarAsync()` — 异步头像下载支持
- [x] CSS `.manage-account-avatar` `border-radius` 调整为 6px

## 上传日志功能
- 设置页"日志"子项已预留"上传日志"按钮（点击 toast「上传功能待实现」），需服务器后实现上传

## 登录状态 UI 接入
- 登录态数据已自动维护落库（进入平台页后台执行 `resolvePidAccountMap` → `updateAccLoginData`，SwAccData 含 pid/has_mutex/linked_acc），**界面未展示登录态**
- 后续加 UI：用 EventBus 流A 订阅或直接读 SwAccData 渲染

## 事件驱动定向刷新迁移（EventBus 流B）
- [x] toggle-hidden 已迁移（saveAccount 发布 AccountDataChangedEvent → 定向更新徽章/悬浮按钮，不整表重渲染）
- [x] 快捷键设置（2026-08-16 列定制会话）：快捷键列点击编辑，保存走 `saveAccount({hotkey})` → 流B 推送 → `onAccountChanged` 定向更新快捷键单元格
- [ ] 删除/批量隐藏/显示/头像设置等账号操作按同模式增量迁移：写库后发布 `AccountDataChangedEvent`，`onAccountChanged` 定向更新对应行/格

## 四表数据接入（2026-08-16 四表架构后）
- [x] 原生账号表已接数据：`getSwExistedAccounts(swId,'origin')`（数据目录子目录）
- [x] 共存账号表已接入（2026-10-04）：`getSwExistedAccounts(swId,'coexist')`；同时修复三个 Java 缺陷（配置键 `exe_wcs`→`executable_wildcards`、`accountOps` 传 null、`inst_path` 可能是目录）
- [ ] 原生程序表：平台主程序/共存程序列表（列：勾选框/名称/路径/状态）— 待定数据源
- [ ] 无效账号表：SwAccData 有记录但磁盘不存在的残留账号（列：勾选框/名称/ID/无效原因）— 待定判定逻辑

## 列表交互（2026-08-16 晚间已定稿）
- [x] 列宽自适应规则定稿：下限=列名宽+余量（展示名列=4字符+按钮占位），无上限；表格宽=列宽总和；固定列绝对固定
- [x] 自定义 overlay 滚动条体系（表内横向/账号区域纵向/设置区域纵向），JavaFX 原生滚动条弃用
- [x] 高度链锁定、整行悬浮高亮（JS 层）、分割线（--divider-solid）、空表行高/居左、列名（头像空/名称）
- [x] 规则文件统一 AGENTS.md（项目）+ ~/.dsh/AGENTS.md（全局）

## 文档欠账（2026-10-05，2026-10-06 已补）
- [x] `MEMORY/DEV_LOGS.MD` 补记本会话全部轮次：新增 **9 节（三十~三十八，146 行，0 删除）**，
      含早先欠的 flashTitle 那节；行尾统一为 LF（原文件是 19 CRLF + 932 LF 混杂，`core.autocrlf=true` 下 git diff 只看新增行）
- [x] 同步更新：项目 `AGENTS.md`（表格/账号数据/交互/离线验证约定）、`DECISIONS.MD`（D-10~D-28）、`FACTS.MD`（当前事实速查改为 10-06 快照）、
      `LESSONS.MD`（第十四节扩到 17 条 + 修掉"## 十一"重号）、全局 `~/.dsh/AGENTS.md`（3 条跨项目工作方式）
- [ ] **后续纪律**：每轮结束就同步 DEV_LOGS，不再积欠

## 删除/重置的语义与副作用（2026-10-05 已实现）
- [x] **批量删除只对失效账号生效**：**确认框照常弹**并在文案里说明"正常账号无法删除、将被跳过"；
      用户可继续确认，真正删除时只对失效账号动手（不静默不响应 —— 那样用户会疑惑为啥点不了）
- [x] **行右键菜单三项齐全（隐藏/重置/删除）**，不能做的**显示为禁用**；删除项对正常账号禁用并带悬停提示
- [x] **重置/删除都清除数据目录里的头像文件**：`AccInfoFuncCore.deleteAccountAvatarFiles()`
      （清所有图片、**保留非图片**、只删空目录）→ 接到 `JsBridge.resetAccount` / `deleteAccount`（探针 `AccFilesProbe` 8/8）
- [x] 顺手修掉 `ConfigManager.getInstance()` 的静态 `init` 误用（独立入口会拿到未初始化实例 → NPE，见 LESSONS 十六第 1 条）

## 三表名称列统一 + 程序名称链（2026-10-05 已实现）
- [x] **程序表名称列 === 账号表名称列**：改列 key 为 `display_name`、行 id 为 `origin_exe`、`showRowActions:false`（无悬浮按钮）。
      实测：15px / 字重 600 / 1 级纯白 / 可点击就地编辑 / 中英分段（`Round2Probe` 91 条断言）
- [x] **程序名称链**：原生账号 `origin_exe.remark` > 平台名称（本地 remark > 远程 alias > swId）
- [x] 所有"遍历账号"的地方排除 `origin_exe`（`getSwDetailData`/`getAccountList`/`getAllAccounts`/两处退化路径）
- [x] **清掉持久化的 `_alias`**（远程别称改为按需取；本地文件里那条会在下次保存时消失）
- [ ] 待你确认：程序表名称列点击编辑是否顺手（**编辑态是统一等宽的**，与账号表名称列一致 —— 因为 `<input>` 只能一种字体）

## 字体/字号（2026-10-05 已定）
- [x] **中文字体 = 微软雅黑**：名称列 / 昵称列 / 状态标签 / 悬浮按钮 / 批量按钮 / 列头
- [x] **名称列"中文雅黑 + 英文等宽"**：由 JS 拆段实现（`scriptSplitHtml` → `.cjk-run` / `.lat-run`）。
      实测本 WebKit 无法在一个元素内按字符集分字体（详见 FACTS / LESSONS 十四第 9 条）
- [x] **字号统一 14px**（列头 / 表内 / 标签 / 悬浮按钮 / 批量按钮 / 已选计数）；**名称列 15px**（大 1 号）
- [x] **ID 列回到等宽**（该列全是英文）
- [x] **编辑态字体**：已定 —— **`<input>` + 统一等宽**。曾试 `contenteditable` 做"编辑态中文雅黑+英文等宽"，
      实测在 JavaFX WebView 里**没法正常输入/修改** → 已回退（LESSONS 十四第 10 条）
- [x] **勾选框（真修，不用兜底）**：勾选态改成**一整块填充**（`border-color: transparent` + `background-clip: border-box`），
      尺寸/圆角 = 空框外沿（16px 含 1px 边框）。实测内部镂空 **0**、轮廓与空框一致（999 像素差 15 个抗锯齿）。
      ~~TOP 指令里的"填充边长 +1"是条件兜底，已修好故未启用~~
- [x] ~~程序表（原生程序）字体：名称列 15px + 中文雅黑/英文等宽（`td[data-col="name"]`）~~ → **已被上面"三表名称列统一"取代**
      （程序表名称列现在直接复用账号表的 `.manage-nickname-cell`，`data-col="name"` 与对应 CSS 已删除）
      同时保留：修掉我之前把昵称列的雅黑写进共用选择器组、导致程序表名称/版本/路径也变雅黑的回归
- [ ] 待你确认：**昵称列**目前整列雅黑（可能含中文）；**平台内ID / 最后登录账号**整列等宽。若哪列要改，说一声
- [ ] **抗锯齿**：`build.gradle.kts` 的 `run` 仍是 `-Dprism.lcdtext=false`（灰度 AA：边缘对比度 51.3→53.5、彩色边缘 97%→0%）→
      你比对后定**保留/去掉**；若保留，打包脚本 `scripts/package-exe.bat` 的 `--java-options` 也要加

## 平台功能与表观感（2026-10-05 已实现）
- [x] **三表"快捷键"列改为非必显**（列头菜单可隐藏）、默认显示；**原生程序表新增快捷键列**
- [x] **原生程序表的快捷键存 `LocalSwConfig.<sw>.hotkey`**（平台自身；不进 SwAccData，免得被当失效账号）
- [x] **版本号自动获取**：改为读 Windows 文件版本资源（与旧版 Python 同源），文件名解析作回退
- [x] **头像弹窗**：点头像 → 原图预览 + 「✎ 编辑」（文件选择器 → 转 JPEG 存本地头像文件）+「✕ 移除」（删本地头像文件）
- [x] **勾选框自绘**（原生控件在 WebView 里会先画方形再变圆角 → 闪烁）
- [x] **扫掉 8 处 `Map.of(..., null)` NPE**（详见 LESSONS 十六）
- [x] **头像弹窗居中**（标题与按钮都居中：`JFC.modal.custom({center:true})` + `.modal-card.center`）
- [x] **账号头像文字兜底**改成"名称末尾 4 个字符宽"（中文算 2 宽）；程序/侧栏兜底仍首字符
- [x] **勾选框**：圆角 4→2px（更"填满"）、勾按像素实测补偿居中（原偏上 1.25px）
- [ ] 待你确认：抖音聊天等程序的"文件版本"是垃圾值时改用产品版本（现已这么做）；若你希望**严格照抄文件版本**（哪怕显示 `29622.0.0.0`），说一声就改

## 账号管理功能（2026-10-05 已实现，用户已逐项验收）
- [x] **行内按钮按账号类型分档**：非失效账号 = 隐藏/显示 + 重置（**删除无意义**——磁盘上还在，下次加载照样出现）；失效账号 = 再加"删除"（移除记录节点 → 该行消失）
- [x] **重置语义**：清空 SwAccData 里该账号节点（保留空节点）→ 备注/快捷键/隐藏/关联账号全部抹掉，名称回退到自动识别；`ConfigManager.resetAccount` + `JsBridge.resetAccount`，成功后由前端整表重载（不做字段推送，避免半套真相）
- [x] **批量按钮**：隐藏/显示**合并为一个**（默认"隐藏"，选中项全为隐藏时才显示"显示"）；"批量删除"→"删除"；新增"重置"；删除/重置都走弹窗
- [x] **弹窗改用自建 HTML 模态**（`JFC.modal.confirm`）：JavaFX WebView 的 `window.confirm()` 恒返回 false，原删除确认是死的（详见 LESSONS 十四）
- [x] **名称列就地编辑备注**：预填 remark；输入框为空时灰字显示"名称回退链（去掉 remark）的结果"（即按空回车后会显示的名字）；Enter 提交 / Esc 放弃 / 点格外交付
- [x] **平台标题输入框**同理：placeholder 动态改为 `alias || swId`（不填备注时会显示的名称），不再写死"输入平台名称"
- [x] **快捷键录入改"松手即确认"**（详见 LESSONS 十五）：只有修饰键 / 多普通键 → 无效回退；Backspace 清空；Esc 放弃
- [x] **鼠标指针**：名称列/快捷键列 `text`；功能按钮/勾选框 `pointer`；其余列与占位列 `default`
- [x] **修掉"编辑态堵住界面"**：单元格 stopPropagation 监听累积 + mousedown 阶段重建整表（详见 LESSONS 十四）
- [x] **修掉"点框外编辑态不退出"**：`closest(元素)` 抛异常导致该处理静默失效（详见 LESSONS 十四第 5 条）；改 `cell.contains()`
- [x] **编辑态不会残留**：`_editFinish` 统一为"结束并还原单元格"（原先只清状态，开新编辑时旧格子永远留着输入框）
- [x] **进入编辑态清空多选**（轻量清空，不重建 DOM，免得把要编辑的格子变成脱离文档的旧节点）
- [x] **批量区加"取消"按钮**（在"已选 x 项"与批量按钮之间）；三个批量按钮横向内边距从 12px 收紧到 8px、组内间距 4px
- [x] **结束编辑的那一下点击不再顺手选中行**（一次性标记 + 400ms 兜底清除）
- [x] **双击/多击当前平台不再触发进度条**：`JFC.router.current() !== 'main'` 才导航，避免每次点击都重跑平台列表加载
- [x] 刷新按钮 2 秒不应期**置灰**（`router.refresh()` 返回"是否真的刷新"，Java 据此灰 2 秒）

## 统一通知通道（toast）— 用户裁定"以后再说"（2026-10-05）
- [ ] **暂缓**：目前还没有"必须通知失败"的场景；删除账号等失败提示待定，后续开发再推进
- 已有基础：`app.js` 的 `JFC.toastError/toastSuccess`（右下角、自动消失、✕ 可关）；将来改造方向 = 常驻（手动叉掉）+ 可复制文本 + 只报流程失败

## 刷新入口（2026-10-05 已实现）
- [x] 标题栏新增"刷新"按钮（浮窗按钮左侧），刷新当前页（识别当前页面：平台页/设置页；无刷新入口的页退回导航）
- [x] **图标用矢量 SVG path**，不用字体字形（字形观感依赖系统字体回退，难看且不可控）：Lucide `rotate-cw`（MIT，24×24、stroke 2、圆头）→ JavaFX `SVGPath` 绘制（`MainWindow.makeSvgTitleBtn`），颜色走 CSS `.title-bar-icon { -fx-stroke }`，深浅主题各一套
- [x] **2 秒不应期防连点**：闸门放在唯一入口 `JFC.router.refresh()`，刷新按钮与"再点当前平台"共用同一道闸（实测：1.1s 时被挡、3.2s 时放行）
- [x] 平台项点击策略：点别的平台 = **立即切换**；点当前平台 = **单击刷新**（等 250ms 确认无后续点击）；**双击/多击 = 不响应**（`onPlatformMultiClick()` 路径预留，目前空实现）
- [x] 页面进度条：内容区顶部 2px 主题色（`--color-primary`）小横条 `#page-progress` + `JFC.progress`（不定长滑动、最短显示 400ms），平台页/设置页加载时显示
- [x] `JFC.router.currentPage` 改为以 DOM（`.page.active`）为准（原先硬编码 `'login'`，会导致刷新跳错页面）

---




# 待推进（自 AGENTS.md 第八节迁入，2026-10-05）

见 `MEMORY/TODOS.MD`：

- 登录页面、统计页面 — 占位未实现
- 数据库层（SQLite + DAO）— 未开始
- 平台图标提取 — ExtractIconExW 完善
- 二进制补丁引擎 — 从 Python 迁移，待评估合法性
- SSL 握手 — 打包版 handshake_failure
- LoggerUtils.java — 待移植
- Handle 操作 — JNA 仿照 pywinhandle.py 重写约 300-500 行
- 登录状态 UI 接入 — 数据已自动维护落库（EventBus 流A），界面未展示
- 其余账号操作的事件驱动迁移 — 删除/批量/头像/快捷键等按 EventBus 流B 增量迁移

---
