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
