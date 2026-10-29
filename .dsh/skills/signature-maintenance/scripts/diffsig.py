#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diffsig.py — 只读二进制差分 / 特征码提炼 / 特征库自检工具（Windows + Python 3.12，零第三方依赖）。

六个子命令
  diff     两个等长文件逐字节差分，按间隔合并为差异区间并带上下文渲染
  extract  从差异区间提炼"候选特征码对"（original / modified，绝不含通配符）并给区间分类
  match    把差异区间对应到特征库里具体哪条规则（feature#/rule#/版本键），补上"这段差异属于哪个渠道"
  check    按特征库语义选出实际生效的版本键，在目标 dll 上扫描每条规则的 original
  merge    判断已存储的 original 特征码能否覆盖新版本（只放松不放紧）
  locate   旧特征不再严格命中时，按锚点找"最像的位置"（漂移定位）

只读保证
  本工具不写配置、不改任何 dll/exe、不打补丁、不上传。
  唯一的写操作是 --json 指定的输出文件（由你显式给出路径）。

版本键（--key）
  selected（默认）复刻 SwRuleResolver.findCompatibleVersion：精确 > 不大于目标的最高键 > 最低键
  latest           忽略目标版本，直接取该规则 ver_adaptations 里版本号最大的键
  两种模式都会打印选键模式、最终用的键、以及该键的值是不是 null（弃用）

用法速查
  python diffsig.py diff    A.dll B.dll [--gap 8] [--left 64] [--right 96] [--json out.json]
  python diffsig.py extract A.dll B.dll [--gap 8] [--min-window 16] [--max-window 512]
                            [--include-strings] [--json out.json]
  python diffsig.py match   --sw Weixin --mode anti-revoke --channel alert --ver 4.1.15.13
                            --file X.dll [--regions extract.json] [--region 0x..-0x..]...
                            [--key selected|latest|any] [--search-span 4096] [--top 3] [--json o.json]
  python diffsig.py check   --sw Weixin --mode anti-revoke --channel silence --ver 4.1.15.13
                            --file X.dll [--key selected|latest] [--region 0x1A20-0x1B00]
  python diffsig.py merge   --old "48 8D ?? ?? E8" --new-bytes "48 8D AA BB E8" [--file X.dll]
  python diffsig.py merge   --sw Weixin --mode anti-revoke --channel bubble --ver 4.1.0
                            --feature 0 --rule 5 [--key latest] --new-bytes "..."
  python diffsig.py locate  --pattern "74 6E 48 8D 8D ?? ?? 00 00" --file X.dll [--top 5]
                            [--max-mismatch-ratio 0.15] [--region 0x100000-0x200000] [--json o.json]
