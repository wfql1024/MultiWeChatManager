---
name: signature-maintenance
description: 维护 JhiFengMultiChat 补丁特征码（平台 WeChat/Weixin/WXWork/QQNT/QQ/TIM/DouYinIM，模式 anti-revoke/multirun/coexist）。当出现"新版本打不上补丁""特征码未命中""某渠道又失效了""帮我从两个 dll 提取特征码""对比原版和打过补丁的文件""更新 ver_adaptations""校验特征库对新版本还有没有效"这类需求时，必须使用本 skill。它把"原版 dll vs 已打过补丁的 dll"的差异提炼成不含通配符的 original/modified，判定已存储的最新特征是否还能覆盖新版本，并产出可直接粘进 scripts/original_remote_sw_v10.json 的草稿。
---

# 特征码维护（JhiFengMultiChat）

这个 skill 只做**只读分析 + 草稿产出**。它不改任何 dll、不改正式配置、不发布远程配置、不写 MEMORY。
原因不是保守：被打过补丁的 dll 留在安装目录后，后续扫描必然失败（`docs/patch_system_design.md` §7.3），而远程配置一旦发出去就会到用户端。所以"判断"和"落盘"必须由人过一道手。

## 输入

一次维护只需要两样东西：
1. **一份干净的原始 dll**（目标平台主补丁文件，如 `Weixin.dll`、`WeChatWin.dll`）
2. **同一版本、已被别人打过补丁的 dll**（日常来自 BetterWX-UI 3.3.3 发布版；它可以选择打在原版或共存体上）

拿到这两份之后的一切分析都由 `scripts/diffsig.py` 完成。

## 事实基线（不要凭记忆，以这些为准）

| 事实 | 出处 |
|---|---|
| 特征库源文件 `scripts/original_remote_sw_v10.json`，结构 `平台→模式→channels→渠道→features[]→patch_rules[]→ver_adaptations{版本:{original,modified,...}}` | `docs/patch_system_design.md` §2 |
| **版本键不是前缀匹配**：精确键 > 不大于目标版本的最高键 > 全部键都更新时兜底取最低键 | `SwRuleResolver.findCompatibleVersion`（`SwRuleResolver.java` 104-126） |
| 版本键的值可以是 `null` = 该版本**弃用**这条规则（不是失败） | 同上 59-63 |
| token 语义：`??` 任意单字节；`!!` 占位符；**尾部 `...` 丢弃 = 其余不变**；**开头 `...` 只在 modified 侧表示左补齐**；半通配（`4?`）非法 | `SwHexUtils.tokenizeWildcard`（`SwHexUtils.java` 100-148） |
| `original` 与 `modified` 对齐后**长度必须完全相等**，否则线上直接判失败 | `SwHexUtils.convertAndAlign`（167-222） |
| 扫描取全部命中；命中多于 1 处意味着可能打到别的位置 | `SwHexUtils.searchPatternDicts`、`SwPatchCacheBuilder` 的失败闸门 |
| 发布链：改 JSON → `scripts\publish-configs.bat` → 版本号变了要同步 `RemoteConfigFetcher.BUILTIN_REMOTE_*_VERSION` | `MEMORY/facts.md` §7 |

## 工作流

### 第 0 步：先确认"干净原版"是真的干净
不要相信文件名。`.bak` 可能被覆盖成打过补丁的副本（实测本机 `Weixin.dll.bak` 与 `Weixin.dll` 的 SHA256 完全相同）。
跑一次 `diffsig.py diff A B`：报"共 0 个差异区间"就说明这两份是同一份文件，先去拿真正的原版（重装该版本、或从安装包解出、或用共存体未打补丁的那份）。

