# 补丁系统（v10 配置结构 + Java 方法设计）

> 目标读者：实现"增强功能 - 补丁"的开发者
> 配置基准：**v10**（`original_sw_v10.json`）。Java 版第一个版本就用 v10，不升版本号。
> 相关：`docs/remote_sw_structure.md`（原始结构摘录）

---

## 0. 三种补丁类型

| 类型 | 模式键 | 性质 | 操作对象 |
|---|---|---|---|
| 防撤回 | `anti-revoke` | 二元（打 / 撤） | 目标文件本身 |
| 多开 | `multirun` | 二元（打 / 撤） | 目标文件本身 |
| 共存 | `coexist` | 多元（工厂模板） | **副本**（原版不动） |

- **二元型**：对文件本身打补丁、撤补丁，状态只有"开 / 关"。
- **多元型（共存）**：按序号批量生产新实体（exe、dll、需要隔离的目录），原版一概不动。
- 数据目录（聊天记录等）公有，所有实例共用，不参与复制。

---

## 1. 工作模型：副本 → 刷入

**任何 feature 都不在原物件上直接改**，统一三步：

```
① 造临时副本   —— 文件复制成临时名；目录复制成临时目录
② 在副本上操作 —— 打补丁（mmap）、改名、递归处理 nested
③ 刷入         —— 改名为最终名，或用副本原子替换原文件
```

刷入的三种结果，由 `wildcard` + `del` 决定：

| wildcard | del | 刷入动作 | 效果 |
|---|---|---|---|
| 无 | — | 副本原子替换 `addr` 指向的原件 | 就地改（二元型；nested 内改副本内的文件） |
| 有 | `false`（默认） | 副本改名为 `wildcard` 名字，**原件保留** | 复制出一份新的 |
| 有 | `true` | 副本改名为 `wildcard` 名字，**删除原件** | 改名（rename） |

- 失败时：删掉临时副本即可，原件从未被写过。
- 目录的"临时副本"就是整目录的复制；目录的"刷入"就是把临时目录改名到最终名。
- 临时物与目标同目录、同盘，保证刷入是原子 rename。

例：

| 场景 | ① 临时副本 | ③ 刷入 |
|---|---|---|
| 顶层 `WeChatWin.dll` → `WeChatWi?.dll` | 复制成临时文件 | 临时文件改名为 `WeChatWi1.dll`（原件保留） |
| nested `node.dll` → `nod?.dll`，`del: true` | 复制成临时文件 | 改名为 `nod1.dll`，删除 `node.dll` |
| nested `node.dll` → `nod?.dll`，`del: false` | 复制成临时文件 | 改名为 `nod1.dll`，`node.dll` 保留 |
| nested `config.bin`（无 wildcard） | 复制成临时文件 | 原子替换回 `config.bin` |
| 二元型 `Weixin.dll`（无 wildcard） | 复制成临时文件 | 原子替换回 `Weixin.dll` |

---

## 2. 配置结构

```
sw（平台）
├─ 环境信息
├─ coexist   { alias, multi_state, channels }
├─ multirun  { alias, natively?, channels }
└─ anti-revoke { alias, channels }
        channels.{渠道}
        ├─ alias / introduce / authors
        ├─ （coexist）exe_wildcard / mutex_wildcard / ordinals / patch_wildcard
        └─ features[]
             ├─ addr           ← 目标路径；末尾 "/" 表示目录
             ├─ wildcard       ← 复制后的命名模板（`?` → 序号）
             ├─ del            ← 刷入后是否删除原件（默认 false）
             ├─ exclude        ← 目录复制时跳过（可选）
             └─ patch_rules[]  ← 按数组顺序执行
                  type = simple | custom | jmp_offset | relation | nested
```

### 2.1 平台级（补丁相关）

| 字段 | 说明 |
|---|---|
| `executable` / `executable_wildcards` | 主程序名 / 识别用通配 |
| `patch_addresses` | **原版主补丁文件**路径（一般主 dll），用于读版本、推导补丁目录 |
| `patch_dll` | 主补丁文件名（部分平台用） |
| `excluded_dirs` | 扫描安装目录时跳过的子目录 |
| `mutex_handles` / `mutex_handle_wildcards` | 互斥体名（内置多开时查杀） |
| `config_addresses` / `config_handle_wildcards` | 配置文件句柄（同上） |

