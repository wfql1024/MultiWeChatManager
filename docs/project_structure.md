# JhiFengMultiChat 项目结构文档

> 最后更新: 2026-07-31

---

## 一、根目录概述

```
JhiFengMultiChat/
├── build.gradle.kts              # Gradle 构建脚本 (Kotlin DSL)
├── settings.gradle.kts           # Gradle 设置文件
├── run.bat                       # 运行脚本
├── logo.ico                      # 应用图标 (ICO 格式)
├── logo.png                      # 应用图标 (PNG 格式)
├── CLAUDE.md                     # 项目主文档
├── MEMORY/                       # 记忆系统文档目录
│   ├── MEMORY.md                 # 索引与摘要
│   ├── DECISIONS.MD              # 决策记录
│   ├── DEV_LOGS.MD               # 开发过程日志
│   ├── FACTS.MD                  # 事实摘要
│   └── TODOS.MD                  # 待办列表
├── .old/                         # 废弃代码归档
│   └── manage.js                 # 原管理页 JS
├.src/                            # 源码目录
├─ resources/                     # 资源文件目录
├─ scripts/                       # 打包脚本目录
├─ .claude/                       # Claude 配置目录
├─ .gradle/                       # Gradle 缓存目录
├─ .git/                          # Git 版本控制目录
├─ bin/                           # 编译输出目录
├─ build/                         # 构建输出目录
├─ storage/                       # 数据存储目录
└─ legacy_python/                 # Python 旧版参考 (不在版本控制中)
```

---

## 二、Java 源码结构 (`src/main/java/com/jfmultichat/`)

```
com/jfmultichat/
├── Launcher.java                    # 程序入口点
├── MainApp.java                     # JavaFX Application 主类
├── config/                          # 配置管理子系统
│   ├── AppEnv.java                  # 运行环境判断 (DEV/TEST/PROD)
│   ├── AppPaths.java                # 路径规范定义
│   ├── AppVersion.java              # 版本号与元数据 (唯一来源)
│   ├── IConfigStore.java            # 配置存储接口
│   ├── JsonConfigStore.java         # JSON 配置存储基类 (Jackson)
│   ├── ConfigManager.java           # 配置管理器单例
│   ├── CryptoUtils.java             # AES-CBC 加密解密工具
│   ├── RemoteConfigFetcher.java     # 远程配置下载与缓存
│   └── RootConfig.java              # RootConfig.json POJO
├── bridge/                          # JavaScript ↔ Java 桥接
│   └── JsBridge.java                # JS 调用 Java 的入口 + 异步回调机制
├── swcore/                          # Windows 探测与补丁引擎核心
│   ├── SwCoreConstants.java         # 常量统一定义 (RemoteSwKey/AccKeys)
│   ├── SwHexUtils.java              # 特征码扫描 (hex/通配符/截断)
│   ├── SwRuleResolver.java          # 规则解析 (simple/custom/jmp_offset/relation)
│   ├── SwAdapterChecker.java        # 补丁状态检测
│   ├── SwConfigAccessor.java        # 配置读取包装器 (Provider 注入)
│   ├── SwPathResolver.java          # 路径解析函数
│   ├── SwVersionHelper.java         # 版本计算工具
│   ├── SwRectCalculator.java        # 截图区域计算
│   ├── SwPidMutexOps.java           # PID-互斥体配置操作
│   ├── SwAccountOps.java            # 账号列表与多开检测
│   ├── SwOperatorCore.java          # DLL切换/共存/登录/备份
│   ├── SwAvatarOps.java             # 头像截取与缓存
│   ├── SwInfoFuncCore.java          # Facade 入口
│   ├── SwPathDetective.java         # 六级路径探测策略 (并发执行)
│   └── SwNativeOps.java             # JNA 原生操作封装 + MemoryMapIterator
├── setting/                         # 设置项抽象基类
│   ├── AbsSetting.java              # JSON 配置基类 (SLF4J 日志)
│   └── RemoteGlobalSetting.java     # 远程全局配置 (回退 classpath 种子)
├── model/                           # 数据模型 (用于 About/Reference/Sponsor 页面)
│   ├── AboutInfo.java               # 关于页面数据模型
│   ├── LinkEntry.java               # 链接条目
│   ├── ReferenceEntry.java          # 引用条目
│   └── SponsorEntry.java            # 赞助条目
├── ui/                              # UI 窗口管理
│   ├── MainWindow.java              # 主窗口 (透明 Region + WebView + 缩放手柄)
│   ├── FloatingSidebar.java         # 浮动侧栏组件
│   └── SampleWindow.java            # 示例窗口类
└── utils/                           # 工具类
    └── AvatarUtils.java             # 头像获取工具类 (本地/URL/SVG 三路回退)
```

