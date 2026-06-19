# CLAUDE.md — JhiFengMultiChat（极峰多聊）

> 最后更新: 2026-06-20  
> 当前阶段: Phase 0 最小原型完成

---

## 一、项目身份

- **项目名**: JhiFengMultiChat（极峰多聊）
- **定位**: Windows 桌面端多平台聊天软件管理器
- **功能**: 微信/企业微信/QQ/TIM/钉钉/飞书多账号管理 — 多开、防撤回、一键登录、窗口切换
- **Python 源码**: `legacy_python/`（Python 分支完整源码，不在版本控制中，仅本地参考）
- **工作目录**: `D:\SpaceDev\MyProj\JhiFengMultiChat`
- **远端**: `main` 分支

---

## 二、当前技术栈

| 层面 | 选型 |
|------|------|
| JDK | 17 LTS (`D:\SpaceDev\softwareDev\SDKs\Java\jdk-17.0.2`) |
| 构建 | Gradle 8.8 (Kotlin DSL) |
| UI | JavaFX 17, `StageStyle.TRANSPARENT` |
| 渲染 | WebView 内嵌 HTML/CSS/JS |
| JSON | Jackson 2.16 |
| Windows API | JNA (待后续 Phase 实现) |
| 图标 | MCP 服务器 `mcp-universal-icons` + `icons-mcp` 已安装（`.mcp.json` 项目配置） |

---

## 三、当前项目结构

```
├── build.gradle.kts              # JavaFX + Web 模块 + Jackson
├── settings.gradle.kts
├── run.bat                       # 一键启动脚本
├── .mcp.json                     # MCP 图标服务器配置
├── logo.png                      # 应用图标
│
└── src/main/
    ├── java/com/jfmultichat/
    │   ├── Launcher.java         # 入口（规避 JavaFX 模块限制）
    │   ├── MainApp.java          # Application 单例，窗口生命周期
    │   ├── bridge/
    │   │   └── JsBridge.java     # JS↔Java 双向通信
    │   ├── setting/
    │   │   ├── AbsSetting.java   # JSON 配置抽象基类（对应 Python AbsSetting）
    │   │   └── RemoteGlobalSetting.java  # 远程全局配置单例
    │   ├── model/
    │   │   ├── AboutInfo.java    # 关于页数据 (record)
    │   │   ├── LinkEntry.java    # 链接条目
    │   │   ├── ReferenceEntry.java
    │   │   └── SponsorEntry.java
    │   └── ui/
    │       ├── MainWindow.java   # 主窗口：标题栏 + WebView + 缩放手柄
    │       ├── FloatingSidebar.java  # 浮动侧栏
    │       └── SampleWindow.java # 示例窗口
    │
    └── resources/
        ├── css/
        │   ├── main.css          # 标题栏样式 (深色)
        │   └── main-light.css    # 标题栏样式 (浅色)
        ├── icons/logo.png
        ├── data/remote_global_v1.json  # 远程全局配置种子数据
        └── web/
            ├── index.html        # 双栏主页面
            ├── css/
            │   ├── theme.css     # CSS 变量 + 浅/深/Auto 三主题
            │   └── main.css      # 布局样式
            ├── icons/logo.png
            └── js/
                ├── bridge.js     # JS→Java 桥封装
                ├── icons.js      # SVG 图标定义
                ├── app.js        # 路由 + 初始化
                ├── components/
                │   └── nav-sidebar.js  # 导航侧栏 (hover 延迟展开)
                └── pages/
                    └── settings.js  # 设置页 (外观/更新/鸣谢/关于)
```

---

## 四、Phase 0 已实现功能