### 2.2 模式级

| 字段 | 说明 |
|---|---|
| `alias` | 展示名 |
| `multi_state` | **识别方法开关**：`true` = 只判文件存在；缺省/`false` = 逐字节比对。与序号无关 |
| `natively` | `true` = 原生支持，不需要补丁（如 QQNT 多开） |
| `channels` | 渠道字典 |

### 2.3 渠道级

通用：`alias`（末尾带 `*` 表示含可自定义文本）、`introduce`、`authors`、`features`

coexist 专属：

| 字段 | 说明 |
|---|---|
| `exe_wildcard` | 克隆主程序命名模板，如 `WeCha?.exe` |
| `mutex_wildcard` | 原互斥体名 → 克隆后互斥体名 |
| `ordinals` | 可用序号串（单字符），如 `123456789A…Z` |
| `patch_wildcard` | 单值映射：原主补丁文件 → 克隆后主补丁文件 |

### 2.4 特征（feature）

| 字段 | 说明 |
|---|---|
| `addr` | 目标路径（`%变量%` 解析为绝对路径）。末尾 `/` = 目录 |
| `wildcard` | 刷入时的名字模板（`?` → 序号）。缺省 = 刷回 `addr` 本身 |
| `del` | 刷入后是否删除原件，默认 `false` |
| `exclude` | 目录复制时跳过的相对模式（可选） |
| `patch_rules` | 规则数组，按顺序执行；后一条以"前一条已生效"为前提 |

`features` 是**有序列表**：同一路径可以出现多次，依次执行，**后可覆盖前**。

### 2.5 规则（rule）公共结构

```json
{
  "type": "simple",
  "ver_adaptations": {
    "4.1":   { "original": "…", "modified": "…" },
    "4.0.6": null
  },
  "descript": "给人看的掩码"
}
```

- 版本键用 `pkg_find_compatible_version` 做兼容匹配（`"4.1"` 可服务 4.1.x）
- 值为 `null` = 该版本**弃用**这条规则（不是失败）
- 除 `type` / `ver_adaptations` 外的键都会带到物化结果里（`descript`/`tip`/`note`/`encoding`/`suffix_hex`/`parents`…）

---

## 3. 占位符

| 记号 | 含义 | 位置 |
|---|---|---|
| `?` | 序号字符（取自 `ordinals`） | `wildcard` / `exe_wildcard` / `mutex_wildcard` / `patch_wildcard` |
| `%变量%` | 路径变量：`%inst_path%` `%inst_dir%` `%dll_dir%` `%data_dir%` | `addr` |
| `??` | 任意单字节 | `original` / `modified` |
| `...` | 其余保持不变 | `modified` |
| `!!` | 待填占位（见下） | `modified` |
| `̲`（U+0332） | 可读掩码里标"被改的字节" | `descript` |

`!!` 的两种填充：

| 场景 | 填充为 |
|---|---|
| `type = jmp_offset` | 4 字节小端相对偏移 = 目标地址 − 下一条指令地址 |
| 共存刷入时（`simple` / `custom`） | 序号字符的 ASCII（`1` → `0x31`） |

---

## 4. 规则类型

| type | 扫描文件 | `original` / `modified` | 额外键 |
|---|---|---|---|
| `simple` | 是 | 特征码 / 补丁特征码（十六进制字节串） | `left_cut` `right_cut` `descript` |
| `custom` | 是 | 同上 | 加 `tip` `note` `encoding` `suffix_hex`，物化后带 `customizable: true` |
| `jmp_offset` | 是 | 特征码 / 含 4×`!!` 的补丁串 | `targets`（带 `!` 锚点的目标特征码） |
| `relation` | 否 | — | `parents` / `children` / `friends` |
| `nested` | 否 | — | **`features`**（结构同 2.4，可再嵌套） |

`nested` 的作用：父 feature 是目录时，把工作目录切换到该目录的临时副本，里面的 `features` 用相对 `addr` 继续处理。内层可再嵌套。

改名不再需要独立规则类型：`wildcard` + `del: true` 就是改名。

---

## 5. 生命周期

### 5.1 扫描 → 物化（建缓存）

