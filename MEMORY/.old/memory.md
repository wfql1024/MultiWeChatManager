# MEMORY — 索引与摘要

> 最后更新: 2026-10-07

## 决策点
- [[DECISIONS.MD#page-main 复制迁移]] — 完整复制 DOM+JS，不动旧文件
- [[DECISIONS.MD#侧栏精简]] — 移除登录/管理，仅平台列表 + 统计 + 设置
- [[DECISIONS.MD#旧代码剥离]] — manage.js → .old/
- [[DECISIONS.MD#版本号管理]] — AppVersion.java 唯一来源
- [[DECISIONS.MD#打包方案]] — jlink + jpackage，便携版 + 安装版
- [[DECISIONS.MD#常量按包分离]] — config 包用 AppCoreConstants，swcore 包用 SwCoreConstants
- [[DECISIONS.MD#头像重构]] — AvatarUtils 统一头像获取逻辑（2026-07-30）
- [[DECISIONS.MD#账号列表来源 = 磁盘扫描]] — getSwExistedAccounts 接入磁盘扫描来源（2026-07-31）
- [[DECISIONS.MD#头像接入 acccore/AvatarUtils 管道]] — 异步逐行更新头像（2026-07-31）
- [[DECISIONS.MD#日志目录固定根配置位置]] — AppPaths.getLogsDir() 不随用户配置（2026-07-31）
- [[DECISIONS.MD#legacy_python 保持忽略]] — 不入版本管理（2026-07-31 确认）
- [[DECISIONS.MD#后台会话关闭 worktree 隔离]] — bgIsolation none（2026-07-31）
- [[DECISIONS.MD#EventBus 事件机制]] — 数据更新↔UI刷新解耦，流A自动维护/流B定向刷新（2026-08-01）
- [[DECISIONS.MD#账号列表列定制]] — 7列结构/列头右键菜单/列宽拖拽/快捷键编辑/悬浮交互（2026-08-16）
- [[DECISIONS.MD#四表架构与可复用组件]] — AccountTable 组件/四表分类/标题行/固定列/快捷键修复（2026-08-16 第二轮）
- [[DECISIONS.MD#滚动条体系与布局锁定]] — 自定义滚动条/高度链/列宽规则/整行高亮/分割线/AGENTS.md（2026-08-16 晚间）
- [[DECISIONS.MD#开发者工具源集与加密单一实现]] — src/tools 源集 + encryptRemoteConfigs 任务，复用 CryptoUtils（2026-10-04）
- **[[DECISIONS.MD#决策记录（2026-10-05 晚 ~ 10-06 凌晨 汇总）]] — D-10 ~ D-28（2026-10-05 晚 ~ 10-06）**，其中重点：
  - [[DECISIONS.MD#D-18 中文字体 = 微软雅黑；字号统一 14px、名称列 15px；中英字体由 JS 拆段]]
  - [[DECISIONS.MD#D-20 表格文字三级色（`--text-level1/2/3`）]]
  - [[DECISIONS.MD#D-21 三张表的名称列完全统一]] ｜ [[DECISIONS.MD#D-22 原生程序名称链 = `origin_exe.remark` > 平台名称；`origin_exe` 不是账号]]
  - [[DECISIONS.MD#D-24 删除 / 重置的语义与副作用（都清头像文件）]] ｜ [[DECISIONS.MD#D-25 批量删除只对失效账号生效（但确认框照常弹）]]
  - [[DECISIONS.MD#D-28 离线验证方式：`build/_probe` 探针（本项目长期做法）]]
- **[[DECISIONS.MD#D-29 平台页分"登录态 / 管理态"两种形态（2026-10-06 用户定）]] ~ [[DECISIONS.MD#D-37 "已查杀 PID"全局缓存（2026-10-07 用户提的方案，已实测）]]（2026-10-06 ~ 10-07）**，其中重点：
  - [[DECISIONS.MD#D-29 平台页分"登录态 / 管理态"两种形态（2026-10-06 用户定）]] ｜ [[DECISIONS.MD#D-30 列定义属性化 + 默认值（`sortable` 默认开）（2026-10-06 用户定）]]
  - [[DECISIONS.MD#D-31 列换序 = 两阶段，落点只认**初始槽位**（2026-10-06 用户设计）]] ｜ [[DECISIONS.MD#D-32 PID / HWND 只存内存，不落配置文件（2026-10-06 用户定）]]
  - **[[DECISIONS.MD#D-33 多开 = 查杀互斥体 + 降权启动（2026-10-07 用户定、已真机验证）]] ｜ [[DECISIONS.MD#D-37 "已查杀 PID"全局缓存（2026-10-07 用户提的方案，已实测）]]**
  - [[DECISIONS.MD#D-34 平台项点击策略：双击 = 启动，三击 = 取消（2026-10-07 用户定）]] ｜ [[DECISIONS.MD#D-35 通知：成功走 toast（自动淡出、无关闭按钮），失败才弹窗（2026-10-07 用户定）]] ｜ [[DECISIONS.MD#D-36 程序表"登录"带 `× __` 实例数量输入框（2026-10-07 用户定）]]

## 待办
- [[TODOS.MD#登录页面]]、[[TODOS.MD#统计页面]] — 占位未实现
- [[TODOS.MD#数据库层]]、[[TODOS.MD#平台图标提取]]、[[TODOS.MD#二进制补丁引擎]]
- [[TODOS.MD#安装版图标]] — 需确认生效
- [[TODOS.MD#SSL 握手]] — 打包版 handshake_failure
- [[TODOS.MD#utils 包]] — LoggerUtils/decrypt/image_utils/file_utils/Handle 操作待移植
- [[TODOS.MD#Handle 操作]] — 需 JNA 重写 NtQuerySystemInformation 系列
- [[TODOS.MD#上传日志功能]] — 设置页"日志"子项已预留按钮，需服务器后实现
- [[TODOS.MD#登录状态 UI 接入]] — 数据已自动维护落库，界面未展示
- [[TODOS.MD#事件驱动定向刷新迁移（EventBus 流B）]] — toggle-hidden 已迁移，其余操作待增量迁移
- [[TODOS.MD#待你拍板]] — **抗锯齿 `-Dprism.lcdtext=false` 保留与否**（若保留，打包脚本也要加）
- [[TODOS.MD#字体/字号（2026-10-05 已定）]] — 遗留：昵称列整列雅黑是否合适、平台内ID/最后登录账号列是否也改
- [[TODOS.MD#DEV_LOGS 欠账]] — 已补（2026-10-06）；后续每轮同步记录

## 事实
- [[FACTS.MD#当前阶段]]—Phase 1.16
- [[FACTS.MD#打包路径]]—build/portable/, build/exe/
- [[FACTS.MD#脚本位置]]—scripts/
- [[FACTS.MD#版本号]]—4.0.0.7000 (AppVersion.java), 4.0.0 (Gradle/packaging)
- [[FACTS.MD#JavaFX]]—Gradle cache, 17.0.2, 五个模块
- [[FACTS.MD#WiX]]—C:\Program Files (x86)\WiX Toolset v3.14\bin
- [[FACTS.MD#包结构]]—acccore/appcore/bridge/config/core/model/setting/swcore/ui/utils
- [[FACTS.MD#远程配置]]—RemoteConfigFetcher 默认 URL + AES-CBC 加密格式
- [[FACTS.MD#物理地图]]—docs/physical_map.md 完整文件树
- [[FACTS.MD#Handle 操作]]—Java 无原生 Handle 操作，需 JNA 仿照 pywinhandle.py
- [[FACTS.MD#解密实现]]—decrypt/ 包（DecryptInterface, WeChatDecrypt, WeixinDecrypt）
- [[FACTS.MD#Handle 操作]]—SwNativeOps.NtDllExt 已扩展 4 个 NT API 声明
- [[FACTS.MD#settings.json]]—showMessageTimestamps=true, claude-time 插件安装失败（hooks 冲突）
- [[FACTS.MD#AvatarUtils]]—头像获取工具类，本地/URL/SVG 三路回退（2026-07-30）
- [[FACTS.MD#page-main]]—主页面从 page-manage 复制迁移，作用域隔离修复
- [[FACTS.MD#新增功能（2026-07-31 会话）]]—账号列表来源/头像显示/日志修复与设置项/提交 5216773 + e7e348c
- [[FACTS.MD#新增模块（2026-08-01）]] — core 包（EventBus + 事件）+ PlatformEventBootstrap
- [[FACTS.MD#新增功能（2026-08-01 会话）]]—展示名/自动填充/EventBus 事件机制/提交 c2561a4 + EventBus 批次
- [[FACTS.MD#新增功能（2026-08-16 会话）]]—账号列表列定制：7列/列头右键菜单/列宽拖拽/快捷键编辑
- [[FACTS.MD#新增模块（2026-08-16 第二轮）]]—AccountTable 组件/快捷键 Scene 捕获/only 参数/NPE 修复
- [[FACTS.MD#新增功能（2026-08-16 晚间会话）]]—自定义滚动条体系/高度链/整行高亮/列宽规则定稿/分割线/NPE 修复
- [[FACTS.MD#规则文件（2026-08-16）]]—项目 AGENTS.md/全局 ~/.dsh/AGENTS.md
- [[FACTS.MD#远程配置发布工具（2026-10-04）]]—src/tools 源集/encryptRemoteConfigs 任务/CryptoUtils 加密单一实现/内置 URL v10+v2/Python 产物兼容实测
- [[FACTS.MD#表格文字【三级色】（用户 2026-10-05 定）]]、[[FACTS.MD#删除 / 重置的语义与副作用]]、[[FACTS.MD#三张表的名称列完全统一]]、[[FACTS.MD#原生程序名称链]]、[[FACTS.MD#`_alias` 已清理]]
- [[FACTS.MD#字体策略（2026-10-05 实测后定）]]、[[FACTS.MD#勾选框]]、[[FACTS.MD#账号头像文字兜底]]

## 开发日志
- [[DEV_LOGS.MD#page-main 复制迁移（2026-07-04~05）]] — 完整复制 DOM+JS，侧栏精简，旧代码剥离
- [[DEV_LOGS.MD#头像显示功能重构（2026-07-30）]] — AvatarUtils 引入、用户目录适配、SVG 文字回退样式
- [[DEV_LOGS.MD#账号列表来源 + 头像显示 + 日志设置页（2026-07-31）]] — 磁盘扫描来源/头像异步接入/日志修复/_handleAsync 双编码坑
- [[DEV_LOGS.MD#展示名 + SwAccData 自动填充 + EventBus 事件机制（2026-08-01）]] — 展示名/自动填充/EventBus 两事件流/NPE 修复
- [[DEV_LOGS.MD#账号列表列定制与交互升级（2026-08-16）]] — 7列结构/列头右键菜单/列宽拖拽/快捷键编辑/悬浮交互
- [[DEV_LOGS.MD#账号列表四表架构与交互优化（2026-08-16 第二轮）]] — AccountTable 组件/四表/标题行/固定列/快捷键修复
- [[DEV_LOGS.MD#账号列表交互打磨与滚动条体系（2026-08-16 晚间）]] — 滚动条全排查/高度链/整行高亮/分割线/AGENTS.md 迁移
- [[DEV_LOGS.MD#三十、彻底移除"借标题当提示条"（flashTitle）（2026-10-05）]] — 移除 flashTitle 整套模式
- [[DEV_LOGS.MD#三十一、刷新入口 + 页面进度条 + 平台图标 SVG 化 + 当前平台单击刷新策略（2026-10-05 晚）]]
- [[DEV_LOGS.MD#三十二、账号管理功能（行内/批量操作 + 就地编辑 + 快捷键录入定稿）（2026-10-05 晚）]]
- [[DEV_LOGS.MD#三十三、交互修复（编辑态卡住 / 点击落空）+ 自绘勾选框（2026-10-05 晚）]]
- [[DEV_LOGS.MD#三十四、程序表快捷键列 + 头像弹窗 + 版本号自动获取（2026-10-05 晚）]]
- [[DEV_LOGS.MD#三十五、账号头像文字兜底改"名称末尾 4 个字符宽" + 中文字体/抗锯齿实测（2026-10-05 深夜）]]
- [[DEV_LOGS.MD#三十六、勾选框"填满"真修 + 字号统一 14px（2026-10-05 深夜）]]
- [[DEV_LOGS.MD#三十七、三表名称列统一 + 原生程序名称链（2026-10-06 凌晨）]]
- [[DEV_LOGS.MD#三十八、表格文字三级色 + 删除/重置语义 + 批量删除规则（2026-10-06 凌晨）]]

## 迁移工程（2026-07-31）
- [[FACTS.MD#新增模块（2026-07-31）]] — appcore/acccore 包 + SwConfigProvider
- [[DECISIONS.MD#appcore/acccore 架构]] — Python func_core 迁移为 Java 包
- [[DEV_LOGS.MD#远程配置加密发布工具（2026-10-04）]] — src/tools 源集决策/兼容性验证证据/两个踩坑

---

## 文件清单（2026-10-05 整理）

| 文件 | 作用 |
|---|---|
| `MEMORY.md` | 本索引 |
| `FACTS.MD` | 当前事实（环境/数据/路径/键名等） |
| `DECISIONS.MD` | 决策记录（为什么这么做） |
| `TODOS.MD` | 待推进事项 |
| `DEV_LOGS.MD` | 开发日志（每次变更过程，含原 AGENTS.md 第九、十二~二十九节） |
| `LESSONS.MD` | 技术教训与经验结晶（含原 AGENTS.md 第十一节 50 条） |
| `ARCHIVE_settings_curtain_animation.md` | 设置区域窗帘改造前的实现与经验存档 |
