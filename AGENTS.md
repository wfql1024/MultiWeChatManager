# AGENTS.md — JhiFengMultiChat（极峰多聊）

> **本文件是"热记忆"**：只写**每次动手都必须遵守/使用**的东西（规矩、命令、硬约束、验证）。
> 现在是什么样 → `MEMORY/facts.md`｜为什么这么定 → `MEMORY/decisions.md`｜踩过的坑 → `MEMORY/lessons.md`｜过程与证据 → `MEMORY/dev_logs.md`｜架构细节 → `docs/project_structure.md`。
> ⚠️ **本文件与 `MEMORY/` 的内容规范严格遵循顶级 `~/.dsh/AGENTS.md`**（跨项目记忆规范）——不在此重复其内容。

**一句话**：Windows 桌面端多平台聊天管理器（Java 17 + JavaFX 17，界面由内嵌 WebView 渲染 HTML/CSS/JS）。

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

> 其余不变量（PID/HWND 只存内存、表格列规则、"创建实例必查杀"、登录失败不中断整批…）都在 [`MEMORY/facts.md`](MEMORY/facts.md) 对应功能块里。

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