输出：`SwCache.json` 里 `{mode}.channels.{ch}.precise_ver_adaptations.{版本}`

1. 定位 `%dll_dir%`、读 `multi_state`、取渠道字典
2. 若远程配置里有预烘焙的 `precise_ver_adaptations[版本]`，先抄进缓存
3. 允许跳过且缓存已存在且格式合法 → 跳过该渠道
4. 否则逐 feature 扫描：
   - 目录 feature：不扫特征码，其 `nested` 内部照常扫描
   - 文件 feature：mmap → 按顺序执行 `patch_rules` → 合并结果
5. 三条闸门：
   - 所有规则都"弃用" → 该渠道该版本删缓存
   - 任一 feature / 规则失败 → 不写缓存，记 `[ERR]`
   - 全部成功 → 写缓存

> 扫描依赖**未打补丁**的文件。补丁开着时重扫必然失败，所以强制重扫的固定流程是：关进程 → 从 `.bak` 恢复 → 扫描。

### 5.2 识别

| 场景 | 判据 |
|---|---|
| 渠道是否可用 | `multi_state` 决定方法；主补丁文件/目录存在 |
| 实例是否存在 | 克隆 exe（`exe_wildcard` 换序号）存在；存在即视为可用，损坏由用户重建 |
| 原版二元补丁状态 | 逐 patch 比对 `modified`，全部命中才算"开" |
| 实例内二元补丁状态 | 同上，对象是 `patch_wildcard` 映射后的克隆主文件 |

汇总：任一目标"文件不存在" → 渠道 `None`；全部 `true` → `true`；否则 `false`。

### 5.3 应用（二元型打/撤）

1. 要求进程已退出（提示，不静默强杀）
2. `target` 未指定时先识别再取反
3. 复制原件为临时文件 → mmap → 按 offset 写入 `modified`（打）或 `original`（撤）→ flush → 释放映射
4. 回读校验：每个 offset 处等于期望字节
5. 刷入：临时文件原子替换原件

失败：删临时文件，原件不动。

### 5.4 实例管理（共存）

| 操作 | 步骤 |
|---|---|
| 新建 | 取最小可用序号 → 逐 feature：造临时副本 → 打补丁/递归 nested → 刷入（改名 + 可选删原件）→ 登记 `acc_data` |
| 删除 | 删实例文件与目录（递归）→ 清账户数据 |
| 重建 | 删旧 → 按当前原版状态重新执行"新建"（继承原生补丁状态） |
| 重置 | 只处理原版：关进程 → 恢复所有 `.bak` → 强制重扫；实例靠重建 |

刷入阶段先做改名、最后做删除；中途失败按逆序撤销已完成的改名。

---

## 6. Java 方法设计

### 6.1 模块

| 类 | 状态 | 职责 |
|---|---|---|
| `SwHexUtils` | 已有 | 特征码分词、扫描、锚点首匹配、小端 hex |
| `SwRuleResolver` | 已有，改 | 五种规则解析；jmp_offset 补真实 FOA→VOA |
| `SwPathResolver` | 已有，改 | `%变量%` 解析、`?` → 序号、目录判定 |
| `SwAdapterChecker` | 已有，改 | 识别（multi-state / binary）、实例上下文 |
| `SwPatchCacheBuilder` | 新增 | 扫描 features → 物化 → 写缓存（三条闸门） |
| `SwCoexistManager` | 新增 | 临时副本、刷入、递归 nested、序号分配、回滚 |
| `SwPatchApplier` | 新增（可先包 `SwOperatorCore.switchPatchTo`） | 副本打补丁 + 原子替换 |
| `SwPatchCustomizer` | 新增 | `customizable` 文本补丁读写 |
| `SwPatchRelations` | 新增 | `relation` 冲突编排 |
| `SwVersionHelper` | 已有 | 版本读取 |

### 6.2 关键签名