"""

from __future__ import annotations

import argparse
import functools
import json
import mmap
import os
import re
import sys
import time

# --------------------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------------------

LOW_LINE = "\u0332"          # 组合下划线：用来标记差异字节
WILDCARD = "??"              # 任意单字节
PLACEHOLDER = "!!"           # 占位符（不是通配符，扫描时必须报错）
TRUNCATE = "..."             # 省略标记
DEFAULT_CONFIG = os.path.join("scripts", "original_remote_sw_v10.json")
SUPPORTED_TYPES = ("simple", "custom", "jmp_offset")
MAX_DIFF_POSITIONS = 4_000_000   # 差异字节数护栏（防止把内存打爆）
DIFF_CHUNK = 1 << 20             # 差分分块大小 1 MiB
HIT_PRINT_LIMIT = 8              # 每条规则打印前几个命中偏移
ANNOTATE_LIMIT = 12              # 每个区间每侧最多注释几处
MIN_ANCHOR = 4                   # locate 锚点块最小长度（低于此长度不许当锚点，否则海量误报）
LOCATE_TOP_DEFAULT = 5           # locate 默认输出几个候选
LOCATE_ANCHOR_WIDTH = 8          # locate 锚点窗口长度（越长越少见，4 字节在 192MB 上会海量误报）
LOCATE_ANCHOR_SLIDE = 4          # 同一确定字节段内锚点滑窗步进（步进小于窗宽 -> 少数字节变化仍留活口）
LOCATE_MAX_CANDIDATES = 20000    # locate 候选数护栏
LOCATE_CHUNK_PRINT = 12          # locate 最多打印几个锚点
MISMATCH_PRINT_LIMIT = 16        # 每个候选最多列几处不匹配
STRING_TEXT_RATIO = 0.6          # 窗口文本占比 >= 它 -> string
CODE_TEXT_RATIO = 0.3            # 文本占比 < 它且含常见指令字节 -> code
BANG = "!"                       # targets 里的锚点前缀
VERSION_PLACEHOLDER = "<VERSION>"  # extract 草稿里的版本键占位符
CLASS_KINDS = ("code", "string", "unknown")
MIN_WINDOW_DEFAULT = 16          # extract 最小窗口：差异本体不够长时先补两侧未变化上下文到它
MATCH_TOP_DEFAULT = 3            # match 每个区间最多列几条候选规则
MATCH_SEARCH_SPAN = 4096         # match 模糊命中的搜索跨度（区间 ± 该值）
MATCH_ORIGINAL_PREVIEW = 12      # match 打印规则 original 的前几个字节
MATCH_MISMATCH_PRINT = 8         # match 模糊命中最多列几处不匹配
MATCH_METHODS = ("exact-in-region", "exact-elsewhere", "fuzzy", "none")
MATCH_METHOD_RANK = {"exact-in-region": 0, "exact-elsewhere": 1, "fuzzy": 2, "none": 3}

# extract 分类用的常见指令字节序列（长序列在前，只做"像不像指令"，不是反汇编）
INSTR_SEQS = [bytes.fromhex(h) for h in (
    "66C705", "0F84", "0F85", "FF25",
    "488D", "488B", "4889", "4839", "4883",
    "E8", "E9", "EB", "74", "75", "C7", "C3", "8D", "89", "90",
)]

# 不支持扫描的规则类型及理由（relation / nested 继续 SKIP，但把原因写清楚）
TYPE_SKIP_REASONS = {
    "relation": "relation 只声明渠道间的父子关系（children/parents），没有 original 字节，无法扫描",
    "nested": "nested 只是把别的渠道的规则嵌进来执行，本工具按扁平 original 扫描，对应不到具体字节",
}

# 小型 x86-64 启发式表：只做"看一眼像什么指令"，绝不假装完整反汇编。
X86_HINTS = [
    (bytes.fromhex("66C705"), "66 C7 05 -> mov word ptr [rip+disp32], imm16"),
    (bytes.fromhex("0F84"), "0F 84 rel32 -> jz（相等则跳；打补丁常改成 90 E9）"),
    (bytes.fromhex("0F85"), "0F 85 rel32 -> jnz"),
    (bytes.fromhex("FF25"), "FF 25 -> jmp qword ptr [rip+disp32]"),
    (bytes.fromhex("488D"), "48 8D -> lea r64"),
    (bytes.fromhex("488B"), "48 8B -> mov r64"),
    (bytes.fromhex("4889"), "48 89 -> mov r/m64"),
    (bytes.fromhex("4839"), "48 39 -> cmp r64"),
    (bytes.fromhex("4883"), "48 83 -> add/sub/cmp r64, imm8"),
    (bytes.fromhex("E9"), "E9 rel32 -> jmp（远处跳转）"),
    (bytes.fromhex("EB"), "EB rel8 -> jmp（近处跳转，常用来顶掉条件跳转）"),
    (bytes.fromhex("E8"), "E8 rel32 -> call"),
    (bytes.fromhex("74"), "74 rel8 -> jz"),
    (bytes.fromhex("75"), "75 rel8 -> jnz"),
    (bytes.fromhex("90"), "90 -> nop（打补丁最常用的填充）"),
    (bytes.fromhex("C3"), "C3 -> ret"),
    (bytes.fromhex("CC"), "CC -> int3"),
]

_NONZERO_RUN = re.compile(rb"[^\x00]+")


class ToolError(Exception):
    """带"怎么办"提示的用户级错误。"""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


# --------------------------------------------------------------------------------------
# 特征码语义（严格复刻 SwHexUtils.tokenizeWildcard）
# --------------------------------------------------------------------------------------

def tokenize_wildcard(text: str, side: str) -> list:
    """把特征码字符串切成 token 列表，复刻 Java 侧 tokenizeWildcard 的行为。

    - 先去掉全部空白再转大写；
    - 开头的 "..." -> 产出 "..." token（左补齐，仅 modified 侧合法）；
      结尾的 "..." -> 直接丢掉（表示"其余不变"）；
    - 其余每 2 字符一个 token，允许 "??"（任意单字节）与 "!!"（占位符）；
    - 半通配（"4?" "?F" "!0" 等）非法。
    """
    raw = text if text is not None else ""
    s = re.sub(r"\s+", "", raw).upper()
    tokens = []
    if s.startswith(TRUNCATE):
        tokens.append(TRUNCATE)
        s = s[3:]
    elif s.endswith(TRUNCATE):
        s = s[:-3]
    if len(s) % 2 != 0:
        raise ToolError(
            f"特征码长度非法（去掉空白后 {len(s)} 个字符，应为偶数）：{raw!r}",
            "按两个十六进制字符一个字节书写，例如 \"48 8D ?? ?? E8\"",
        )
    for i in range(0, len(s), 2):
        pair = s[i:i + 2]
        for ch in pair:
            if not (("0" <= ch <= "9") or ("A" <= ch <= "F") or ch in "?!"):
                raise ToolError(
                    f"特征码含非法字符 {ch!r}：{raw!r}",
                    "只允许 0-9 A-F 与 ? ! 以及空白分隔符",
                )
        if pair in (WILDCARD, PLACEHOLDER):
            tokens.append(pair)
        elif "?" in pair or "!" in pair:
            raise ToolError(
                f"特征码含半通配字节 {pair!r}：{raw!r}",
                "通配必须整字节写成 ??（任意单字节）或 !!（占位符）；半通配如 4? ?F 不合法",
            )
        else:
            tokens.append(pair)
    return tokens


class Pattern:
    """编译好的特征码：tokens 中 None 表示任意字节。"""

    __slots__ = ("tokens", "size", "left_fill", "text")

    def __init__(self, tokens: list, left_fill: bool, text: str):
        self.tokens = tokens
        self.size = len(tokens)
        self.left_fill = left_fill
        self.text = text

    def to_text(self) -> str:
        out = []
        for t in self.tokens:
            out.append(WILDCARD if t is None else f"{t:02X}")
        body = " ".join(out)
        return (TRUNCATE + " " + body) if self.left_fill else body


def compile_pattern(text: str, side: str) -> Pattern:
    """编译特征码。side 用于决定 "..." 与 "!!" 是否合法。"""
    tokens = tokenize_wildcard(text, side)
    left_fill = False
    compiled = []
    for tok in tokens:
        if tok == TRUNCATE:
            if side != "modified":
                raise ToolError(
                    f"{side} 侧特征码不允许以 ... 开头（左补齐只对 modified 合法）：{text!r}",
                    "把开头的 ... 去掉；original 必须是确定的字节序列（可含 ??）",
                )
            left_fill = True
        elif tok == PLACEHOLDER:
            raise ToolError(
                f"特征码含占位符 !!（它是占位标记，不是通配符）：{text!r}",
                "扫描/差分请不要用 !!；需要任意字节请写 ??，需要「其余不变」请在结尾写 ...",
            )
        elif tok == WILDCARD:
            compiled.append(None)
        else:
            compiled.append(int(tok, 16))
    return Pattern(compiled, left_fill, text)


# --------------------------------------------------------------------------------------
# 扫描
# --------------------------------------------------------------------------------------

def _anchor_of(tokens: list):
    """把 token 里最长的连续确定字节段当作扫描锚点。返回 (偏移, bytes) 或 None。"""
    best = None
    best_len = 0
    i = 0
    n = len(tokens)
    while i < n:
        if tokens[i] is None:
            i += 1
            continue
        j = i
        while j < n and tokens[j] is not None:
            j += 1
        if j - i > best_len:
            best_len = j - i
            best = (i, bytes(tokens[i:j]))
        i = j
    return best


def find_all_raw(buf, needle: bytes) -> list:
    """在 buf 中找出 needle 的全部命中偏移（允许重叠）。"""
    if not needle:
        return []
    hits = []
    pos = 0
    while True:
        j = buf.find(needle, pos)
        if j < 0:
            break
        hits.append(j)
        pos = j + 1
    return hits


def find_all_pattern(buf, pat: Pattern) -> list:
    """按特征码语义扫描：先用最长确定段做 bytes.find 锚点，再逐点校验通配。"""
    if pat.left_fill:
        raise ToolError(
            "带左补齐（开头 ...）的特征码无法直接扫描",
            "扫描请用 original 的完整前缀；左补齐只用于 modified",
        )
    if pat.size == 0:
        raise ToolError("特征码为空，无法扫描", "检查配置里该版本键的 original 字段")
    size = len(buf)
    if size == 0 or pat.size > size:
        return []
    anchor = _anchor_of(pat.tokens)
    if anchor is None:
        raise ToolError(
            "特征码没有任何确定字节（全是 ??），无法作为扫描锚点",
            "特征码至少要有一段确定字节，否则命中数等于文件长度，没有意义",
        )
    a_off, a_bytes = anchor
    a_end = a_off + len(a_bytes)
    hits = []
    pos = 0
    while True:
        j = buf.find(a_bytes, pos)
        if j < 0:
            break
        start = j - a_off
        if start >= 0 and start + pat.size <= size:
            ok = True
            for k in range(a_off):
                t = pat.tokens[k]
                if t is not None and buf[start + k] != t:
                    ok = False
                    break
            if ok:
                for k in range(a_end, pat.size):
                    t = pat.tokens[k]
                    if t is not None and buf[start + k] != t:
                        ok = False
                        break
            if ok:
                hits.append(start)
        pos = j + 1
    return hits


def split_marked_text(text: str) -> tuple:
    """拆分带 `!` 前缀锚点的特征码（只用于 jmp_offset 的 targets）。

    语义复刻 SwHexUtils.searchFirstPatternWithMarked：
    `!48` 表示"这个字节是锚点"；返回的首个 `!` 的 token 下标就是 marked 偏移。
    返回 (去掉 ! 的特征码文本, 首个 ! 的 token 下标或 None)。
    """
    raw = text if text is not None else ""
    s = re.sub(r"\s+", "", raw).upper()
    if s.endswith(TRUNCATE):
        s = s[:-3]
    out = []
    bang = None
    i = 0
    n = len(s)
    while i < n:
        if s[i] == BANG:
            if bang is None:
                bang = len(out)
            i += 1
            if i >= n:
                raise ToolError(
                    f"锚点特征码以 ! 结尾，缺少它标记的字节：{raw!r}",
                    "! 必须紧贴在一个字节前，例如 !48 8B 8D",
                )
        if i + 2 > n:
            raise ToolError(
                f"锚点特征码长度非法（去掉空白后 {n} 个字符，应为偶数）：{raw!r}",
                "按两个十六进制字符一个字节书写",
            )
        pair = s[i:i + 2]
        for ch in pair:
            if not (("0" <= ch <= "9") or ("A" <= ch <= "F") or ch in "?!"):
                raise ToolError(
                    f"锚点特征码含非法字符 {ch!r}：{raw!r}",
                    "只允许 0-9 A-F 与 ? ! 以及空白分隔符",
                )
        if pair not in (WILDCARD, PLACEHOLDER) and ("?" in pair or "!" in pair):
            raise ToolError(
                f"锚点特征码含半通配字节 {pair!r}：{raw!r}",
                "通配必须整字节写成 ??；! 只作为锚点前缀紧贴某个字节",
            )
        out.append(pair)
        i += 2
    return " ".join(out), bang


# --------------------------------------------------------------------------------------
# 文件映射
# --------------------------------------------------------------------------------------

class MappedFile:
    """只读 mmap 包装（空文件退化为 b""）。"""

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        if not os.path.exists(self.path):
            raise ToolError(
                f"文件不存在：{path}",
                "检查路径拼写；路径含空格或中文时用引号包住",
            )
        if os.path.isdir(self.path):
            raise ToolError(f"这是一个目录而不是文件：{path}", "请指向具体的 dll/exe 文件")
        self._fh = open(self.path, "rb")
        self.size = os.fstat(self._fh.fileno()).st_size
        self.mm = mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ) if self.size else b""

    def close(self):
        if isinstance(self.mm, mmap.mmap):
            self.mm.close()
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


# --------------------------------------------------------------------------------------
# 差分与区间
# --------------------------------------------------------------------------------------

def _chunk_diff_offsets(a: bytes, b: bytes) -> list:
    """块内差异偏移：整块异或后再找非零字节，比逐字节 Python 循环快一个数量级。"""
    x = int.from_bytes(a, "big") ^ int.from_bytes(b, "big")
    if x == 0:
        return []
    xb = x.to_bytes(len(a), "big")
    out = []
    for m in _NONZERO_RUN.finditer(xb):
        out.extend(range(m.start(), m.end()))
    return out


def iter_diff_positions(mm1, mm2, size: int):
    """按块扫描出全部差异字节的绝对偏移（升序）。"""
    for base in range(0, size, DIFF_CHUNK):
        n = min(DIFF_CHUNK, size - base)
        a = mm1[base:base + n]
        b = mm2[base:base + n]
        if a == b:
            continue
        for off in _chunk_diff_offsets(a, b):
            yield base + off


def scan_diff_regions(mm1, mm2, size: int, gap: int, max_positions: int):
    """把差异字节合并成区间。

    区间 = [start, end)（end 不含），长度 = end - start。
    合并判据：两个差异字节之间夹着的相同字节数 <= gap 就并入同一区间。
    """
    regions = []
    cur = None
    total = 0
    for pos in iter_diff_positions(mm1, mm2, size):
        total += 1
        if total > max_positions:
            raise ToolError(
                f"差异字节数超过护栏上限 {max_positions}（已统计到 {total}），疑似两个不同版本的文件",
                "先确认 A 是本机原版、B 是同一版本打完补丁的副本；确认无误可加大 --max-positions",
            )
        if cur is None or pos - cur["positions"][-1] - 1 > gap:
            if cur is not None:
                regions.append(cur)
            cur = {"start": pos, "end": pos + 1, "positions": [pos]}
        else:
            cur["positions"].append(pos)
            cur["end"] = pos + 1
    if cur is not None:
        regions.append(cur)
    return regions, total


# --------------------------------------------------------------------------------------
# 渲染（沿用 legacy_python/utils/diff2files.py 的可读风格）
# --------------------------------------------------------------------------------------

def _render_hex_line(data: bytes, rel: set) -> str:
    parts = []
    for i, byte in enumerate(data):
        h = f"{byte:02X}"
        parts.append("".join(LOW_LINE + c for c in h) if i in rel else h)
    return " ".join(parts)


def _render_ascii_lines(data: bytes, rel: set):
    spaced = []
    compact = []
    for i, byte in enumerate(data):
        c = chr(byte) if 32 <= byte <= 126 else "."
        if i in rel:
            spaced.append(" " + LOW_LINE + c)
            compact.append(LOW_LINE + c)
        else:
            spaced.append(" " + c)
            compact.append(c)
    return " ".join(spaced), "".join(compact)


def annotate_at(buf, pos: int) -> str:
    """启发式识别 pos 处看起来像什么 x86-64 指令；认不出返回 "?"。"""
    if pos < 0 or pos >= len(buf):
        return "?"
    for prefix, text in X86_HINTS:
        if buf[pos:pos + len(prefix)] == prefix:
            return text
    return "?"


def render_region(lines: list, label: str, path: str, buf, region: dict,
                  left: int, right: int, size: int, with_notes: bool):
    ctx_start = max(region["start"] - left, 0)
    ctx_end = min(region["end"] + right, size)
    data = buf[ctx_start:ctx_end]
    rel = {p - ctx_start for p in region["positions"]}
    lines.append(f"### {label}: {path}  [0x{ctx_start:08X}~0x{ctx_end:08X}]")
    lines.append(_render_hex_line(data, rel))
    spaced, compact = _render_ascii_lines(data, rel)
    lines.append(spaced)
    lines.append(compact)
    if with_notes:
        shown = region["positions"][:ANNOTATE_LIMIT]
        notes = [f"0x{p:08X} {annotate_at(buf, p)}" for p in shown]
        if len(region["positions"]) > ANNOTATE_LIMIT:
            notes.append(f"…（其余 {len(region['positions']) - ANNOTATE_LIMIT} 处略）")
        lines.append(f"启发式({label}): " + " ; ".join(notes))


def render_byte_pairs(a, b, positions: list, limit: int = 32) -> str:
    shown = positions[:limit]
    items = [f"0x{p:08X}:A={a[p]:02X}/B={b[p]:02X}" for p in shown]
    tail = "" if len(positions) <= limit else f"  …（共 {len(positions)} 处，仅列前 {limit} 处）"
    return "逐字节对照: " + "  ".join(items) + tail


# --------------------------------------------------------------------------------------
# 分类（code / string / unknown）与"漂移定位"
# --------------------------------------------------------------------------------------

def _printable_byte(b: int) -> bool:
    return 32 <= b <= 126 or b in (9, 10, 13)


def text_ratios(window: bytes) -> tuple:
    """窗口的可打印文本占比：返回 (综合, ASCII, UTF-16LE)。"""
    n = len(window)
    if n == 0:
        return 0.0, 0.0, 0.0
    ascii_hit = sum(1 for b in window if _printable_byte(b))
    utf16_hit = 0
    for i in range(0, n - 1, 2):
        lo, hi = window[i], window[i + 1]
        if (hi == 0 and _printable_byte(lo)) or (lo == 0 and _printable_byte(hi)):
            utf16_hit += 2
    r_ascii = ascii_hit / n
    r_utf16 = utf16_hit / n
    return max(r_ascii, r_utf16), r_ascii, r_utf16


def classify_window(window: bytes, subject: str = "窗口") -> dict:
    """给一段字节打启发式分类：文本占比 >= 0.6 判 string；文本少且含常见指令字节判 code。

    subject 只影响 why 的措辞（extract 用"差异本体"传入，避免把被撑开的上下文说成判断对象）。
    """
    r_text, r_ascii, r_utf16 = text_ratios(window)
    instr = [seq for seq in INSTR_SEQS if seq in window]
    if r_text >= STRING_TEXT_RATIO:
        kind = "string"
        why = f"{subject}文本占比 {r_text:.2f} >= {STRING_TEXT_RATIO}（品牌改名/URL 替换之类）"
    elif r_text < CODE_TEXT_RATIO and instr:
        kind = "code"
        why = f"{subject}文本占比 {r_text:.2f} < {CODE_TEXT_RATIO} 且含指令字节 {hex_compact(instr[0])}"
    elif r_text >= CODE_TEXT_RATIO:
        kind = "unknown"
        why = f"{subject}文本占比 {r_text:.2f} 落在 {CODE_TEXT_RATIO}~{STRING_TEXT_RATIO} 的灰区"
    else:
        kind = "unknown"
        why = f"{subject}文本占比 {r_text:.2f} 够低，但里面没有常见指令字节"
    return {
        "kind": kind,
        "why": why,
        "textRatio": round(r_text, 4),
        "asciiRatio": round(r_ascii, 4),
        "utf16Ratio": round(r_utf16, 4),
        "instrHits": [hex_compact(seq) for seq in instr[:12]],
        "instrHitCount": len(instr),
    }


def segments_of(tokens: list) -> list:
    """模式里全部连续确定字节段：[(pattern 偏移, 段长)]。"""
    segs = []
    i, n = 0, len(tokens)
    while i < n:
        if tokens[i] is None:
            i += 1
            continue
        j = i
        while j < n and tokens[j] is not None:
            j += 1
        segs.append((i, j - i))
        i = j
    return segs


def locate_anchors(tokens: list, width: int = LOCATE_ANCHOR_WIDTH,
                   slide: int = LOCATE_ANCHOR_SLIDE) -> tuple:
    """构造 locate 的锚点：确定字节段内长为 width 的滑窗（步进 slide），短段整段当锚点。

    返回 (锚点列表 [(pattern 偏移, bytes)], 太短被跳过的段 [(偏移, 长度)])。
    锚点按"越长越前"排序 —— 长串在文件里更少见，先扫它才不会被常见短串淹没。
    """
    anchors = []
    skipped = []
    for off, length in segments_of(tokens):
        if length >= width:
            k = 0
            while k + width <= length:
                anchors.append((off + k, bytes(tokens[off + k:off + k + width])))
                k += slide
            last = length - width
            if last > 0 and (last % slide):
                anchors.append((off + last, bytes(tokens[off + last:off + length])))
        elif length >= MIN_ANCHOR:
            anchors.append((off, bytes(tokens[off:off + length])))
        else:
            skipped.append((off, length))
    anchors.sort(key=lambda a: (-len(a[1]), a[0]))
    return anchors, skipped


def locate_candidates(buf, pat: Pattern, anchors: list,
                      max_total: int = LOCATE_MAX_CANDIDATES) -> tuple:
    """按锚点取候选起点，再逐字节比对（?? 位置永远算相同）。

    候选约束：命中的锚点个数 >= min(2, 锚点总数)。锚点命中数是"就地比对"出来的
    （不是靠别的锚点也落在同一 start），所以常见短锚点会把全部出现都送进来，
    真正相似的位置不会被单锚点预算挤掉。
    返回 (候选列表（按不匹配比例升序）, 是否因为候选太多而只保留了最好的那些)。
    """
    size = len(buf)
    det = [k for k, t in enumerate(pat.tokens) if t is not None]
    need = min(2, len(anchors))
    out = {}
    truncated = False
    for aoff, abytes in anchors:
        pos = 0
        while True:
            j = buf.find(abytes, pos)
            if j < 0:
                break
            pos = j + 1
            start = j - aoff
            if start < 0 or start + pat.size > size or start in out:
                continue
            matched = 0
            for boff, bbytes in anchors:
                end = start + boff + len(bbytes)
                if end <= size and buf[start + boff:end] == bbytes:
                    matched += 1
            if matched < need:
                continue
            bad = []
            for k in det:
                actual = buf[start + k]
                if actual != pat.tokens[k]:
                    bad.append((k, pat.tokens[k], actual))
            out[start] = {
                "offset": start,
                "mismatchCount": len(bad),
                "determinateCount": len(det),
                "length": pat.size,
                "ratio": (len(bad) / len(det)) if det else 0.0,
                "matchedAnchors": matched,
                "mismatches": bad,
            }
            if len(out) > max_total * 2:
                kept = sorted(out.values(), key=lambda c: c["ratio"])[:max_total]
                out = {c["offset"]: c for c in kept}
                truncated = True
    cands = sorted(out.values(),
                   key=lambda c: (c["ratio"], c["mismatchCount"], c["offset"]))
    return cands, truncated


# --------------------------------------------------------------------------------------
# 版本键（严格复刻 SwRuleResolver.findCompatibleVersion）
# --------------------------------------------------------------------------------------

def _ver_parts(v: str) -> list:
    parts = []
    for piece in str(v).split("."):
        try:
            parts.append(int(piece))
        except (TypeError, ValueError):
            parts.append(0)
    return parts


def compare_ver_asc(a: str, b: str) -> int:
    pa = _ver_parts(a)
    pb = _ver_parts(b)
    for i in range(max(len(pa), len(pb))):
        va = pa[i] if i < len(pa) else 0
        vb = pb[i] if i < len(pb) else 0
        if va != vb:
            return -1 if va < vb else 1
    return 0


def find_compatible_version(target: str, keys) -> tuple:
    """返回 (版本键, 选键规则)。规则：exact / highest-not-greater / lowest-fallback。"""
    keys = list(keys)
    if not keys:
        return None, "none"
    if target in keys:
        return target, "exact"
    ordered = sorted(keys, key=functools.cmp_to_key(compare_ver_asc), reverse=True)  # 版本降序
    for v in ordered:
        if compare_ver_asc(v, target) <= 0:
            return v, "highest-not-greater"
    return ordered[-1], "lowest-fallback"


def select_version_key(va: dict, ver: str, mode: str) -> tuple:
    """按 --key 选出目标版本键：返回 (键, 选键规则, 值是否为 null)。

    mode=selected：复刻 findCompatibleVersion（精确 > 不大于目标的最高键 > 最低键）。
    mode=latest  ：忽略目标版本，直接取版本号最大的键（"和 json 里最新的版本比对"）。
    """
    keys = list(va.keys())
    if not keys:
        return None, "none", False
    if mode == "latest":
        key = max(keys, key=functools.cmp_to_key(compare_ver_asc))
        return key, "highest-key-ignored-target", va.get(key) is None
    key, kind = find_compatible_version(ver, keys)
    return key, kind, (va.get(key) is None if key is not None else False)


def describe_version_value(value) -> str:
    """把版本键的值描述成一句话：null（弃用）/ 有 original / 对象但无 original。"""
    if value is None:
        return "null（该版本弃用此规则）"
    if isinstance(value, dict):
        if value.get("original"):
            return "有 original/modified"
        keys = "、".join(list(value.keys())[:6])
        return f"是对象但没有 original（字段：{keys}）"
    return f"是 {type(value).__name__}，不是对象（结构异常）"


def version_rule_text(rule: str, target: str, key: str) -> str:
    if rule == "exact":
        return "精确匹配"
    if rule == "highest-not-greater":
        return f"用不大于目标的最高键（目标 {target} 无精确键）"
    if rule == "lowest-fallback":
        return f"所有版本键都比目标新，按语义取最低键（目标 {target}）"
    if rule == "highest-key-ignored-target":
        return f"忽略目标版本 {target}，直接取版本号最大的键 {key}"
    return "无可用版本键"


# --------------------------------------------------------------------------------------
# jmp_offset 的静态信息与 targets 定位（只报告位置，不推断填充值）
# --------------------------------------------------------------------------------------

def jmp_offset_info(payload: dict, original: str) -> dict:
    """jmp_offset 的 !! / targets 静态信息：本工具不推断填充值。"""
    modified = payload.get("modified") if isinstance(payload, dict) else None
    try:
        tokens = tokenize_wildcard(modified or "", "modified")
    except ToolError:
        tokens = []
    runs = []
    i = 0
    while i < len(tokens):
        if tokens[i] == PLACEHOLDER:
            j = i
            while j < len(tokens) and tokens[j] == PLACEHOLDER:
                j += 1
            runs.append({"at": i, "length": j - i})
            i = j
        else:
            i += 1
    return {
        "originalHasPlaceholder": PLACEHOLDER in re.sub(r"\s+", "", original or ""),
        "modifiedHasPlaceholder": bool(runs),
        "modifiedPlaceholderRuns": runs,
        "modifiedPlaceholderTotal": sum(r["length"] for r in runs),
        "hasTargets": bool(payload.get("targets")) if isinstance(payload, dict) else False,
    }


def render_jmp_info(info: dict) -> str:
    runs = info["modifiedPlaceholderRuns"]
    run_text = "无" if not runs else "、".join(str(r["length"]) for r in runs)
    return (f"jmp_offset: original 含 !! = {info['originalHasPlaceholder']}；"
            f"modified 含 !! {info['modifiedPlaceholderTotal']} 个（每组长度：{run_text}）；"
            f"targets = {'有' if info['hasTargets'] else '无'}")


def report_targets(buf, targets: list) -> list:
    """逐条按带 ! 前缀锚点的语义报位置：首个命中偏移 + ! 标记偏移。

    只报位置，不计算填充值、不判 PASS/FAIL（填充是应用时按 FOA→RVA 算的）。
    """
    out = []
    for idx, text in enumerate(targets):
        item = {"index": idx, "error": None, "hitCount": None, "firstHit": None,
                "markedOffset": None, "bangIndex": None, "length": None}
        try:
            cleaned, bang = split_marked_text(text)
            pat = compile_pattern(cleaned, side="target")
            hits = find_all_pattern(buf, pat)
        except ToolError as exc:
            item["error"] = str(exc)
            out.append(item)
            continue
        first = hits[0] if hits else None
        item["hitCount"] = len(hits)
        item["firstHit"] = first
        item["bangIndex"] = bang
        item["length"] = pat.size
        if first is not None and bang is not None:
            item["markedOffset"] = first + bang
        out.append(item)
    return out


def render_targets(items: list) -> list:
    lines = []
    for it in items:
        if it["error"]:
            lines.append(f"        target#{it['index']}  无法解析：{it['error']}")
        elif it["firstHit"] is None:
            lines.append(
                f"        target#{it['index']}  未命中（长度 {it['length']} 字节）"
                f" —— 应用时对应的 !! 无法填充"
            )
        else:
            mark = ("无 ! 标记" if it["markedOffset"] is None
                    else f"! 标记偏移 = 0x{it['markedOffset']:0X}")
            lines.append(
                f"        target#{it['index']}  首个命中 = 0x{it['firstHit']:0X}  {mark}"
                f"  （长度 {it['length']}，命中 {it['hitCount']} 次）"
            )
    return lines


# --------------------------------------------------------------------------------------
# 输出小工具
# --------------------------------------------------------------------------------------

def write_json(path: str, payload: dict):
    target = os.path.abspath(path)
    parent = os.path.dirname(target)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    try:
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    except OSError as exc:
        raise ToolError(
            f"写 JSON 失败：{path}（{exc}）",
            "确认目标目录存在且可写；--json 是唯一会写盘的地方",
        )
    print(f"已写出 JSON: {target}")


def hex_bytes(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def hex_compact(data: bytes) -> str:
    return "".join(f"{b:02X}" for b in data)


def parse_addr(token: str) -> int:
    s = token.strip()
    if not s:
        raise ToolError("空的地址", "地址写成 0x1A20 这样")
    if s.lower().startswith("0x"):
        return int(s, 16)
    if re.fullmatch(r"[0-9]+", s):
        return int(s, 10)
    return int(s, 16)


def parse_region_arg(text: str, size=None):
    if text is None:
        return None
    m = re.fullmatch(r"\s*([^-\s]+)\s*-\s*([^-\s]+)\s*", text)
    if not m:
        raise ToolError(
            f"--region 格式非法：{text!r}",
            "写成 START-END，例如 --region 0x1A20-0x1B00（带 0x 或含 A-F 按十六进制，纯数字按十进制）",
        )
    start = parse_addr(m.group(1))
    end = parse_addr(m.group(2))
    if end <= start:
        raise ToolError(
            f"--region 区间非法：start=0x{start:X} end=0x{end:X}",
            "END 必须大于 START，且 END 为不含端",
        )
    if size is not None and start >= size:
        raise ToolError(
            f"--region 起点 0x{start:X} 已超出文件大小 0x{size:X}",
            "核对区间是否来自本次 diff 的输出",
        )
    return start, end


# --------------------------------------------------------------------------------------
# 子命令：diff
# --------------------------------------------------------------------------------------

def cmd_diff(args) -> int:
    t0 = time.perf_counter()
    if args.gap < 0:
        raise ToolError("--gap 不能是负数", "间隔单位是字节，例如 --gap 8")
    with MappedFile(args.fileA) as fa, MappedFile(args.fileB) as fb:
        if fa.size != fb.size:
            raise ToolError(
                f"两个文件大小不同：A={fa.size} 字节，B={fb.size} 字节，无法逐字节差分",
                "打补丁不改变文件长度，长度不同通常说明拿错了文件"
                "（比如一边是新版本原版）；请确认两边是同一版本的原版/补丁版",
            )
        regions, total = scan_diff_regions(fa.mm, fb.mm, fa.size, args.gap, args.max_positions)

        lines = []
        lines.append(f"文件A: {fa.path}  ({fa.size} 字节)")
        lines.append(f"文件B: {fb.path}  ({fb.size} 字节)")
        lines.append(f"合并间隔 gap={args.gap} 字节；共 {len(regions)} 个差异区间，{total} 个差异字节")
        lines.append("")

        to_print = regions if args.max_print <= 0 else regions[:args.max_print]
        for idx, reg in enumerate(to_print):
            lines.append(
                f"## 区间=0x{reg['start']:08X}~0x{reg['end']:08X} "
                f"长度={reg['end'] - reg['start']} 差异字节数={len(reg['positions'])}"
            )
            render_region(lines, "A", fa.path, fa.mm, reg, args.left, args.right, fa.size, True)
            render_region(lines, "B", fb.path, fb.mm, reg, args.left, args.right, fb.size, True)
            lines.append(render_byte_pairs(fa.mm, fb.mm, reg["positions"]))
            lines.append("")
            del idx
        if len(to_print) < len(regions):
            lines.append(
                f"…（还有 {len(regions) - len(to_print)} 个区间未打印；--max-print 0 可打印全部）"
            )

        elapsed = time.perf_counter() - t0
        lines.append(f"耗时={elapsed:.2f}s")
        print("\n".join(lines))

        if args.json:
            payload = {
                "fileA": fa.path,
                "fileB": fb.path,
                "size": fa.size,
                "regions": [
                    {
                        "start": r["start"],
                        "end": r["end"],
                        "diffPositions": r["positions"],
                        "aBytes": hex_compact(fa.mm[r["start"]:r["end"]]),
                        "bBytes": hex_compact(fb.mm[r["start"]:r["end"]]),
                    }
                    for r in regions
                ],
            }
            write_json(args.json, payload)
    return 0


# --------------------------------------------------------------------------------------
# 子命令：extract
# --------------------------------------------------------------------------------------

def _elide_tail(orig: bytes, mod: bytes) -> tuple:
    """把 mod 尾部与 orig 相同的连续字节截成 " ..."，返回 (省略式字符串, 截掉的字节数)。"""
    n = 0
    limit = min(len(orig), len(mod))
    while n < limit and orig[len(orig) - 1 - n] == mod[len(mod) - 1 - n]:
        n += 1
    if n == 0:
        return hex_bytes(mod), 0
    keep = mod[:len(mod) - n]
    return hex_bytes(keep) + " ...", n


def pad_to_min_window(size: int, start: int, end: int, minimum: int) -> tuple:
    """把差异本体补到至少 minimum 字节：默认两侧对称补，一侧触到文件边界时差额全挪到另一侧。

    补进来的字节都是**未变化的上下文**，目的只是让特征够长、以便在线上唯一定位。
    返回 (start, end, 左侧补的字节数, 右侧补的字节数)。
    """
    start = max(0, min(start, size))
    end = max(start, min(end, size))
    need = minimum - (end - start)
    if need <= 0:
        return start, end, 0, 0
    left = min(need // 2, start)
    right = need - left
    if right > size - end:
        right = size - end
        left = min(need - right, start)
    return start - left, end + right, left, right


def _expand_window(buf, start: int, end: int, max_window: int, pad: int = 8):
    """从给定窗口开始对称外扩，直到窗口在原文件里唯一命中或触到上限/边界。"""
    size = len(buf)
    start = max(0, min(start, size))
    end = max(start, min(end, size))
    hits = find_all_raw(buf, bytes(buf[start:end]))
    while len(hits) != 1 and (end - start) < max_window:
        new_start = max(start - pad, 0)
        new_end = min(end + pad, size)
        if (new_start, new_end) == (start, end):
            break
        start, end = new_start, new_end
        hits = find_all_raw(buf, bytes(buf[start:end]))
    return start, end, hits


def build_draft(candidates: list) -> dict:
    """把 code 类候选整理成可直接粘进 ver_adaptations 的草稿片段。

    版本键用 <VERSION> 占位；这份草稿只写进 --json 文件，本工具绝不改正式配置。
    """
    fragments = []
    for c in candidates:
        if c.get("class") != "code" or c.get("skipped"):
            continue
        fragments.append({
            "candidateIndex": c.get("index"),
            "region": f"0x{c['regionStart']:08X}~0x{c['regionEnd']:08X}",
            "diffBodySpan": c.get("diffBodySpan"),
            "window": f"0x{c['windowStart']:08X}",
            "windowLength": c.get("windowLength"),
            "minWindowPadded": c.get("minWindowPadded"),
            "minWindowPadLeft": c.get("minWindowPadLeft"),
            "minWindowPadRight": c.get("minWindowPadRight"),
            "hitCount": c["hitCount"],
            "unique": c["unique"],
            "ver_adaptations": {
                VERSION_PLACEHOLDER: {"original": c["original"], "modified": c["modified"]},
            },
        })
    return {
        "note": (f"版本键 {VERSION_PLACEHOLDER} 是占位符，粘进 ver_adaptations 前替换成目标版本号；"
                 "只包含 class=code 的候选；diffsig.py 只读，不会改动正式配置"),
        "fragments": fragments,
    }


def cmd_extract(args) -> int:
    t0 = time.perf_counter()
    if args.gap < 0:
        raise ToolError("--gap 不能是负数", "间隔单位是字节，例如 --gap 8")
    if args.max_window < 1:
        raise ToolError("--max-window 至少为 1", "默认 512 字节")
    if args.min_window < 1:
        raise ToolError("--min-window 至少为 1", f"默认 {MIN_WINDOW_DEFAULT} 字节")
    if args.min_window > args.max_window:
        raise ToolError(
            f"--min-window ({args.min_window}) 不能大于 --max-window ({args.max_window})",
            "最小窗口是长度下限、唯一化上限是外扩上界；把 --max-window 调大或 --min-window 调小",
        )
    with MappedFile(args.fileA) as fa, MappedFile(args.fileB) as fb:
        if fa.size != fb.size:
            raise ToolError(
                f"两个文件大小不同：A={fa.size} 字节，B={fb.size} 字节，无法提炼特征码对",
                "打补丁不改变文件长度；请确认两边是同一版本的原版/补丁版",
            )
        regions, total = scan_diff_regions(fa.mm, fb.mm, fa.size, args.gap, args.max_positions)

        lines = []
        lines.append(f"文件A: {fa.path}  ({fa.size} 字节)")
        lines.append(f"文件B: {fb.path}  ({fb.size} 字节)")
        lines.append(
            f"合并间隔 gap={args.gap} 字节；共 {len(regions)} 个差异区间，{total} 个差异字节；"
            f"最小窗口 --min-window={args.min_window} 字节；"
            f"窗口唯一化上限 --max-window={args.max_window} 字节"
        )
        lines.append("")

        candidates = []
        skipped_strings = 0
        kind_counts = {k: 0 for k in CLASS_KINDS}
        for idx, reg in enumerate(regions):
            body_start, body_end = reg["start"], reg["end"]
            body = bytes(fa.mm[body_start:body_end])
            min_start, min_end, pad_left, pad_right = pad_to_min_window(
                fa.size, body_start, body_end, args.min_window)
            w_start, w_end, hits = _expand_window(fa.mm, min_start, min_end, args.max_window)
            unique = len(hits) == 1
            padded = (min_start, min_end) != (body_start, body_end)
            expanded = (w_start, w_end) != (min_start, min_end)
            orig = bytes(fa.mm[w_start:w_end])
            mod = bytes(fb.mm[w_start:w_end])
            diff_count = sum(1 for i in range(len(orig)) if orig[i] != mod[i])
            elided, cut = _elide_tail(orig, mod)
            cls = classify_window(body, subject="差异本体")   # 分类只用差异本体
            win_cls = classify_window(orig)                   # 窗口整体分类只作参考
            kind_counts[cls["kind"]] += 1
            note = ""
            if not unique:
                if w_end - w_start >= args.max_window:
                    note = f"无法唯一化：窗口已达上限 {args.max_window} 字节仍有 {len(hits)} 次命中"
                else:
                    note = f"无法唯一化：窗口已触文件边界仍有 {len(hits)} 次命中"
            skipped = bool(args.skip_strings and cls["kind"] == "string")
            candidates.append({
                "index": idx,
                "regionStart": body_start,
                "regionEnd": body_end,
                "diffBodySpan": {"start": body_start, "length": body_end - body_start},
                "minWindow": args.min_window,
                "minWindowPadded": padded,
                "minWindowPadLeft": pad_left,
                "minWindowPadRight": pad_right,
                "paddedLength": min_end - min_start,
                "uniqueExpanded": expanded,
                "windowStart": w_start,
                "windowLength": w_end - w_start,
                "class": cls["kind"],
                "classBasis": "diff-body",
                "classWhy": cls["why"],
                "windowClass": win_cls["kind"],
                "windowTextRatio": win_cls["textRatio"],
                "classMetrics": {
                    "textRatio": cls["textRatio"],
                    "asciiRatio": cls["asciiRatio"],
                    "utf16Ratio": cls["utf16Ratio"],
                    "instrHitCount": cls["instrHitCount"],
                    "instrHits": cls["instrHits"],
                },
                "original": hex_bytes(orig),
                "modified": hex_bytes(mod),
                "modifiedElided": elided,
                "diffCount": diff_count,
                "hitCount": len(hits),
                "unique": unique,
                "skipped": skipped,
                "note": note,
            })
            body_len = body_end - body_start
            if padded:
                origin_desc = (
                    f"被最小窗口撑开到 {min_end - min_start} 字节"
                    f"（左侧补 {pad_left} 字节、右侧补 {pad_right} 字节）"
                    " —— 撑进来的字节都是未变化的上下文，只为让特征够长、可在线上唯一定位"
                )
                if (min_end - min_start) < args.min_window:
                    origin_desc += (f"；注意窗口已触文件边界，只能补到 {min_end - min_start} 字节"
                                    f"（不足 --min-window={args.min_window}）")
            else:
                origin_desc = f"差异本体（{body_len} 字节，已 >= --min-window={args.min_window}，未撑开）"
            if expanded:
                origin_desc += f"；为在 fileA 里唯一定位又外扩到 {w_end - w_start} 字节"

            lines.append(
                f"## 候选#{idx} 差异本体=0x{body_start:08X} 长度={body_len} "
                f"差异字节数={len(reg['positions'])} 分类={cls['kind']}（分类依据=差异本体）"
            )
            if skipped:
                skipped_strings += 1
                lines.append(f"   已跳过：{cls['why']}（加 --include-strings 可显示）")
                lines.append("")
                continue
            lines.append(
                f"   窗口偏移=0x{w_start:08X} 窗口长度={w_end - w_start} "
                f"窗口内差异字节数={diff_count} 在 fileA 命中次数={len(hits)}"
                + ("" if unique else "  <-- " + note)
            )
            lines.append(f"   窗口来源: {origin_desc}")
            lines.append(
                f"   分类依据: {cls['why']}（只用差异本体 {body_len} 字节判断；"
                f"窗口整体文本占比 {win_cls['textRatio']:.2f} 仅为参考，撑开的上下文不参与分类）"
            )
            lines.append(f"   original = {hex_bytes(orig)}")
            lines.append(f"   modified = {hex_bytes(mod)}（与 original 等长、不含通配）")
            if cut:
                lines.append(
                    f"   modified(省略式) = {elided}"
                    f"（尾部 {cut} 字节与 original 相同，与上面的完整式等价）"
                )
            else:
                lines.append("   modified(省略式) = 与完整式相同（尾部没有与 original 相同的字节可省）")
            lines.append("")

        if skipped_strings:
            lines.append(
                f"已跳过 {skipped_strings} 个疑似字符串区间（品牌改名/URL 替换之类，与打补丁点无关）；"
                f"需要的话加 --include-strings"
            )
        lines.append(
            f"分类统计：code {kind_counts['code']} / string {kind_counts['string']} "
            f"/ unknown {kind_counts['unknown']}"
        )
        draft = build_draft(candidates)
        if not args.json:
            if draft["fragments"]:
                lines.append(
                    f"提示：加 --json <路径> 可把 {len(draft['fragments'])} 条 code 候选的 ver_adaptations "
                    f"草稿片段（draft）写出来"
                )
            else:
                lines.append("提示：本次没有 code 类候选，草稿片段为空")

        elapsed = time.perf_counter() - t0
        lines.append(f"耗时={elapsed:.2f}s")
        print("\n".join(lines))

        if args.json:
            payload = {
                "fileA": fa.path,
                "fileB": fb.path,
                "size": fa.size,
                "skipStrings": bool(args.skip_strings),
                "classSummary": kind_counts,
                "regions": [
                    {
                        "start": r["start"],
                        "end": r["end"],
                        "diffPositions": r["positions"],
                        "aBytes": hex_compact(fa.mm[r["start"]:r["end"]]),
                        "bBytes": hex_compact(fb.mm[r["start"]:r["end"]]),
                    }
                    for r in regions
                ],
                "candidates": candidates,
                "draft": draft,
            }
            write_json(args.json, payload)
            if draft["fragments"]:
                print(
                    f"草稿片段已写入 {args.json}（{len(draft['fragments'])} 条 code 候选，"
                    f"版本键用 {VERSION_PLACEHOLDER} 占位；本工具不改正式配置）"
                )
            else:
                print(f"草稿片段已写入 {args.json}（没有 code 类候选，draft.fragments 为空）")
    return 0


# --------------------------------------------------------------------------------------
# 子命令：locate
# --------------------------------------------------------------------------------------

def cmd_locate(args) -> int:
    t0 = time.perf_counter()
    if not (0.0 <= args.max_mismatch_ratio <= 1.0):
        raise ToolError(
            "--max-mismatch-ratio 必须在 0.0~1.0 之间",
            "默认 0.15 表示允许 15/100 的确定字节不一致；0 表示必须全中",
        )
    if args.top < 1:
        raise ToolError("--top 至少为 1", "默认 5")
    pat = compile_pattern(args.pattern, side="original")
    if pat.size == 0:
        raise ToolError("--pattern 是空的", "传一条带 ?? 的旧 original")
    det_total = sum(1 for t in pat.tokens if t is not None)
    segments = segments_of(pat.tokens)
    anchors, short_segments = locate_anchors(pat.tokens)
    if not anchors:
        raise ToolError(
            f"模式里没有任何长度 >= {MIN_ANCHOR} 的连续确定字节段，无法定位",
            f"旧 original 至少要有一段连续 {MIN_ANCHOR} 个确定字节；把模式写长一点再试",
        )

    with MappedFile(args.file) as mf:
        region = parse_region_arg(args.region, mf.size)
        exact_hits = find_all_pattern(mf.mm, pat)
        cands, truncated = locate_candidates(mf.mm, pat, anchors)
        accepted = [c for c in cands if c["ratio"] <= args.max_mismatch_ratio]
        rejected = len(cands) - len(accepted)
        to_show = accepted[:args.top]

        lines = []
        lines.append(f"文件: {mf.path}  ({mf.size} 字节)")
        lines.append(
            f"模式: {pat.to_text()}（长度={pat.size} 字节，确定位={det_total}，"
            f"通配={pat.size - det_total}）"
        )
        lines.append(
            f"锚点 = {len(anchors)} 个（{LOCATE_ANCHOR_WIDTH} 字节滑窗，步进 {LOCATE_ANCHOR_SLIDE}，"
            f"取自 {len(segments)} 个确定字节段；长锚点优先）"
        )
        for i, (off, b) in enumerate(anchors[:LOCATE_CHUNK_PRINT]):
            lines.append(f"  #{i} 模式偏移=0x{off:0X} 长{len(b)} = {hex_bytes(b)}")
        if len(anchors) > LOCATE_CHUNK_PRINT:
            lines.append(f"  …（其余 {len(anchors) - LOCATE_CHUNK_PRINT} 个略）")
        if short_segments:
            shown = "、".join(f"0x{o:0X}({n}B)" for o, n in short_segments[:8])
            lines.append(f"  跳过 {len(short_segments)} 个过短的确定字节段：{shown}")
        if exact_hits:
            shown = "、".join(f"0x{h:0X}" for h in exact_hits[:HIT_PRINT_LIMIT])
            lines.append(
                f"严格命中: {len(exact_hits)} 处（{shown}）"
                f" —— 原模式其实还能扫到，locate 只在已失效时才有意义"
            )
        else:
            lines.append("严格命中: 0 处（旧特征已不再精确命中，下面按「最像」排序）")
        lines.append(f"阈值: 不匹配比例 <= {args.max_mismatch_ratio:.4f} 视为「可能是同一处」")
        lines.append(
            f"候选约束: 命中的锚点 >= {min(2, len(anchors))} 个（单锚点巧合直接丢弃）"
        )
        if truncated:
            lines.append(
                f"注意: 满足约束的候选超过 {LOCATE_MAX_CANDIDATES} 个，只保留了比例最小的那些"
            )
        lines.append("")

        for i, c in enumerate(to_show, 1):
            lines.append(
                f"## 候选 #{i}  文件偏移=0x{c['offset']:08X} "
                f"不匹配={c['mismatchCount']}/{det_total} ({c['ratio'] * 100:.2f}%) "
                f"命中锚点={c['matchedAnchors']}/{len(anchors)}"
            )
            if region is not None:
                in_region = region[0] <= c["offset"] < region[1]
                lines.append(
                    f"   落在区间 0x{region[0]:08X}~0x{region[1]:08X} 内 = {in_region}"
                )
            if c["mismatches"]:
                items = [
                    f"模式#{k} 期望={exp:02X} 实际={act:02X}（文件 0x{c['offset'] + k:08X}）"
                    for k, exp, act in c["mismatches"][:MISMATCH_PRINT_LIMIT]
                ]
                tail = ("" if len(c["mismatches"]) <= MISMATCH_PRINT_LIMIT
                        else f" …（共 {len(c['mismatches'])} 处）")
                lines.append("   不匹配位置: " + "；".join(items) + tail)
            else:
                lines.append("   不匹配位置: 无（确定字节全中；?? 位置无从判断）")
            lines.append("")

        hint = ("提示: 可能是目标处的代码被整体改写、或前后挪了字节数（插入/删除导致整体位移），"
                "自动定位不可靠，需要人工汇编写特征（IDA/x64dbg 里按调用点/引用链定位后再差分）。")
        if not accepted:
            lines.append("没有任何候选满足锚点约束。")
            if cands:
                lines.append(
                    f"（找到 {len(cands)} 个锚点候选，但最小不匹配比例 "
                    f"{cands[0]['ratio'] * 100:.2f}% 已超过阈值 "
                    f"{args.max_mismatch_ratio * 100:.2f}%，大概率不是同一处代码）"
                )
                for c in cands[:min(3, args.top)]:
                    lines.append(
                        f"  参考: 0x{c['offset']:08X} 不匹配={c['mismatchCount']}/{det_total} "
                        f"({c['ratio'] * 100:.2f}%)"
                    )
                relaxed = min(1.0, round(cands[0]["ratio"] + 0.005, 4))
                lines.append(f"  若想放宽再看，加 --max-mismatch-ratio {relaxed}")
            else:
                lines.append("（锚点在文件里一次都没出现，连候选起点都没有）")
            lines.append(hint)
        else:
            lines.append(
                f"共 {len(accepted)} 个候选在阈值内（另有 {rejected} 个超阈值未列出），"
                f"已按不匹配比例升序取前 {len(to_show)} 个。"
            )
            if len(accepted) > 1:
                lines.append(
                    "提示: 多个候选都在阈值内时不要只看第一个 —— 结合 --region 与调用点上下文判断哪处才是同一段代码。"
                )
        elapsed = time.perf_counter() - t0
        lines.append(f"耗时={elapsed:.2f}s")
        print("\n".join(lines))

        if args.json:
            write_json(args.json, {
                "file": mf.path,
                "size": mf.size,
                "pattern": pat.to_text(),
                "patternLength": pat.size,
                "determinateCount": det_total,
                "region": list(region) if region else None,
                "maxMismatchRatio": args.max_mismatch_ratio,
                "top": args.top,
                "segments": [{"offset": o, "length": ln} for o, ln in segments],
                "anchorWidth": LOCATE_ANCHOR_WIDTH,
                "anchorSlide": LOCATE_ANCHOR_SLIDE,
                "anchors": [
                    {"index": i, "offset": o, "length": len(b), "bytes": hex_compact(b)}
                    for i, (o, b) in enumerate(anchors)
                ],
                "skippedShortSegments": [{"offset": o, "length": n} for o, n in short_segments],
                "exactHitCount": len(exact_hits),
                "exactHits": exact_hits[:HIT_PRINT_LIMIT],
                "candidates": [
                    {
                        "offset": c["offset"],
                        "mismatchCount": c["mismatchCount"],
                        "determinateCount": det_total,
                        "ratio": round(c["ratio"], 6),
                        "matchedAnchors": c["matchedAnchors"],
                        "inRegion": (None if region is None
                                     else region[0] <= c["offset"] < region[1]),
                        "mismatches": [
                            {
                                "patternIndex": k,
                                "expected": f"{exp:02X}",
                                "actual": f"{act:02X}",
                                "fileOffset": c["offset"] + k,
                            }
                            for k, exp, act in c["mismatches"]
                        ],
                    }
                    for c in to_show
                ],
                "acceptedCount": len(accepted),
                "rejectedCount": rejected,
                "truncated": truncated,
                "summary": {
                    "exactHits": len(exact_hits),
                    "anchorCandidates": len(cands),
                    "accepted": len(accepted),
                    "rejected": rejected,
                },
            })
    return 0


# --------------------------------------------------------------------------------------
# 子命令：check
# --------------------------------------------------------------------------------------

def _load_config(path: str) -> dict:
    if not os.path.exists(path):
        raise ToolError(
            f"配置文件不存在：{path}",
            "默认读 scripts/original_remote_sw_v10.json；用 --config 指定别的路径",
        )
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ToolError(f"配置文件不是合法 JSON：{path}（{exc}）", "检查文件是否被截断或编码损坏")
    if not isinstance(data, dict):
        raise ToolError(f"配置文件顶层应为对象：{path}", "确认用的是特征库文件而不是别的 json")
    return data


def _pick(mapping: dict, key: str, what: str, path: str):
    if key in mapping:
        return mapping[key]
    avail = "、".join(list(mapping.keys())[:12])
    more = "" if len(mapping) <= 12 else f" …（共 {len(mapping)} 个）"
    raise ToolError(
        f"配置里找不到{what} {key!r}（{path}）",
        f"可用的{what}：{avail}{more}；核对拼写后再试",
    )


def navigate_channel(config_path: str, sw_key: str, mode_key: str, channel_key: str) -> dict:
    """按 平台 -> 模式 -> channels -> 渠道 导航，返回渠道节点。"""
    cfg = _load_config(config_path)
    sw = _pick(cfg, sw_key, "平台", config_path)
    if not isinstance(sw, dict):
        raise ToolError(f"平台 {sw_key} 不是对象", "确认配置结构为 平台 -> 模式 -> channels -> 渠道")
    mode = _pick(sw, mode_key, "模式", config_path)
    if not isinstance(mode, dict):
        raise ToolError(f"模式 {sw_key}/{mode_key} 不是对象", "确认该模式下有 channels 节点")
    channels = mode.get("channels")
    if not isinstance(channels, dict):
        raise ToolError(
            f"模式 {sw_key}/{mode_key} 下没有 channels",
            "确认配置结构；本工具只读，不会改动配置",
        )
    channel = _pick(channels, channel_key, "渠道", config_path)
    if not isinstance(channel, dict):
        raise ToolError(
            f"渠道 {sw_key}/{mode_key}/{channel_key} 不是对象",
            "确认渠道节点结构为 features[] -> patch_rules[]",
        )
    return channel


def pick_feature_rule(channel: dict, feature_idx: int, rule_idx: int) -> dict:
    """从渠道节点里取第 feature_idx 个 feature 的第 rule_idx 条规则。"""
    features = channel.get("features")
    if not isinstance(features, list) or not features:
        raise ToolError("该渠道没有 features 数组或为空", "换一个渠道；或先确认配置结构")
    if not (0 <= feature_idx < len(features)):
        raise ToolError(
            f"feature 下标 {feature_idx} 越界（该渠道共 {len(features)} 个 feature）",
            "下标从 0 开始；先跑 check 看输出里的 feature# 编号",
        )
    feature = features[feature_idx]
    rules = feature.get("patch_rules") if isinstance(feature, dict) else None
    if not isinstance(rules, list) or not rules:
        raise ToolError(
            f"feature#{feature_idx} 没有 patch_rules",
            "换一个 feature 下标；纯 wildcard 规则本工具不处理",
        )
    if not (0 <= rule_idx < len(rules)):
        raise ToolError(
            f"rule 下标 {rule_idx} 越界（feature#{feature_idx} 共 {len(rules)} 条规则）",
            "下标从 0 开始；先跑 check 看输出里的 rule# 编号",
        )
    return rules[rule_idx]


def type_skip_reason(rtype) -> str:
    if rtype in TYPE_SKIP_REASONS:
        return TYPE_SKIP_REASONS[rtype]
    return (f"类型 {rtype} 不是 simple/custom/jmp_offset，本工具不扫描"
            f"（只扫描带 original 的 simple / custom / jmp_offset）")


def cmd_check(args) -> int:
    t0 = time.perf_counter()
    region = parse_region_arg(args.region)
    channel = navigate_channel(args.config, args.sw, args.mode, args.channel)
    features = channel.get("features")
    if not isinstance(features, list):
        raise ToolError(
            f"渠道 {args.sw}/{args.mode}/{args.channel} 下没有 features 数组",
            "确认配置结构；空数组表示该渠道暂无规则",
        )

    lines = []
    lines.append(f"配置: {os.path.abspath(args.config)}")
    lines.append(f"平台={args.sw} 模式={args.mode} 渠道={args.channel} 目标版本={args.ver}")
    lines.append(
        f"选键模式 = {args.key}"
        f"（{'latest：忽略目标版本，直接取版本号最大的键' if args.key == 'latest' else 'selected：按 findCompatibleVersion 语义选键'}）"
    )
    if region is not None:
        lines.append(f"限定区间: 0x{region[0]:08X}~0x{region[1]:08X}（END 不含）")
    lines.append("")

    results = []
    counts = {"pass": 0, "multi": 0, "fail": 0, "skip": 0}

    mapped = None
    try:
        if args.file:
            mapped = MappedFile(args.file)
            lines.insert(3, f"文件: {mapped.path}  ({mapped.size} 字节)")
        else:
            lines.insert(3, "文件: （未提供 --file，只做版本键选择，不扫描）")

        rule_no = 0
        for feat_idx, feature in enumerate(features):
            if not isinstance(feature, dict):
                continue
            addr = feature.get("addr", "")
            rules = feature.get("patch_rules")
            if not isinstance(rules, list) or not rules:
                rule_no += 1
                counts["skip"] += 1
                results.append({
                    "featureIndex": feat_idx, "ruleIndex": None, "type": None,
                    "addr": addr, "versionKey": None, "versionRule": None,
                    "status": "SKIP", "reason": "该 feature 没有 patch_rules（可能是纯 wildcard 规则，本工具未处理）",
                    "hitCount": None, "hits": [], "inRegion": None,
                })
                lines.append(f"[规则 {rule_no}] feature#{feat_idx} addr={addr} 无 patch_rules -> SKIP")
                lines.append("")
                continue

            for r_idx, rule in enumerate(rules):
                if not isinstance(rule, dict):
                    continue
                rule_no += 1
                rtype = rule.get("type")
                va = rule.get("ver_adaptations")
                head = f"[规则 {rule_no}] feature#{feat_idx} rule#{r_idx} type={rtype} addr={addr}"
                lines.append(head)

                if not isinstance(va, dict) or not va:
                    counts["skip"] += 1
                    results.append({
                        "featureIndex": feat_idx, "ruleIndex": r_idx, "type": rtype, "addr": addr,
                        "versionKey": None, "versionRule": None, "status": "SKIP",
                        "reason": "没有 ver_adaptations", "hitCount": None, "hits": [], "inRegion": None,
                    })
                    lines.append("      SKIP  没有 ver_adaptations，无法选版本键")
                    lines.append("")
                    continue

                key, rule_kind, key_is_null = select_version_key(va, args.ver, args.key)
                if key is None:
                    counts["skip"] += 1
                    results.append({
                        "featureIndex": feat_idx, "ruleIndex": r_idx, "type": rtype, "addr": addr,
                        "versionKey": None, "versionRule": rule_kind, "status": "SKIP",
                        "reason": "ver_adaptations 为空", "hitCount": None, "hits": [], "inRegion": None,
                    })
                    lines.append("      SKIP  ver_adaptations 为空")
                    lines.append("")
                    continue
                lines.append(f"      选中的版本键 = {key}（{version_rule_text(rule_kind, args.ver, key)}）")
                lines.append(f"      该键的值 = {describe_version_value(va.get(key))}")

                if rtype not in SUPPORTED_TYPES:
                    counts["skip"] += 1
                    results.append({
                        "featureIndex": feat_idx, "ruleIndex": r_idx, "type": rtype, "addr": addr,
                        "versionKey": key, "versionRule": rule_kind, "status": "SKIP",
                        "reason": type_skip_reason(rtype),
                        "hitCount": None, "hits": [], "inRegion": None, "keyIsNull": key_is_null,
                    })
                    lines.append(f"      SKIP  {type_skip_reason(rtype)}")
                    lines.append("")
                    continue

                payload = va.get(key)
                if payload is None:
                    counts["skip"] += 1
                    results.append({
                        "featureIndex": feat_idx, "ruleIndex": r_idx, "type": rtype, "addr": addr,
                        "versionKey": key, "versionRule": rule_kind, "status": "SKIP",
                        "reason": "该版本键的值为 null（该版本弃用此规则）",
                        "hitCount": None, "hits": [], "inRegion": None, "keyIsNull": True,
                    })
                    lines.append(f"      SKIP  版本键 {key} 的值为 null —— 该版本弃用此规则")
                    lines.append("")
                    continue

                original = payload.get("original") if isinstance(payload, dict) else None
                if not original:
                    counts["skip"] += 1
                    results.append({
                        "featureIndex": feat_idx, "ruleIndex": r_idx, "type": rtype, "addr": addr,
                        "versionKey": key, "versionRule": rule_kind, "status": "SKIP",
                        "reason": "该版本键没有 original", "hitCount": None, "hits": [], "inRegion": None,
                    })
                    lines.append("      SKIP  该版本键没有 original 字段")
                    lines.append("")
                    continue

                lines.append(f"      original = {original}")
                jmp_info = None
                if rtype == "jmp_offset":
                    jmp_info = jmp_offset_info(payload, original)
                    lines.append(f"      {render_jmp_info(jmp_info)}")
                    if jmp_info["modifiedPlaceholderRuns"]:
                        lines.append(
                            f"                  说明：modified 里 {jmp_info['modifiedPlaceholderTotal']} 个 !! "
                            f"需要在应用时按 targets 的命中地址 + FOA→RVA 填 4 字节小端，本工具不推断填充值"
                        )
                if mapped is None:
                    counts["skip"] += 1
                    results.append({
                        "featureIndex": feat_idx, "ruleIndex": r_idx, "type": rtype, "addr": addr,
                        "versionKey": key, "versionRule": rule_kind, "status": "SKIP",
                        "reason": "未提供 --file，未扫描", "original": original,
                        "hitCount": None, "hits": [], "inRegion": None,
                    })
                    lines.append("      SKIP  未提供 --file，未扫描")
                    lines.append("")
                    continue

                try:
                    pat = compile_pattern(original, side="original")
                    hits = find_all_pattern(mapped.mm, pat)
                except ToolError as exc:
                    counts["fail"] += 1
                    results.append({
                        "featureIndex": feat_idx, "ruleIndex": r_idx, "type": rtype, "addr": addr,
                        "versionKey": key, "versionRule": rule_kind, "status": "FAIL",
                        "reason": f"特征码无法扫描：{exc}", "original": original,
                        "hitCount": None, "hits": [], "inRegion": None, "keyIsNull": key_is_null,
                        "jmpOffset": jmp_info,
                    })
                    lines.append(f"      FAIL  特征码无法扫描：{exc}")
                    if exc.hint:
                        lines.append(f"             建议：{exc.hint}")
                    lines.append("")
                    continue

                in_region = None
                if region is not None:
                    in_region = any(region[0] <= h < region[1] for h in hits)
                    lines.append(
                        f"      限定区间内命中 = {sum(1 for h in hits if region[0] <= h < region[1])}"
                    )

                status = "PASS"
                reason = ""
                if len(hits) == 0:
                    status = "FAIL"
                    reason = "0 命中"
                elif len(hits) > 1:
                    status = "PASS?"
                    reason = "多重命中（有误打风险）"
                elif region is not None and not in_region:
                    status = "FAIL"
                    reason = "唯一命中不在指定区间内"

                if status == "PASS":
                    counts["pass"] += 1
                elif status == "PASS?":
                    counts["multi"] += 1
                else:
                    counts["fail"] += 1

                shown = hits[:HIT_PRINT_LIMIT]
                hit_text = "、".join(f"0x{h:0X}" for h in shown) if shown else "（无）"
                if len(hits) > HIT_PRINT_LIMIT:
                    hit_text += f" …（共 {len(hits)} 处）"
                label = {"PASS": "PASS ", "PASS?": "PASS?", "FAIL": "FAIL "}[status]
                line = f"      {label} 命中次数={len(hits)} 前几个命中={hit_text}"
                if reason:
                    line += f"  -> {reason}"
                if region is not None:
                    line += f"  区间内命中={in_region}"
                lines.append(line)

                target_reports = None
                if rtype == "jmp_offset" and isinstance(payload, dict):
                    targets = payload.get("targets")
                    if isinstance(targets, list) and targets:
                        target_reports = report_targets(mapped.mm, targets)
                        lines.append("      targets 锚点（只报命中位置，不计算填充值、不判 PASS/FAIL）：")
                        lines.extend(render_targets(target_reports))
                    else:
                        lines.append("      targets = 无（该版本不需要填充 !!）")
                lines.append("")

                results.append({
                    "featureIndex": feat_idx,
                    "ruleIndex": r_idx,
                    "type": rtype,
                    "addr": addr,
                    "versionKey": key,
                    "versionRule": rule_kind,
                    "keyIsNull": key_is_null,
                    "status": status,
                    "reason": reason,
                    "original": original,
                    "hitCount": len(hits),
                    "hits": shown,
                    "inRegion": in_region,
                    "jmpOffset": jmp_info,
                    "targets": target_reports,
                })
    finally:
        if mapped is not None:
            mapped.close()

    summary = (
        f"汇总：共 {rule_no} 条规则：PASS {counts['pass']} / 多重命中 {counts['multi']} "
        f"/ FAIL {counts['fail']} / SKIP {counts['skip']}"
    )
    elapsed = time.perf_counter() - t0
    lines.append(summary)
    lines.append(f"耗时={elapsed:.2f}s")
    print("\n".join(lines))

    if args.json:
        key_summary = {}
        for r in results:
            if r.get("versionKey"):
                key_summary.setdefault((r.get("featureIndex"), r.get("ruleIndex")), r["versionKey"])
        write_json(args.json, {
            "config": os.path.abspath(args.config),
            "sw": args.sw,
            "mode": args.mode,
            "channel": args.channel,
            "ver": args.ver,
            "keyMode": args.key,
            "file": os.path.abspath(args.file) if args.file else None,
            "size": mapped.size if mapped is not None else None,
            "region": list(region) if region else None,
            "selectedVersionKeys": [
                {"featureIndex": k[0], "ruleIndex": k[1], "versionKey": v}
                for k, v in key_summary.items()
            ],
            "rules": results,
            "summary": {
                "total": rule_no,
                "pass": counts["pass"],
                "multi": counts["multi"],
                "fail": counts["fail"],
                "skip": counts["skip"],
            },
        })
    return 0


# --------------------------------------------------------------------------------------
# 子命令：match
# --------------------------------------------------------------------------------------

def _original_preview(original: str, limit: int = MATCH_ORIGINAL_PREVIEW) -> str:
    """规则 original 的前 limit 个字节（人眼核对用）。"""
    toks = str(original).split()
    head = " ".join(toks[:limit])
    if len(toks) > limit:
        return f"{head} …（全 {len(toks)} 字节）"
    return f"{head}（全 {len(toks)} 字节）"


def load_regions_from_json(path: str) -> list:
    """从 extract --json 的产物里取差异区间（优先 regions[]，退到 candidates[] 的 regionStart/End）。"""
    if not os.path.exists(path):
        raise ToolError(f"--regions 指向的文件不存在：{path}", "先用 extract --json <路径> 生成它")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ToolError(
            f"--regions 的文件不是合法 JSON：{path}（{exc}）",
            "确认它就是 extract --json 写出的那个文件",
        )
    items = []
    if isinstance(data, dict):
        for r in (data.get("regions") or []):
            if isinstance(r, dict) and isinstance(r.get("start"), int) and isinstance(r.get("end"), int):
                items.append((r["start"], r["end"], "--regions(regions[])"))
        if not items:
            for c in (data.get("candidates") or []):
                if (isinstance(c, dict) and isinstance(c.get("regionStart"), int)
                        and isinstance(c.get("regionEnd"), int)):
                    items.append((c["regionStart"], c["regionEnd"], "--regions(candidates[])"))
    elif isinstance(data, list):
        for r in data:
            if isinstance(r, dict) and isinstance(r.get("start"), int) and isinstance(r.get("end"), int):
                items.append((r["start"], r["end"], "--regions(数组)"))
    if not items:
        raise ToolError(
            f"--regions 的文件里找不到区间：{path}",
            "期望 extract --json 产物的 regions[].start/end 或 candidates[].regionStart/regionEnd",
        )
    return items


def collect_match_rules(channel: dict, ver, key_mode: str) -> tuple:
    """按 --key 语义把渠道下所有可扫描规则的 original 收成候选规则列表。

    返回 (条目列表, 统计字典, 跳过原因计数)。同一条规则在 any 模式下可能命中多个版本键，
    original 字节完全相同的键只入队一次（当前键留在 item 上，其余记进 keysAlso），
    否则 top-N 会被同一条规则的多份拷贝挤满，看不到别的规则。
    """
    features = channel.get("features")
    if not isinstance(features, list):
        raise ToolError("该渠道下没有 features 数组", "确认配置结构为 features[] -> patch_rules[]")
    entries = []
    skips = {}
    stat = {"featureCount": 0, "ruleCount": 0, "entryCount": 0, "dedupedKeys": 0}

    def skip(reason: str):
        skips[reason] = skips.get(reason, 0) + 1

    for fi, feature in enumerate(features):
        if not isinstance(feature, dict):
            continue
        stat["featureCount"] += 1
        addr = feature.get("addr", "")
        rules = feature.get("patch_rules")
        if not isinstance(rules, list) or not rules:
            skip("该 feature 没有 patch_rules（纯 wildcard 规则）")
            continue
        for ri, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue
            stat["ruleCount"] += 1
            rtype = rule.get("type")
            va = rule.get("ver_adaptations")
            if rtype not in SUPPORTED_TYPES:
                skip(f"类型 {rtype} 不支持扫描（只扫 simple/custom/jmp_offset）")
                continue
            if not isinstance(va, dict) or not va:
                skip("没有 ver_adaptations")
                continue
            if key_mode == "any":
                keys = sorted(va.keys(), key=functools.cmp_to_key(compare_ver_asc), reverse=True)
                picks = [(k, "any-all-keys") for k in keys]
            else:
                key, key_rule, _is_null = select_version_key(va, ver, key_mode)
                picks = [] if key is None else [(key, key_rule)]
            by_text = {}
            for key, key_rule in picks:
                payload = va.get(key)
                if payload is None:
                    skip(f"版本键 {key} 的值为 null（该版本弃用此规则）")
                    continue
                original = payload.get("original") if isinstance(payload, dict) else None
                if not original:
                    skip(f"版本键 {key} 没有 original")
                    continue
                norm = re.sub(r"\s+", "", str(original)).upper()
                if norm in by_text:
                    by_text[norm]["keysAlso"].append(key)
                    stat["dedupedKeys"] += 1
                    continue
                ent = {
                    "featureIndex": fi,
                    "ruleIndex": ri,
                    "type": rtype,
                    "addr": addr,
                    "key": key,
                    "keyRule": key_rule,
                    "keysAlso": [],
                    "original": str(original),
                    "originalNorm": norm,
                }
                by_text[norm] = ent
                entries.append(ent)
    stat["entryCount"] = len(entries)
    return entries, stat, skips


def scan_match_patterns(buf, entries: list) -> dict:
    """每条不重复的 original 全文件只扫一次：{norm: {hits, error, pattern, anchors, determinate}}。"""
    cache = {}
    for ent in entries:
        norm = ent["originalNorm"]
        if norm in cache:
            continue
        item = {"hits": [], "error": None, "pattern": None, "anchors": [], "determinate": 0}
        try:
            pat = compile_pattern(ent["original"], side="original")
            item["pattern"] = pat
            item["determinate"] = sum(1 for t in pat.tokens if t is not None)
            item["hits"] = find_all_pattern(buf, pat)
            item["anchors"], _short = locate_anchors(pat.tokens)
        except ToolError as exc:
            item["error"] = str(exc)
        cache[norm] = item
    return cache


def fuzzy_in_span(buf, pat: Pattern, anchors: list, lo: int, hi: int, span: int) -> tuple:
    """在 [lo, hi) 内用锚点滑窗找最像的起点，返回 (候选 dict 或 None, 原因)。"""
    size = len(buf)
    lo = max(0, min(lo, size))
    hi = max(lo, min(hi, size))
    if not anchors:
        return None, f"模式没有长度 >= {MIN_ANCHOR} 的连续确定字节段，无法模糊匹配"
    if hi - lo < pat.size:
        return None, f"搜索范围 {hi - lo} 字节比模式 {pat.size} 字节还短"
    cands, _truncated = locate_candidates(bytes(buf[lo:hi]), pat, anchors)
    if not cands:
        return None, f"区间 ±{span} 内没有任何锚点候选（该规则在这段附近没出现过）"
    best = dict(cands[0])
    best["offset"] += lo
    return best, ""


def _region_distance(offset: int, region_start: int, region_end: int) -> int:
    if offset < region_start:
        return region_start - offset
    if offset >= region_end:
        return offset - region_end
    return 0


def match_region(region_start: int, region_end: int, entries: list, cache: dict,
                 buf, span: int) -> list:
    """对每条候选规则给出该区间上的最佳证据，并按 精确(区间内) > 精确(区间外) > 模糊 > 无 排序。"""
    rows = []
    for ent in entries:
        scan = cache[ent["originalNorm"]]
        row = {
            "featureIndex": ent["featureIndex"],
            "ruleIndex": ent["ruleIndex"],
            "type": ent["type"],
            "addr": ent["addr"],
            "key": ent["key"],
            "keysAlso": ent["keysAlso"],
            "original": ent["original"],
            "originalPreview": _original_preview(ent["original"]),
            "patternLength": scan["pattern"].size if scan["pattern"] else None,
            "determinateCount": scan["determinate"],
            "hitCount": len(scan["hits"]),
            "hits": scan["hits"][:HIT_PRINT_LIMIT],
            "method": "none",
            "reason": "",
            "evidence": "",
            "exactHits": [],
            "inRegionHits": [],
            "nearestHit": None,
            "distance": None,
            "fuzzy": None,
        }
        if scan["error"]:
            row["reason"] = f"特征码无法扫描：{scan['error']}"
            row["evidence"] = row["reason"]
            rows.append(row)
            continue
        hits = scan["hits"]
        inside = [h for h in hits if region_start <= h < region_end]
        if inside:
            row["method"] = "exact-in-region"
            row["inRegionHits"] = inside[:HIT_PRINT_LIMIT]
            row["distance"] = 0
            row["evidence"] = (
                f"全文件命中 {len(hits)} 处，其中 {len(inside)} 处落在区间内："
                + "、".join(f"0x{h:08X}" for h in inside[:HIT_PRINT_LIMIT])
            )
            rows.append(row)
            continue
        if hits:
            nearest = min(hits, key=lambda h: (_region_distance(h, region_start, region_end), h))
            dist = _region_distance(nearest, region_start, region_end)
            row["method"] = "exact-elsewhere"
            row["nearestHit"] = nearest
            row["distance"] = dist
            side = "在区间之前" if nearest < region_start else "在区间之后"
            row["evidence"] = (
                f"全文件命中 {len(hits)} 处，都不在区间内；最近 0x{nearest:08X}"
                f"（距区间 {dist} 字节，{side}）"
            )
            rows.append(row)
            continue
        best, why = fuzzy_in_span(buf, scan["pattern"], scan["anchors"],
                                  region_start - span, region_end + span, span)
        if best is not None:
            row["method"] = "fuzzy"
            row["fuzzy"] = best
            row["distance"] = _region_distance(best["offset"], region_start, region_end)
            row["evidence"] = (
                f"全文件 0 处精确命中；区间 ±{span} 内最佳起点 0x{best['offset']:08X}"
                f" 不匹配 {best['mismatchCount']}/{best['determinateCount']}"
                f" ({best['ratio'] * 100:.2f}%)"
            )
        else:
            row["reason"] = why
            row["evidence"] = f"全文件 0 处精确命中；{why}"
        rows.append(row)
    rows.sort(key=lambda r: (
        MATCH_METHOD_RANK[r["method"]],
        r["fuzzy"]["ratio"] if r["method"] == "fuzzy" else 0.0,
        r["distance"] if r["distance"] is not None else 0,
        r["featureIndex"],
        r["ruleIndex"],
    ))
    return rows


def _fuzzy_json(fuzzy: dict) -> dict:
    if not fuzzy:
        return None
    return {
        "offset": fuzzy["offset"],
        "mismatchCount": fuzzy["mismatchCount"],
        "determinateCount": fuzzy["determinateCount"],
        "ratio": round(fuzzy["ratio"], 6),
        "matchedAnchors": fuzzy["matchedAnchors"],
        "mismatches": [
            {
                "patternIndex": k,
                "expected": f"{exp:02X}",
                "actual": f"{act:02X}",
                "fileOffset": fuzzy["offset"] + k,
            }
            for k, exp, act in fuzzy["mismatches"]
        ],
    }


def cmd_match(args) -> int:
    t0 = time.perf_counter()
    if args.top < 1:
        raise ToolError("--top 至少为 1", f"默认 {MATCH_TOP_DEFAULT}")
    if args.search_span < 0:
        raise ToolError("--search-span 不能是负数", f"默认 {MATCH_SEARCH_SPAN} 字节")
    if args.key == "selected" and not args.ver:
        raise ToolError(
            "--key selected 需要 --ver",
            "给目标版本号（如 --ver 4.1.15.13），或改用 --key latest / --key any",
        )
    regions = []
    for text in (args.region or []):
        start, end = parse_region_arg(text)
        regions.append((start, end, "--region"))
    if args.regions:
        regions.extend(load_regions_from_json(args.regions))
    if not regions:
        raise ToolError(
            "没有要匹配的区间",
            "给至少一个 --region START-END，或用 --regions <extract --json 的产物>",
        )

    channel = navigate_channel(args.config, args.sw, args.mode, args.channel)
    entries, stat, skips = collect_match_rules(channel, args.ver, args.key)

    lines = []
    lines.append(f"配置: {os.path.abspath(args.config)}")
    lines.append(
        f"平台={args.sw} 模式={args.mode} 渠道={args.channel} "
        f"目标版本={args.ver if args.ver else '（本模式不需要）'}"
    )
    key_text = {
        "selected": "selected：按 findCompatibleVersion 只取目标版本生效的那一个键",
        "latest": "latest：忽略目标版本，只取版本号最大的键",
        "any": "any：遍历所有非 null 版本键，每个键都当成一条候选规则",
    }[args.key]
    lines.append(f"选键模式 = {args.key}（{key_text}）")

    with MappedFile(args.file) as mf:
        lines.append(f"文件: {mf.path}  ({mf.size} 字节)")
        cache = scan_match_patterns(mf.mm, entries)
        hit_desc = "、".join(str(len(cache[e["originalNorm"]]["hits"])) for e in entries) or "无"
        lines.append(
            f"规则集: {stat['featureCount']} 个 feature / {stat['ruleCount']} 条 rule -> "
            f"候选规则 {stat['entryCount']} 条"
            + (f"（同字节的多版本键去重掉 {stat['dedupedKeys']} 个）" if stat["dedupedKeys"] else "")
        )
        if skips:
            lines.append("跳过: " + "；".join(f"{k} ×{v}" for k, v in skips.items()))
        lines.append(
            f"扫描: {len(cache)} 条不同字节的 original，每条在目标文件上只扫一次（命中数依次 {hit_desc}）"
        )

        norm_regions = []
        for start, end, src in regions:
            if start >= mf.size:
                raise ToolError(
                    f"区间起点 0x{start:X} 已超出文件大小 0x{mf.size:X}",
                    "核对区间是否来自本次 diff/extract 的输出",
                )
            norm_regions.append((start, min(end, mf.size), src))
        region_src = {}
        for _s, _e, src in norm_regions:
            region_src[src] = region_src.get(src, 0) + 1
        lines.append(
            f"区间: {len(norm_regions)} 个（"
            + "、".join(f"{k} {v} 个" for k, v in region_src.items())
            + f"）；模糊命中限定在区间 ± {args.search_span} 字节内"
        )
        lines.append("")

        if not entries:
            lines.append("该渠道在这个选键模式下没有任何可扫描的规则。")
            print("\n".join(lines))
            return 0

        region_reports = []
        total_counts = {m: 0 for m in MATCH_METHODS}
        for idx, (start, end, src) in enumerate(norm_regions):
            rows = match_region(start, end, entries, cache, mf.mm, args.search_span)
            counts = {m: 0 for m in MATCH_METHODS}
            for r in rows:
                counts[r["method"]] += 1
                total_counts[r["method"]] += 1
            lines.append(f"## 区间 #{idx} 0x{start:08X}~0x{end:08X}（长度 {end - start}，来源 {src}）")
            for rank, r in enumerate(rows[:args.top], 1):
                key_extra = ("（同字节的其它键：" + "、".join(r["keysAlso"]) + "）"
                             if r["keysAlso"] else "")
                lines.append(
                    f"   排名 {rank}) feature#{r['featureIndex']} rule#{r['ruleIndex']} "
                    f"type={r['type']} 键={r['key']}{key_extra} 命中方式={r['method']}"
                )
                lines.append(f"      证据: {r['evidence']}")
                if r["method"] == "fuzzy" and r["fuzzy"] and r["fuzzy"]["mismatches"]:
                    items = [
                        f"模式#{k} 期望={exp:02X} 实际={act:02X}（文件 0x{r['fuzzy']['offset'] + k:08X}）"
                        for k, exp, act in r["fuzzy"]["mismatches"][:MATCH_MISMATCH_PRINT]
                    ]
                    tail = ("" if len(r["fuzzy"]["mismatches"]) <= MATCH_MISMATCH_PRINT
                            else f" …（共 {len(r['fuzzy']['mismatches'])} 处）")
                    lines.append("      不匹配位置: " + "；".join(items) + tail)
                lines.append(f"      original(前{MATCH_ORIGINAL_PREVIEW}字节) = {r['originalPreview']}")
            lines.append(
                f"   汇总: exact-in-region {counts['exact-in-region']} / "
                f"exact-elsewhere {counts['exact-elsewhere']} / fuzzy {counts['fuzzy']} / "
                f"none {counts['none']}（候选规则 {len(rows)} 条，已列前 {min(args.top, len(rows))} 条）"
            )
            if counts["none"] == len(rows):
                lines.append(
                    "   !! 该区间没有任何库规则留下证据：这段差异可能是品牌改名/URL 替换，"
                    "或对应的是库里没有记录的新位置 —— 需要人工判断，不要硬套到某条规则上。"
                )
            lines.append("")
            region_reports.append({
                "index": idx,
                "start": start,
                "end": end,
                "source": src,
                "candidates": [
                    {
                        "rank": rank,
                        "featureIndex": r["featureIndex"],
                        "ruleIndex": r["ruleIndex"],
                        "type": r["type"],
                        "addr": r["addr"],
                        "key": r["key"],
                        "keysAlso": r["keysAlso"],
                        "method": r["method"],
                        "evidence": r["evidence"],
                        "reason": r["reason"],
                        "original": r["original"],
                        "originalPreview": r["originalPreview"],
                        "patternLength": r["patternLength"],
                        "determinateCount": r["determinateCount"],
                        "hitCount": r["hitCount"],
                        "hits": r["hits"],
                        "inRegionHits": r["inRegionHits"],
                        "nearestHit": r["nearestHit"],
                        "distance": r["distance"],
                        "fuzzy": _fuzzy_json(r["fuzzy"]),
                    }
                    for rank, r in enumerate(rows[:args.top], 1)
                ],
                "counts": counts,
                "candidateRuleCount": len(rows),
                "noEvidence": counts["none"] == len(rows),
            })

        lines.append(
            f"汇总: 区间 {len(norm_regions)} 个；exact-in-region {total_counts['exact-in-region']} / "
            f"exact-elsewhere {total_counts['exact-elsewhere']} / fuzzy {total_counts['fuzzy']} / "
            f"none {total_counts['none']}（按区间数规则，每区间每规则各计一次）"
        )
        if any(rep["noEvidence"] for rep in region_reports):
            bad = [f"#{rep['index']}" for rep in region_reports if rep["noEvidence"]]
            lines.append(
                f"注意: 区间 {'、'.join(bad)} 完全没有库规则命中，别硬套到某条规则上；"
                "可能是改名/URL 替换或库里没有的新位置"
            )
        elapsed = time.perf_counter() - t0
        lines.append(f"耗时={elapsed:.2f}s")
        print("\n".join(lines))

        if args.json:
            write_json(args.json, {
                "config": os.path.abspath(args.config),
                "sw": args.sw,
                "mode": args.mode,
                "channel": args.channel,
                "ver": args.ver,
                "keyMode": args.key,
                "file": mf.path,
                "size": mf.size,
                "searchSpan": args.search_span,
                "top": args.top,
                "ruleSet": {
                    "featureCount": stat["featureCount"],
                    "ruleCount": stat["ruleCount"],
                    "entryCount": stat["entryCount"],
                    "dedupedKeys": stat["dedupedKeys"],
                    "skipped": [{"reason": k, "count": v} for k, v in skips.items()],
                    "rules": [
                        {
                            "featureIndex": e["featureIndex"],
                            "ruleIndex": e["ruleIndex"],
                            "type": e["type"],
                            "addr": e["addr"],
                            "key": e["key"],
                            "keysAlso": e["keysAlso"],
                            "original": e["original"],
                            "patternLength": (cache[e["originalNorm"]]["pattern"].size
                                              if cache[e["originalNorm"]]["pattern"] else None),
                            "determinateCount": cache[e["originalNorm"]]["determinate"],
                            "hitCount": len(cache[e["originalNorm"]]["hits"]),
                            "hits": cache[e["originalNorm"]]["hits"][:HIT_PRINT_LIMIT],
                            "scanError": cache[e["originalNorm"]]["error"],
                        }
                        for e in entries
                    ],
                },
                "regions": region_reports,
                "summary": {
                    "regionCount": len(norm_regions),
                    "uniquePatterns": len(cache),
                    "methods": total_counts,
                },
            })
    return 0


# --------------------------------------------------------------------------------------
# 子命令：merge
# --------------------------------------------------------------------------------------

def old_from_config(args) -> tuple:
    """--old 未给时：按 --key 选出该规则的版本键，取该键的 original。

    返回 (original 或 None, 打印用的说明行)。None 表示该版本弃用此规则。
    """
    for need, flag in (("sw", "--sw"), ("mode", "--mode"), ("channel", "--channel")):
        if not getattr(args, need):
            raise ToolError(
                f"--old 与 --sw/--mode/--channel 是二选一：不给 --old 就必须给 {flag}",
                "例：merge --sw Weixin --mode anti-revoke --channel bubble --ver 4.1.0 "
                "--feature 0 --rule 5 --new-bytes \"...\"",
            )
    if args.feature is None:
        raise ToolError(
            "从特征库取 original 时必须指定 --feature",
            "先跑 check 看输出里的 feature# 编号（从 0 开始）",
        )
    if args.key == "selected" and not args.ver:
        raise ToolError(
            "--key selected 需要 --ver（要拿目标版本去选键）",
            "要么给 --ver，要么用 --key latest 直接取版本号最大的键",
        )
    channel = navigate_channel(args.config, args.sw, args.mode, args.channel)
    rule = pick_feature_rule(channel, args.feature, args.rule)
    va = rule.get("ver_adaptations")
    if not isinstance(va, dict) or not va:
        raise ToolError("这条规则没有 ver_adaptations", "换一条规则，或直接用 --old 指定特征码")
    key, kind, is_null = select_version_key(va, args.ver, args.key)
    info = [
        f"库里规则 = {args.sw}/{args.mode}/{args.channel} feature#{args.feature} "
        f"rule#{args.rule} type={rule.get('type')}",
        f"选键模式 = {args.key}；选中的版本键 = {key}"
        + ("" if args.key == "latest" else f"（{version_rule_text(kind, args.ver, key)}）"),
        f"该键的值 = {describe_version_value(va.get(key))}",
    ]
    if is_null:
        info.append("该版本弃用此规则：没有 original 可比对，merge 无事可做。")
        return None, info
    payload = va.get(key)
    original = payload.get("original") if isinstance(payload, dict) else None
    if not original:
        info.append(f"版本键 {key} 没有 original 字段：无法比对。")
        return None, info
    info.append(f"取自特征库的 old = {original}")
    return original, info


def cmd_merge(args) -> int:
    old_text = args.old
    key_lines = []
    if old_text is None:
        old_text, key_lines = old_from_config(args)
        if old_text is None:
            print("\n".join(key_lines))
            if args.json:
                write_json(args.json, {
                    "old": None, "new": args.newBytes, "result": "deprecated-rule",
                    "key": key_lines[1] if len(key_lines) > 1 else None,
                    "note": key_lines[-1],
                })
            return 0
    new_text = args.newBytes
    old = compile_pattern(old_text, side="old")
    new = compile_pattern(new_text, side="new-bytes")
    if any(t is None for t in new.tokens):
        raise ToolError(
            "--new-bytes 必须是具体字节，不能含 ??",
            "把 extract 输出的 original 串原样传进来（那串本来就不含通配）",
        )
    if old.left_fill:
        raise ToolError(
            "已存储的 original 不应以 ... 开头（左补齐是 modified 侧的写法）",
            "去掉开头的 ...；original 只允许 ?? 与结尾的 ...（其余不变）",
        )

    lines = []
    if key_lines:
        lines.extend(key_lines)
        lines.append("")
    elif args.ver or args.sw:
        lines.append("选键模式 = （未使用：--old 直接给出特征码，--key 只影响从特征库取 original 的情况）")
    lines.append(f"old = {old.to_text() or '（空）'}")
    lines.append(f"new = {new.to_text() or '（空）'}")
    if old_text.strip().endswith(TRUNCATE):
        lines.append("提示：old 结尾的 ... 已按语义丢弃（表示\"其余不变\"），下面只比较显式写出的字节。")
    lines.append("")

    payload = {
        "old": old.to_text(),
        "new": new.to_text(),
        "oldLength": old.size,
        "newLength": new.size,
        "result": None,
        "merged": None,
        "hitCount": None,
        "hits": [],
        "file": os.path.abspath(args.file) if args.file else None,
    }

    if old.size != new.size:
        payload["result"] = "incompatible-lengths"
        lines.append(
            f"无法合并：长度不一致（old={old.size}, new={new.size}），需要新增版本键。"
        )
        lines.append(
            "说明：长度不同的两条特征码是不同指令形态，不能靠放松通配合并；"
            "请把 new 作为新的版本键写进 ver_adaptations（本工具只读，不会替你改配置）。"
        )
        print("\n".join(lines))
        if args.json:
            write_json(args.json, payload)
        return 0

    merged_tokens = []
    for o, n in zip(old.tokens, new.tokens):
        if o is None or o != n:
            merged_tokens.append(None)
        else:
            merged_tokens.append(o)
    merged = Pattern(merged_tokens, False, "")

    if merged.tokens == old.tokens:
        payload["result"] = "no-update"
        payload["merged"] = old.to_text()
        lines.append("无需更新：已存储特征已覆盖新版（新版每一位都与 old 的字节或 ?? 相容）。")
        merged_for_scan = old
    else:
        payload["result"] = "merged"
        payload["merged"] = merged.to_text()
        newly_relaxed = sum(1 for o, n in zip(old.tokens, new.tokens) if o is not None and o != n)
        kept_wild = sum(1 for o in old.tokens if o is None)
        diff_positions = [i for i, (o, n) in enumerate(zip(old.tokens, new.tokens)) if o is not None and o != n]
        lines.append(f"合并候选（只放松不放紧，旧版本仍可匹配）：{merged.to_text()}")
        shown_pos = "、".join(f"#{i}" for i in diff_positions[:16])
        if len(diff_positions) > 16:
            shown_pos += f" …（共 {len(diff_positions)} 处）"
        lines.append(
            f"说明：其中 {newly_relaxed} 位因 old 与 new 字节不同而被放宽为 ??"
            f"（位置 {shown_pos or '无'}）；另有 {kept_wild} 位 old 原本就是 ??（保持 ??）。"
        )
        merged_for_scan = merged

    if args.file:
        with MappedFile(args.file) as mf:
            try:
                hits = find_all_pattern(mf.mm, merged_for_scan)
            except ToolError as exc:
                lines.append(f"唯一性校验跳过：{exc}")
                print("\n".join(lines))
                if args.json:
                    write_json(args.json, payload)
                raise ToolError(
                    f"无法在 {args.file} 上校验唯一性：{exc}",
                    "换一条含确定字节的特征码，或去掉 --file 只做合并判断",
                ) from exc
            payload["hitCount"] = len(hits)
            payload["hits"] = hits[:HIT_PRINT_LIMIT]
            shown = "、".join(f"0x{h:0X}" for h in hits[:HIT_PRINT_LIMIT]) or "（无）"
            lines.append(f"在新文件上的命中次数 = {len(hits)}：{shown}")
            if len(hits) == 1:
                lines.append("可提交：唯一命中。")
            elif len(hits) == 0:
                lines.append(
                    "注意：0 命中 —— 说明这条特征码在新 dll 里根本不存在，"
                    "可能文件版本不符、或该处已被改写成别的形态（不要当成可提交）。"
                )
            else:
                lines.append(
                    "告警：多重命中（有误打风险）—— 本工具不会自动截断特征码，"
                    "请手工复核或重新差分取更长的窗口。"
                )
    print("\n".join(lines))
    if args.json:
        write_json(args.json, payload)
    return 0


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="diffsig.py",
        description="只读二进制差分 / 特征码提炼 / 特征库自检工具（标准库实现，绝不改文件、不改配置、不打补丁）",
        epilog="示例：\n"
               "  python diffsig.py diff A.dll B.dll\n"
               "  python diffsig.py extract A.dll B.dll --json tmp/skillwork/cand.json\n"
               "  python diffsig.py check --sw Weixin --mode anti-revoke --channel silence --ver 4.1.15.13 --file B.dll\n"
               "  python diffsig.py check --sw Weixin --mode anti-revoke --channel bubble --ver 4.1.15.13 "
               "--file B.dll --key latest\n"
               "  python diffsig.py merge --old \"48 8D ?? ?? E8\" --new-bytes \"48 8D AA BB E8\" --file B.dll\n"
               "  python diffsig.py locate --pattern \"74 6E 48 8D 8D ?? ?? 00 00\" --file B.dll --top 5",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="command", required=True,
                            metavar="{diff,extract,match,check,merge,locate}")

    p = sub.add_parser(
        "diff",
        help="逐字节差分两个等长文件并渲染差异区间",
        description="逐字节差分：要求两个文件大小完全相同；把相邻差异（间隔 <= gap 字节）合并成区间，"
                    "带上下文渲染 A/B 两侧，并可选输出 JSON。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="区间 = [START, END)，长度 = END-START；END 不含。\n"
               "例：python diffsig.py diff a.bin b.bin --gap 8 --json tmp/skillwork/diff.json",
    )
    p.add_argument("fileA", help="文件A（原版）")
    p.add_argument("fileB", help="文件B（打完补丁的副本）")
    p.add_argument("--gap", type=int, default=8,
                   help="合并间隔：两个差异字节之间最多夹几个相同字节仍算同一区间（默认 8）")
    p.add_argument("--left", type=int, default=64, help="区间左侧上下文字节数（默认 64，边界裁剪）")
    p.add_argument("--right", type=int, default=96, help="区间右侧上下文字节数（默认 96，边界裁剪）")
    p.add_argument("--max-print", type=int, default=50,
                   help="最多渲染几个区间（默认 50，0 表示全部；总数始终会报告）")
    p.add_argument("--max-positions", type=int, default=MAX_DIFF_POSITIONS,
                   help=f"差异字节数护栏（默认 {MAX_DIFF_POSITIONS}，防内存打爆）")
    p.add_argument("--json", metavar="OUT", help="把机器可读结果写到该文件")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser(
        "extract",
        help="从差异区间提炼候选特征码对（不含通配符）",
        description="对每个差异区间取窗口：先把差异本体两侧补未变化上下文到 --min-window 字节"
                    "（触边界只补一侧），再在 fileA 中对称外扩直到唯一命中，"
                    "输出等长的 original/modified 具体字节串（绝不含 ??），并给出省略式 modified。"
                    "分类（code/string/unknown）只看差异本体，撑开的上下文不参与判断。"
                    "--json 里的 draft 是可直接粘进 ver_adaptations 的片段（版本键用 <VERSION> 占位），"
                    "只写 JSON 文件。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="例：python diffsig.py extract a.dll b.dll --json tmp/skillwork/cand.json\n"
               "     python diffsig.py extract a.dll b.dll --min-window 4（看差异本体原样，不撑开）\n"
               "     python diffsig.py extract a.dll b.dll --include-strings（连字符串区间一起看）",
    )
    p.add_argument("fileA", help="文件A（原版）")
    p.add_argument("fileB", help="文件B（打完补丁的副本）")
    p.add_argument("--gap", type=int, default=8, help="区间合并间隔（默认 8）")
    p.add_argument("--min-window", type=int, default=MIN_WINDOW_DEFAULT,
                   help=f"最小窗口字节数（默认 {MIN_WINDOW_DEFAULT}）：差异本体不足时先两侧补未变化上下文到它，"
                        "再做唯一化外扩；1 表示只要差异本体")
    p.add_argument("--max-window", type=int, default=512,
                   help="窗口唯一化上限字节数（默认 512；到上限仍多重命中则报无法唯一化）")
    p.add_argument("--max-positions", type=int, default=MAX_DIFF_POSITIONS,
                   help=f"差异字节数护栏（默认 {MAX_DIFF_POSITIONS}）")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--skip-strings", dest="skip_strings", action="store_true", default=True,
                   help="默认跳过疑似字符串区间（品牌改名/URL 替换之类，与打补丁点无关）")
    g.add_argument("--include-strings", dest="skip_strings", action="store_false",
                   help="不跳过字符串区间，全部列出")
    p.add_argument("--json", metavar="OUT", help="把机器可读结果写到该文件（含可直接粘贴的 draft）")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser(
        "check",
        help="按版本键语义在目标 dll 上扫描特征库里每条 original",
        description="读取特征库，按 SwRuleResolver.findCompatibleVersion 的语义（精确 > 不大于目标的最高键 > "
                    "最低键）为每条规则选出生效版本键，再用 SwHexUtils.tokenizeWildcard 的语义扫描目标文件。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="判定口径：命中==1（且给了 --region 时落于区间内）-> PASS；命中>1 -> PASS? 多重命中；"
               "0 命中 -> FAIL；版本值为 null / 无 original / 类型未支持 -> SKIP。\n"
               "jmp_offset 的 original 也会按 tokenizeWildcard 语义扫描，并额外报该规则的 !! 数量与 "
               "targets 首个命中位置（不计算填充值、不判 PASS/FAIL）；relation / nested 仍 SKIP 并说明原因。\n"
               "例：python diffsig.py check --sw Weixin --mode anti-revoke --channel silence "
               "--ver 4.1.15.13 --file Weixin.dll.bak",
    )
    p.add_argument("--sw", required=True, help="平台键，如 Weixin")
    p.add_argument("--mode", required=True, help="模式键，如 anti-revoke")
    p.add_argument("--channel", required=True, help="渠道键，如 silence")
    p.add_argument("--ver", required=True, help="当前版本号，如 4.1.15.13")
    p.add_argument("--key", choices=("selected", "latest"), default="selected",
                   help="取哪个版本键：selected（默认，按 findCompatibleVersion 选目标版本生效的键）"
                        "/ latest（忽略目标版本，直接取版本号最大的键）")
    p.add_argument("--file", help="要扫描的 dll 路径；不给则只做版本键选择")
    p.add_argument("--config", default=DEFAULT_CONFIG,
                   help=f"特征库路径（默认 {DEFAULT_CONFIG}）")
    p.add_argument("--region", metavar="START-END",
                   help="限定区间，如 0x1A20-0x1B00（带 0x 或含 A-F 按十六进制，纯数字按十进制）；END 不含")
    p.add_argument("--json", metavar="OUT", help="把机器可读结果写到该文件")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser(
        "merge",
        help="判断已存储的 original 能否覆盖新版（只放松不放紧）",
        description="把旧特征码与新提炼的 original 对齐：长度相同则逐位比较，不同位放宽为 ??（只放松不放紧）；"
                    "长度不同则报无法合并、必须新增版本键。旧特征码可以直接用 --old 给，"
                    "也可以给 --sw/--mode/--channel/--feature/--rule 从特征库按 --key 取出。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="例：python diffsig.py merge --old \"0F 84 ?? ?? 48 8D\" "
               "--new-bytes \"0F 84 11 22 48 8D\" --file new.dll\n"
               "    python diffsig.py merge --sw Weixin --mode anti-revoke --channel bubble --ver 4.1.0 "
               "--feature 0 --rule 5 --key latest --new-bytes \"E8 11 22 33 44\"",
    )
    p.add_argument("--old", help="已存储的 original 特征码（可含 ??）；不给则用 --sw/--mode/--channel 从特征库取")
    p.add_argument("--new-bytes", dest="newBytes", required=True,
                   help="extract 得到的新 original 串（必须是具体字节，可含空白）")
    p.add_argument("--key", choices=("selected", "latest"), default="selected",
                   help="从特征库取 old 时用哪个版本键：selected（默认，需 --ver）/ latest（版本号最大的键）")
    p.add_argument("--sw", help="平台键（配合 --old 的替代用法），如 Weixin")
    p.add_argument("--mode", help="模式键，如 anti-revoke")
    p.add_argument("--channel", help="渠道键，如 bubble")
    p.add_argument("--ver", help="目标版本号；--key selected 时必填")
    p.add_argument("--feature", type=int, default=None, help="feature 下标（从 0 开始，见 check 输出）")
    p.add_argument("--rule", type=int, default=0, help="该 feature 内 rule 下标（默认 0）")
    p.add_argument("--config", default=DEFAULT_CONFIG,
                   help=f"特征库路径（默认 {DEFAULT_CONFIG}）")
    p.add_argument("--file", help="可选：在新 dll 上校验合并候选的唯一性")
    p.add_argument("--json", metavar="OUT", help="把机器可读结果写到该文件")
    p.set_defaults(func=cmd_merge)

    p = sub.add_parser(
        "locate",
        help="旧特征在新文件里漂移到了哪（按锚点找最像的位置）",
        description="把模式里连续的确定字节段按 4 字节切块当锚点，用 bytes.find 取候选起点，"
                    "再对每个候选逐字节比对（?? 位置永远算相同），按不匹配比例升序给出最像的位置。"
                    "只报位置与差异，不改任何文件、不推断填充值。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="候选约束：命中的锚点块个数 >= min(2, 块总数)（块位置与模式一致），用来挡掉单块巧合。\n"
               "没有任何候选时说明锚点一次都没出现 —— 多半是代码被整体改写或前后挪了字节数，需要人工汇编定位。\n"
               "例：python diffsig.py locate --pattern \"74 6E 48 8D 8D ?? ?? 00 00 E8 ?? ?? ?? ??\" "
               "--file Weixin.dll --top 5 --region 0x100000-0x200000",
    )
    p.add_argument("--pattern", required=True, help="旧特征码（可含 ??；不要含 !! 或开头的 ...）")
    p.add_argument("--file", required=True, help="要搜索的 dll/exe")
    p.add_argument("--max-mismatch-ratio", type=float, default=0.15,
                   help="不匹配比例上限（默认 0.15，即允许 15/100 的确定字节不一致；超过视为不是同一处）")
    p.add_argument("--top", type=int, default=LOCATE_TOP_DEFAULT,
                   help=f"最多输出几个候选（默认 {LOCATE_TOP_DEFAULT}）")
    p.add_argument("--region", metavar="START-END",
                   help="限定区间，如 0x1A20-0x1B00（逐候选标出是否落在区间内）；END 不含")
    p.add_argument("--json", metavar="OUT", help="把机器可读结果写到该文件")
    p.set_defaults(func=cmd_locate)

    p = sub.add_parser(
        "match",
        help="把差异区间对应到特征库里具体哪条规则（feature#/rule#/版本键）",
        description="给定目标文件与若干差异区间，对指定渠道下所有可扫描规则的 original 逐区间给出证据："
                    "精确命中落在区间内（exact-in-region）/ 精确命中但都在区间外（exact-elsewhere）/ "
                    "只在区间 ± --search-span 内模糊命中（fuzzy）/ 完全无证据（none），"
                    "按该顺序取前 --top 条，解决“这段差异属于哪个渠道哪条规则”的问题。"
                    "每条规则的全文件扫描只做一次并缓存，不按区间重复扫。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="判定顺序：exact-in-region > exact-elsewhere > fuzzy（按不匹配比例升序）> none。\n"
               "--key any 会把每条规则的所有非 null 版本键都当成候选规则，"
               "但 original 字节完全相同的键只入队一次（避免同一条规则的多份拷贝挤满 top-N）。\n"
               "某区间全是 none 时会提示：别硬套到某条规则上，那段差异可能是改名/URL 替换或库外新位置。\n"
               "例：python diffsig.py match --sw Weixin --mode anti-revoke --channel alert "
               "--ver 4.1.15.13 --file Weixin.dll.bak --region 0x55127A0-0x55127C0 --top 3",
    )
    p.add_argument("--sw", required=True, help="平台键，如 Weixin")
    p.add_argument("--mode", required=True, help="模式键，如 anti-revoke")
    p.add_argument("--channel", required=True, help="渠道键，如 alert")
    p.add_argument("--file", required=True, help="要匹配的 dll/exe（差异通常相对它产生）")
    p.add_argument("--ver", help="目标版本号；--key selected 时必填")
    p.add_argument("--key", choices=("selected", "latest", "any"), default="selected",
                   help="规则集合取哪个版本键：selected（默认，按 findCompatibleVersion）"
                        "/ latest（版本号最大的键）/ any（所有非 null 键各算一条候选规则）")
    p.add_argument("--regions", metavar="JSON",
                   help="直接吃 extract --json 的产物，取其中全部差异区间")
    p.add_argument("--region", action="append", metavar="START-END",
                   help="手工指定区间，可重复，如 --region 0x55127A0-0x55127C0（END 不含）")
    p.add_argument("--search-span", type=int, default=MATCH_SEARCH_SPAN,
                   help=f"模糊命中的搜索跨度：区间 ± 该字节数（默认 {MATCH_SEARCH_SPAN}）")
    p.add_argument("--top", type=int, default=MATCH_TOP_DEFAULT,
                   help=f"每个区间最多列几条候选规则（默认 {MATCH_TOP_DEFAULT}）")
    p.add_argument("--config", default=DEFAULT_CONFIG,
                   help=f"特征库路径（默认 {DEFAULT_CONFIG}）")
    p.add_argument("--json", metavar="OUT", help="把机器可读的匹配结果写到该文件（供后续步骤消费）")
    p.set_defaults(func=cmd_match)

    return ap


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ToolError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        if exc.hint:
            print(f"建议: {exc.hint}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"错误: 文件或目录不存在：{exc.filename}", file=sys.stderr)
        print("建议: 检查路径；含空格或中文时用引号包住", file=sys.stderr)
        return 2
    except PermissionError as exc:
        print(f"错误: 没有访问权限：{exc.filename or exc}", file=sys.stderr)
        print("建议: 该文件可能被占用或需要管理员权限；本工具只读打开，不会修改它", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"错误: 文件读写失败：{exc}", file=sys.stderr)
        print("建议: 确认文件存在且未被独占锁定", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