### 第 1 步：定位目标与版本
- 平台/模式/渠道：问清或从用户给的截图/描述里认出（`Weixin` 的 `anti-revoke` 有 silence / bubble / alert / custom_alert / alert2 五个渠道，各自打的位置不同）。
- 主补丁文件路径：按 `patch_addresses` 推导（`%dll_dir%/Weixin.dll` 之类），实际文件一般在 `<安装目录>\<版本号>\`。
- 当前版本号：从安装目录名或 PE 版本资源读，写进后续命令的 `--ver`。

### 第 2 步：确认已存储的特征在这个版本上到底有没有命中
```
python diffsig.py check --sw Weixin --mode anti-revoke --channel silence --ver 4.1.15.13 --file <干净原版.dll>
```
这一步给的是**基线**：哪些规则 PASS（不用动）、哪些 FAIL（要处理）、哪些多重命中（有误打风险，需要收紧或人工确认）、哪些 SKIP（该版本弃用）。
先看汇总行再逐条看明细，不要一上来就改 JSON。

### 第 3 步：差分出补丁点
```
python diffsig.py diff <干净原版.dll> <已打补丁.dll> --json tmp/skillwork/<日期>/diff.json
```
- 区间 = 差异被合并后的连续段（间隔 <= `--gap` 就并成一段）。
- 每个区间会渲染 A/B 两侧的十六进制与 ASCII，并用组合下划线标出差异字节的位置。
- 如果差异多到几百个区间，八成是拿错了文件（例如对比的是加了壳/被重打包的产物），先停下来核对。

### 第 4 步：把差异提炼成 original/modified
```
python diffsig.py extract <干净原版.dll> <已打补丁.dll> --json tmp/skillwork/<日期>/cand.json
```
- 对每个区间给出**不含 `??`** 的 `original`（原版字节）与等长 `modified`（补丁后字节）。
- 窗口先按 `--min-window`（默认 16 字节）撑开，再自动扩到"在原版文件里唯一命中"的最小长度。撑进来的字节是未变化的上下文，只为让特征够长——**线上取首个命中，非唯一就是隐患，太短就必然到处命中**；特征库真实签名多在 24~48 字节，2 字节的 `0F 84` 是废品。
- 默认跳过疑似字符串区间（品牌改名、URL 替换）。分类只看**差异本体**，不会被撑进来的上下文带偏。
- `--json` 里的 `draft` 是**能直接粘进 `ver_adaptations` 的片段**，版本键用 `<VERSION>` 占位，需要你填。

### 第 4.5 步：把区间对应回"库里的哪条规则"
```
python diffsig.py match --sw <平台> --mode <模式> --channel <渠道> --ver <版本> --file <干净原版.dll> \
  --regions tmp/skillwork/<日期>/cand.json [--key selected|latest|any] [--top 3]
```
不跑这一步就是在猜。判定分级：`exact-in-region`（该规则的 original 全文件命中且有一处落在区间内，基本就是它）> `exact-elsewhere`（别处有命中但不在区间里，看证据里的距离，几百 KB 以上基本等于不相关）> `fuzzy`（区间 ±4KB 内最像的位置，给不匹配比例）> `none`。
区间全 `none` 时不要硬套：这段差异通常是品牌改名/URL 替换，或者库里根本没记录过这个位置。
match 的 `--json` 每条候选带 `featureIndex/ruleIndex/key`，下一步 merge 直接拿来用。

### 第 5 步：判定"旧特征还能不能覆盖新版"（核心判断）
拿同一条规则、同一个语义位置的两份东西比：
- `--old` = 特征库里那条例**生效版本键**的 `original`；不给 `--old` 就让工具自己从库里取（`--sw/--mode/--channel/--feature/--rule` + `--key selected|latest`）
- `--new-bytes` = 第 4 步在**同一位置**得到的 `original`（不含通配，工具会拒绝带 `??` 的输入）

```
python diffsig.py merge --sw <平台> --mode <模式> --channel <渠道> --feature <i> --rule <j> \
  --key latest --new-bytes "<extract 的 original>" --file <新版干净原版.dll>