```java
// 路径
static String resolve(String sw, String path, SwConfigAccessor acc);
static String applyOrdinal(String path, String ordinal);
static boolean isDirTarget(String path);
static String coexistMainPatch(String sw, String channel, String ordinal, SwConfigAccessor acc);

// 物化
SwPatchCacheBuilder.build(String sw, String mode, List<String> channels,
                          boolean skipCache, SwConfigAccessor acc, ObjectNode cache)
// → { ok, channels: { ch: { status: OK|DISABLED|FAILED, msg, ruleHits, failures[] } }, msg }

// 规则
SwRuleResolver.resolve(String curVer, ByteBuffer mm, JsonNode rule)
// → { patches: [...], deprecated: bool, error }
//   nested 产出子 features 引用，不放 patches

// 识别
SwAdapterChecker.identifyDllCore(String sw, String mode, List<String> channels,
                                 String coexistChannel, String ordinal,
                                 boolean skipCache, SwConfigAccessor acc, ObjectNode cache)

// 应用
SwPatchApplier.apply(String sw, String mode, String channel, String coexistChannel, String ordinal,
                     Boolean target, SwConfigAccessor acc, ObjectNode cache)
// → { ok, newState, msg, written: [...] }

// 实例
SwCoexistManager.create(String sw, String channel, String ordinal, SwConfigAccessor acc,
                        SwConfigAccessor accData, ObjectNode cache)
SwCoexistManager.delete(String sw, String instRoot)
SwCoexistManager.rebuild(String sw, String channel, String ordinal, …)
SwCoexistManager.nextOrdinal(String sw, String channel, SwConfigAccessor acc)

// 自定义文本 / 关系
SwPatchCustomizer.read(sw, mode, channel, coexistChannel, ordinal, …)
SwPatchCustomizer.write(sw, mode, channel, coexistChannel, ordinal, edits, …)
SwPatchRelations.conflictsOf(sw, mode, channel, acc)
SwPatchRelations.turnOffConflicts(sw, mode, channel, conflicts, coexistChannel, ordinal, …)

// 原生文件操作（补 SwNativeOps）
static boolean restoreFiles(List<String> paths);      // .bak → 原文
static boolean copyDirectory(Path src, Path dst, List<String> exclude, ProgressCb cb);
static boolean deleteDirectoryRecursively(Path dir);
static boolean atomicReplace(Path staged, Path target);   // Files.move ATOMIC_MOVE + REPLACE_EXISTING
```

### 6.3 新建实例的执行顺序

```
ordinal = nextOrdinal()
stageDir = <目标目录>/.jf_stage_<pid>_<ts>/          // 同盘，保证原子 rename

for feature in channel.features:                    // 数组顺序
    src = resolve(feature.addr)
    staged = copyToStage(src, stageDir)             // 文件或目录
    for rule in feature.patch_rules:                // 数组顺序
        nested → recurse(staged, rule.features)     // 工作目录切到 staged
        others → patch(staged, rule)                // mmap + 回读校验
    commit(staged, feature.wildcard ?? feature.addr, feature.del)

commit 阶段先改名、最后删除；失败按逆序撤销
```

### 6.4 日志与错误

- 扫描：每渠道一行（命中几个目标 / 几条规则），失败列出目标与原因
- 识别：`{sw}/{mode}/{channel} = true|false|unknown`，unknown 带"哪个文件不存在"
- 应用：写前写后各一行；每条 patch 的 offset 与长度（debug）
- 用户可见错误只说原因与措施：文件被占用 → 先退出程序；无适配 → 尝试重装该版本；状态未知 → 可执行[重置]；创建失败 → 删除后重建

### 6.5 任务中心

扫描、目录复制、重建走 `TaskRegistry.submit`，内部 `TaskContext.phase()` 报进度、`checkpoint()` 支持取消。

---

## 7. 实现注意

1. **mmap 释放后才能改名/删除**：Windows 上映射未解除时文件被占用；小文件可直接用 `FileChannel.write`，大文件 mmap 后主动 unmap。
2. **临时物必须同盘同目录**，否则 `Files.move` 会退化成跨盘复制，失去原子性。
3. **扫描依赖干净文件** → 强制重扫必须先关进程并恢复 `.bak`。
4. `!!` 有两种填充语义，靠 type 区分。
5. `customizable` 不参与状态判定 → 每个渠道至少要有一条非 customizable 的"开关"补丁，否则永远显示未开启。
6. 渠道级"全 True 才算开" → 半开会被判为关，切换时整渠道拉齐。
7. `reset` 只处理原版文件，实例靠重建。
8. 缓存键名统一为 `precise_ver_adaptations`（与配置一致；Java 现有 `precises` 需改）。
