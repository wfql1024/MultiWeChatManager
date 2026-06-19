# Vue 3 + Tauri 2 + Spring Boot 混合方案（已废弃）

> **归档日期**: 2026-06-19  
> **废弃原因**: 暂时不使用 Vue 和 Tauri 方案，当前 Phase 0 采用 JavaFX + WebView 架构

---

## 方案概述

这是一个 Vue 3 + Vite + Tauri 2 + Spring Boot 的混合桌面应用方案：
- **前端**: Vue 3 (Composition API) + Vite 5 + Axios
- **桌面壳**: Tauri 2 (Rust)，提供原生窗口和系统 API
- **后端**: Spring Boot 3 (Java)，提供 REST API
- **通信**: 前端通过 Vite 代理 `/api` → `localhost:8080` → Spring Boot 后端

## 文件清单与职责

### 前端 (Vue 3 + Vite)

| 文件 | 职责 |
|------|------|
| `index.html` | Vite 入口 HTML，挂载 `#app` 节点 |
| `src/main.js` | Vue 3 应用入口，`createApp(App).mount('#app')` |
| `src/App.vue` | 根组件 — 含一个测试按钮"创建随机文件夹"，通过 Axios 调用 `/api/create-random-folder` |
| `package.json` | npm 依赖：vue 3.4, axios 1.5, vite 5, @tauri-apps/api 2.8, @tauri-apps/cli 2.8, @vitejs/plugin-vue 5 |
| `package-lock.json` | npm 锁定版本文件 |
| `vite.config.js` | Vite 配置：启用 Vue 插件 + 开发代理 `/api` → `http://localhost:8080` |

### Spring Boot 后端

| 文件 | 职责 |
|------|------|
| `src/main/java/.../JhiFengMultiChatBackendApplication.java` | Spring Boot 启动类 |
| `src/main/java/.../controller/FileController.java` | REST Controller — `/create-random-folder` 端点，演示 JNA 调用 Windows Shell API (`SHGetKnownFolderPath`) 获取桌面路径并创建随机文件夹 |
| `src/main/java/.../config/Knife4jConfiguration.java` | Knife4j (Swagger) API 文档配置 |
| `src/main/java/.../util/Shell32Flags.java` | JNA Shell32 标志常量定义 |
| `src/main/resources/application.properties` | Spring Boot 配置：端口 8080，应用名 JhiFengMultiChatBackend |
| `src/test/java/WindowControlTests.java` | 窗口控制测试 |
| `pom.xml` | Maven 构建配置（Spring Boot 后端），含 JNA、Spring Boot Starter Web、Knife4j 等依赖 |

### Tauri 桌面壳 (Rust)

| 文件 | 职责 |
|------|------|
| `src-tauri/Cargo.toml` | Rust 项目配置：依赖 tauri 2.8.5, tauri-plugin-log 2, serde, serde_json |
| `src-tauri/Cargo.lock` | Rust 依赖锁定文件 |
| `src-tauri/src/main.rs` | Rust 入口 — 调用 `app_lib::run()`，Windows 下隐藏控制台窗口 |
| `src-tauri/src/lib.rs` | Tauri Builder — 初始化插件（日志），运行 Tauri 应用 |
| `src-tauri/build.rs` | Tauri 构建脚本 |
| `src-tauri/tauri.conf.json` | Tauri 配置：窗口 800×600，前端 dev URL `localhost:5173`，构建产物 `../frontend/dist` |
| `src-tauri/capabilities/default.json` | Tauri 2 权限声明：`core:default` |
| `src-tauri/icons/` | Tauri 应用图标（多尺寸 PNG/ICO/ICNS） |
| `src-tauri/.gitignore` | 忽略 `/target` |

## 运行方式（原计划）

```bash
# 1. 启动 Spring Boot 后端 (Java 17 + Gradle/Maven)
cd src
./gradlew bootRun          # 或 mvn spring-boot:run
# 监听 localhost:8080

# 2. 启动 Vue 前端开发服务器
npm run dev                 # 即 vite --port 5173
# 监听 localhost:5173，API 请求代理到 8080

# 3. 启动 Tauri 桌面壳（开发模式）
npm run tauri:dev           # 即 tauri dev
# 打开原生窗口，内嵌 localhost:5173 的 Vue 页面

# 4. 生产构建
npm run tauri:build         # 即 tauri build
# 生成 Windows .msi / .nsis 安装包
```

## 废弃原因

1. 项目决定暂时不采用 Vue 前端框架，改用 JavaFX 内嵌 WebView + 原生 HTML/CSS/JS
2. Tauri 桌面壳被 JavaFX Stage 直接替代
3. Spring Boot REST API 方案暂时搁置，当前采用 JS Bridge (`netscape.javascript.JSObject`) 直调 Java 方法
4. 当前 `main` 分支的 Phase 0 已基于 JavaFX + JNA + SQLite 完成窗口框架

## 可复用内容

- `FileController.java` 中的 JNA `SHGetKnownFolderPath` / `CoInitializeEx` 用法可作 JNA 参考
- `Knife4jConfiguration.java` 可在后续启用 REST API 时复用
- Tauri 图标资源 (`src-tauri/icons/`) 可在打包阶段复用
- `vite.config.js` 中的 Vite 代理配置模式可作参考