---

## 三、资源文件结构 (`src/main/resources/`)

```
resources/
├── logback.xml                      # SLF4J + Logback 日志配置
├── css/                             # JavaFX 桌面 CSS
│   ├── main.css                     # 主题样式 (深色)
│   ├── main-light.css               # 主题样式 (浅色)
│   └── sidebar.css                  # 侧栏专用样式
├── data/                            # 种子数据
│   └── remote_global_v1.json        # 远程配置默认种子
├── icons/                           # 应用图标
│   └── logo.png
└── web/                             # Web 前端 (HTML/CSS/JS)
    ├── index.html                   # 主页面入口
    ├── css/                         # Web CSS
    │   ├── main.css                 # 页面主样式
    │   └── theme.css                # 主题样式
    └── js/                          # JavaScript
        ├── app.js                   # 路由 + toast + 远程配置兜底
        ├── bridge.js                # JS↔Java 桥 (含异步回调 _handleAsync)
        ├── icons.js                 # SVG 图标
        ├── components/nav-sidebar.js # 侧栏导航组件
        └── pages/                   # 页面模块
            ├── main.js              # 主页面逻辑 (从 manage.js 复制)
            └── settings.js         # 设置页逻辑
```

---

## 四、用户数据存储路径

```
%APPDATA%/JhiFengMultiChat/{version}/
├── RootConfig.json              # 锚点配置 (代理/URL/数据目录, 永不移动)
├── UserFiles/                   # 正式版数据存储
│   ├── LocalGlobalConfig.json   # 软件偏好 (主题/窗帘状态等)
│   ├── LocalSwConfig.json       # 各平台安装配置 ({swId}: {inst_path, remark})
│   ├── SwAccData.json           # 账号数据 ({sw_id}: [{acc_id, ...}])
│   ├── SwCache.json             # 适配缓存
│   ├── RemoteGlobalConfig.json  # 远程全局配置缓存
│   └── RemoteSwConfig.json      # 远程平台配置缓存
│   └── logs/                    # 运行时日志
└── DevUserFiles/                # 开发版 (--dev) 数据存储 (同结构)
```

---

## 五、关键架构特性

### 1. 配置层架构 (三层抽象)
```
IConfigStore (接口)
  ├── getData()/setData()/reload()/save()
  ├── getSet/remove/have()/ensure()
  ↓
JsonConfigStore (实现 — Jackson ObjectNode)
  ├── getSubNode()/setSubNode()/removeSubNode()
  ├── loadFromJson()/toJson()/deepCopy()
  ↓
ConfigManager (单例统筹者)
  ├── getRootConfig() → RootConfig POJO
  ├── getGlobalConfig() → LocalGlobalConfig.json ObjectNode
  ├── getSwConfig(swId) → LocalSwConfig.json.{swId}
  ├── getRemoteGlobal() → RemoteGlobalConfig.json ObjectNode
  └── ... (访问所有 6 个 ConfigStore)
```

### 2. JS↔Java 异步架构
```
JS 调用 void Java 方法 → 立刻返回
               ↓
     ExecutorService 后台线程
     · HTTP 下载 · AES 解密 · JSON 解析
               ↓
     Platform.runLater → scriptExecutor
     → JFC.bridge._handleAsync(type, cbId, jsonStr)
               ↓
     JS 回调更新 DOM
```

### 3. 六级路径探测策略 (并发执行)
内存映射正则 > 注册表 > 猜测 > 进程 > 其他SW > DLL遍历

---

## 六、相关文档索引

| 文档 | 内容描述 |
|------|----------|
| `CLAUDE.md` | 项目总览 + 关键技术教训 (44条) |
| `MEMORY/MEMORY.md` | 各记忆文档索引摘要 |
| `MEMORY/DECISIONS.MD` | 关键决策记录 (page-main/头像重构等) |
| `MEMORY/DEV_LOGS.MD` | 开发过程笔记 (页架构迁移细节/经验教训) |
| `MEMORY/FACTS.MD` | 当前阶段事实汇总 |
| `MEMORY/TODOS.MD` | 待办任务清单 |
| `HANDOFF.md` | 交接文档 |
| `remote_sw_structure.md` | 远程结构定义 |
| `logic_filter_rules.md` | 逻辑过滤规则 |
| `handle-shape-preview.html` | Handle 形状预览 |
