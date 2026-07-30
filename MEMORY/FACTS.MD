# 事实

## 当前阶段
- Phase 1.10 — page-main 替代 page-manage，旧代码剥离至 .old/，侧栏精简

## 打包路径
- 免安装版: `build/portable/JhiFengMultiChat/JhiFengMultiChat.exe`
- 安装版: `build/exe/JhiFengMultiChat-{version}.exe`
- 总大小: ~154MB（含 JRE + JavaFX WebView）

## 脚本位置
- `scripts/run.bat` — 开发运行
- `scripts/analyze.bat` — 依赖分析
- `scripts/package.bat` — 基础打包 (distZip)
- `scripts/package-exe.bat` — EXE 打包 (jlink + jpackage)

## 旧代码位置
- `.old/manage.js` — 原管理页 JS

## 版本号
- `AppVersion.java`: `"4.0.0.7000"` — 唯一来源
- `build.gradle.kts`: `"4.0.0"` — 同步
- 打包安装版用 `4.0.0`（WiX 限制 3 段），便携版用 `4.0.0.7000`

## JavaFX 依赖路径
- Gradle 缓存: `C:\Users\25359\.gradle\caches\modules-2\files-2.1\org.openjfx\`
- 版本: 17.0.2
- 模块: base, controls, graphics, web, media

## WiX Toolset
- 路径: `C:\Program Files (x86)\WiX Toolset v3.14\bin`
- 版本: 3.14.1.8722

## 数据存储规范（骨架事实）

### 用户数据目录格式
%APPDATA%/JhiFengMultiChat/{version}/
├── RootConfig.json               # 锚点文件，永不移动
├── UserFiles/
│   ├── LocalGlobalConfig.json    # 软件偏好
│   ├── LocalSwConfig.json        # 各平台设置
│   ├── SwAccData.json            # 账号数据
│   ├── SwCache.json              # 适配缓存
│   ├── RemoteGlobalConfig.json   # 远程全局配置缓存
│   └── RemoteSwConfig.json       # 远程平台配置缓存
└── DevUserFiles/                 # 开发版（--dev）

### RootConfig.json 字段示例
{ "user_data_path": "...", ... }

## 配置层架构

接口层次：IConfigStore → JsonConfigStore → ConfigManager

未来扩展：如需更换存储格式，只需实现新的 IConfigStore

## swcore 包关键细节
### SwConfigAccessor.Provider 模式：通过 Provider 注入，BridgeConfigProvider 适配 ConfigManager
### 六级路径探测：内存映射正则 > 注册表 > 猜测 > 进程 > 其他SW > DLL遍历

### 运行命令速查
- 开发运行: gradle run --no-daemon --args="--dev"
- 仅编译: gradle compileJava --no-daemon
