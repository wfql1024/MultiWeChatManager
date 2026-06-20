# HANDOFF.md — 新同事接手指南

> 写给接手此项目的下一个开发者/模型

---

## 启动前必读

1. **先读 `CLAUDE.md`** — 里面包含了完整的项目结构、技术栈、数据存储路径、异步架构、已知问题。
2. 工作目录是 `D:\SpaceDev\MyProj\JhiFengMultiChat`
3. JDK 17 在 `D:\SpaceDev\softwareDev\SDKs\Java\jdk-17.0.2`
4. Gradle 8.8 在 `D:\SpaceDev\softwareDev\SDKs\gradle-8.8`

---

## 当前阶段

Phase 0 — 配置管理 + 设置页 UI 已完成。程序可以启动，主窗口 + WebView + 五个设置页（外观/配置/更新/鸣谢/关于）均可正常工作。

---

## 最高优先级规则

1. **后台线程** — 任何网络操作（HTTP下载、解密、JSON解析）必须用 `JsBridge` 的 `*Async` 方法，走 `ExecutorService` 线程池 → `Platform.runLater` → `executeScript` 回调 JS。绝不能用 `setTimeout` 模拟异步。
2. **字号** — 用户喜欢大字号，所有字体 +2px。不要擅自改小。
3. **编译直接执行** — `gradle build` 不用问，遇到 `Failed to clean up stale outputs` 就 `taskkill //F //IM java.exe && rm -rf build && gradle build`。
4. **不要自作主张** — 用户的需求非常具体，按照他说的做，不要猜测和发挥。不懂就问，该问的一定要问。

---

## 目前最可能接手的工作

1. **自动滚动修复** — 鸣谢页赞助列表和技术参考的自动滚动在顶部不会往下滚。当前实现使用了 `requestAnimationFrame` 双缓冲 + `setTimeout` 调度。可能是 `scrollHeight` 在内容异步加载后获取为 0 的问题。
2. **远程配置 URL** — 四个内置 URL 指向 `main` 分支但文件未上传（404）。用户会手动添加 `python` 分支地址。
3. **下一页 Phase** — 登录页、管理页、统计页的功能实现。参考 `legacy_python/` 中的旧版 Python 代码。
4. **JNA 集成** — 进程管理、窗口句柄操作、注册表读写。

---

## 代码风格注意事项

- Java: 方法名/变量名统一使用 `Sw` 术语（Software 缩写），不用 `Platform`
- JS: 全局命名空间 `JFC`，桥接方法通过 `JFC.bridge.call*` 调用
- CSS: 使用 CSS 变量（定义在 `theme.css`），三个主题 dark/light/auto
- 字体规范: `--font-h1: 20px`, `--font-h2: 17px`, `--font-body: 15px`
- 括号: 用户目录用 `（默认）`（中文全角），URL列表用 `(默认)`（英文半角）
- "数据目录"/"远程平台"/"远程全局" 三个标签必须用同一个 CSS class (`config-subtitle`)

---

## 调试技巧

1. 日志在 `%APPDATA%/JhiFengMultiChat/4.0.0.7000/user_files/logs/`
2. 开发模式启动: `gradle run --no-daemon --args="--dev"`（使用 `dev_user_files/` 隔离数据）
3. 配置数据在 `%APPDATA%/JhiFengMultiChat/4.0.0.7000/user_files/` 下，可以直接编辑 JSON 文件来模拟各种状态

---

## 旧版 Python 参考

`legacy_python/` 目录包含了完整的老版 Python 项目，但是：
- 不在版本控制中（`.gitignore` 排除）
- 部分 `.py` 源码已丢失（如 `utils/encoding_utils.py`），只剩 `.pyc` 编译文件
- 用户数据在 `legacy_python/user_files/` 中可参考数据结构
- 业务逻辑参考优先级最高 — 如果新版行为与旧版不一致，以旧版为准