### 窗口架构
- **StackPane 根布局**: `contentBox(VBox:标题栏+WebView)` + `resizePane(8个透明Region缩放手柄)`
- **自制标题栏**: logo(动态对齐侧栏图标) + ☰ ─ ☐ ✕ 四按钮
- **圆角裁剪**: `Rectangle` clip with `ArcWidth/Height=24`，最大化时归零
- **边缘缩放**: 8 个透明 `Region` 节点（四边四角），`setOnMousePressed/Dragged` 直接操作 stage
- **最大化不遮任务栏**: `Screen.getPrimary().getVisualBounds()`
- **最大化时隐藏缩放手柄**: `resizePane.setVisible(false)`
- **双击标题栏切换最大化**
- **最大化拖拽恢复**: 移动超过 4px 阈值才恢复窗口

### WebView 内嵌
- `JsBridge` 通过 `JSObject.setMember("javaObject", bridge)` 注入
- `addEventFilter` + webView 级 filter 处理拖拽事件
- 外部链接拦截 → `Desktop.getDesktop().browse()` 浏览器打开
- `suppressLinkIntercept` 标志防止 baseUrl 重载时二次触发

### 左导航侧栏
- hover 300ms 后展开（64px→200px），图标 `position:absolute` 绝对定锚不动
- 移除顶部留白和分割线，底部留白 `border-radius` 等宽
- 左侧 `::before` 伪元素激活指示条
- SVG 图标 (`stroke="currentColor"`)

### 设置页
- 双栏独立滚动（隐藏滚动条，hover 时浮现）
- 外观(主题切换) / 更新 / 鸣谢 / 关于
- 主题: CSS 变量 `data-theme="dark|light|auto"`，JS 点击切换 → JsBridge 通知 Java 切换标题栏 CSS

### 数据层
- `AbsSetting` Jackson-based JSON 读取
- `RemoteGlobalSetting` 类型化访问 `AboutInfo`
- 数据模型: `AboutInfo`, `LinkEntry`, `ReferenceEntry`, `SponsorEntry` (records)

---

## 五、关键技术教训

1. **WebView 会拦截鼠标事件** — `scene.setOnMouse*` 不可靠，需 `addEventFilter`（捕获阶段）+ webView 级 filter 双保险。边缘缩放终极方案：用透明 `Region` 节点盖在 WebView 之上，彻底绕过。
2. **`root` 引用时序** — `buildResizeHandles()` 绑定了 `root.widthProperty()`，必须先创建 `root` 再调用。
3. **WebView 的 `load()` 会触发 location listener** — 外链拦截后 `load(baseUrl)` 会导致二次触发。用 `suppressLinkIntercept` 标志跳过。
4. **maximized 拖拽不要立即恢复** — 按下时只记录位置，拖拽超过阈值（DRAG_THRESHOLD=4）才恢复 + 跟随鼠标。
5. **`isDragging` 标志** — 非标题栏区域按下时不设 `isDragging=true`，防止窗口闪移到上次拖拽位置。
6. **UTF-8 BOM** — Write 工具保存的 `.bat` 文件可能含 BOM 导致 cmd 报错。改用 Bash `cat >` 写。
7. **Java 方法签名歧义** — `getString(String... path)` 和 `getString(String defaultVal, String... path)` 在单参数调用时歧义。改为 `getStringOr(defaultVal, ...path)`。

---

## 六、运行命令

```bash
# 双击 run.bat 或
cd D:\SpaceDev\MyProj\JhiFengMultiChat
export JAVA_HOME="/d/SpaceDev/softwareDev/SDKs/Java/jdk-17.0.2"
export PATH="/d/SpaceDev/softwareDev/SDKs/gradle-8.8/bin:$PATH"
gradle run --no-daemon
```

---

## 七、待推进 (后续 Phase)

1. Native 层 JNA 真实现（进程/窗口/注册表）
2. 登录页 / 管理页 / 统计页功能实现
3. `RemoteGlobalSetting` 数据接入 HTML 关于页（JsBridge 动态渲染）
4. 数据库层 SQLite + DAO
5. 远程配置加密下载（端口从 Python AppFuncCore）
6. 二进制补丁引擎迁移（待评估合法性）