python diffsig.py merge --old "<库里的 original>" --new-bytes "<新得到的 original>" --file <新版干净原版.dll>
```

三种结局，对应三种处理：

| merge 结果 | 含义 | 处理 |
|---|---|---|
| 无需更新 | 旧特征的约束全部被新版满足 | 什么都不改，只在报告里记一笔"该键仍覆盖 <版本>" |
| 合并候选（出现新的 `??`） | 只是少数确定字节变了，位置和长度没变 | 用合并候选替换该键的 `original`（**只放松不放紧**，旧版本仍能匹配）；再用 `--file` 确认命中唯一 |
| 长度不一致 | 指令形态变了，靠通配救不回来 | 新增一个版本键（取当前版本号），把第 4 步的 original/modified 原样写进去 |

判断顺序永远是"先试着放宽已有键，放不动才加新键"。已存储键数量（现在已 40+）就是这套顺序的收益。

### 第 6 步：写草稿，交给人拍板
- 只把结果写进 `tmp/skillwork/<日期>/` 下的报告与 JSON 草稿。
- 报告里给出：改了哪条（平台/模式/渠道/feature 序号/规则序号）、版本键从什么变成什么、原始串与新串的对照、唯一性校验的命中次数。
- **改正式 `scripts/original_remote_sw_v10.json` 必须由用户明确指示**；发布（`scripts\publish-configs.bat`）同理。

### 第 7 步：改完回归
改了 JSON 之后建议跑一次：
```
python diffsig.py check --sw <平台> --mode <模式> --channel <渠道> --ver <目标版本> --file <干净原版.dll>
```
确认新写的键被选中、命中唯一、且**其它渠道没有从 PASS 变 FAIL**（放宽通配最容易在这里伤到别人）。

## 当旧特征完全找不到位置

`check` 报 FAIL 且 `merge` 连窗口都对不上时，用 `locate` 让工具给出"最像的位置"：
```
python diffsig.py locate --pattern "<旧 original>" --file <新版干净原版.dll>
```
它按锚点段找候选、按不匹配比例排序。不匹配比例小于 `--max-mismatch-ratio`（默认 0.15）且位置合理，说明是同一处代码被改了几个字节（回第 5 步）；一个候选都没有，说明这段代码被整体重写了，只能人工上 IDA/x64dbg 定位，再拿差分结果写特征。

## 报告模板

```
# 特征码维护报告 <平台>/<模式>/<渠道> @ <版本>

## 基线（改前）
- check 汇总：PASS x / 多重命中 y / FAIL z / SKIP w
- 选中版本键：<key>（模式 selected|latest）

## 差异
- 差分区间 N 个（code / string / unknown 分类计数）
- 与补丁点相关的区间：<偏移列表>

## 结论
| 规则 | 旧键 | merge 结果 | 处理 |
|---|---|---|---|
| feature#i rule#j | 4.1.5 | 合并候选（放宽 2 位） | 替换该键 original |

## 草稿
- 文件：tmp/skillwork/<日期>/draft.json
- 需要新增的版本键：<版本号 list>

## 待人工确认
- <多重命中的规则 / 无法定位的规则 / 需要真机验证的功能>
```

## 别踩这些坑（都是本项目踩过的）

1. **跨版本必变的位移字节必须写成 `??`**：`E8/E9` 的 rel32、`0F 8x` 的 rel32、`FF 15/FF 25` 的 RIP 相对 disp32、`EB/74/75` 的 rel8 —— 这些字节每次编译都会变，写死就注定断版本。实测 `multirun/default` 的 4.1.9 键就是败在这里：`FF 15 F9 CE 08 …` 把 disp32 写成了具体字节，4.1.15.13 上只差这 3 个字节就整条失效（其余 21 个确定字节一个都没变）。
2. **版本比较方向**：`compareVersionDesc(a,b) < 0` 表示 `a > b`。搞反了会选到最旧的适配版本，症状是"以前能扫到，现在扫不到"（`MEMORY/lessons.md:474`）。
3. **`...` 的位置语义**：只有开头才是"前补"，尾部是"省略"。`!!` 里的 `!` 不能被顺手剥掉（`lessons.md:478`）。
4. **别用通配表示"不想管"**：`??` 每多一个，误命中概率就上升一档；`original` 里的 `??` 只能来自"历史上确实变化过的位"，不能来自"我没看"。
5. **性能**：逐字节 Python 比较在 192MB 上是灾难。工具已经用锚点 + `bytes.find` 分段，自己写临时脚本时也别退回全量扫描（`lessons.md:483`）。
6. **失败不落盘**：任何"扫不出来"的结论都不要写进缓存或报告里的"已完成"栏位。
7. **本机 python 调用**：用完整路径 `D:\SpaceDev\Env\Infrastructure\runtime\python\Python312\python.exe`，并且不要把它的输出接进 PowerShell 管道（沙箱下管道会 EPERM，表现为"拒绝访问"）。

## 边界

- 只读：不改 dll、不改正式 JSON、不发布、不写 `MEMORY/` 的 facts/decisions/lessons/dev_logs（要记过程就追加 `MEMORY/tmp/<日期>.md` 素材卡）。
- 临时产物只放 `tmp/skillwork/<日期>/`（`tmp` 已 gitignore）。
- 打补丁这一步如果 agent 参与（截图识别 + 操作第三方工具），全程**不要碰正式安装目录**：让用户先把原版复制出来，或者用共存体。
