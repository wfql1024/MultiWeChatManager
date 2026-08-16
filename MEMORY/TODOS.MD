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
- 打包版远程配置测试报 handshake_failure
- 已添加 jdk.crypto.ec，可能还需其他模块

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
- [ ] 共存账号表：`getSwExistedAccounts(swId,'coexist')`（共存 exe，`only` 参数已就绪）— 待接
- [ ] 原生程序表：平台主程序/共存程序列表（列：勾选框/名称/路径/状态）— 待定数据源
- [ ] 无效账号表：SwAccData 有记录但磁盘不存在的残留账号（列：勾选框/名称/ID/无效原因）— 待定判定逻辑

## 列表交互（2026-08-16 晚间已定稿）
- [x] 列宽自适应规则定稿：下限=列名宽+余量（展示名列=4字符+按钮占位），无上限；表格宽=列宽总和；固定列绝对固定
- [x] 自定义 overlay 滚动条体系（表内横向/账号区域纵向/设置区域纵向），JavaFX 原生滚动条弃用
- [x] 高度链锁定、整行悬浮高亮（JS 层）、分割线（--divider-solid）、空表行高/居左、列名（头像空/名称）
- [x] 规则文件统一 AGENTS.md（项目）+ ~/.dsh/AGENTS.md（全局）
