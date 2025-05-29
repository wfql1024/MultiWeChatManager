#!/usr/bin/env python3
# ------------------------------------------------------------------
# 包含来自 BetterWX (https://github.com/zetaloop/BetterWX) 的二进制通配符处理逻辑
# 原始代码采用 Unlicense 协议发布，此文件后续修改部分同样放弃版权
# ------------------------------------------------------------------

import os
import pathlib
import re
import shutil
from typing import Union, List

if os.name == "nt":
    # ANSI Support for OLD Windows
    os.system("color")

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[96m"
RESET = "\033[0m"

BOLD = "\033[1m"
NO_BOLD = "\033[22m"
REVERSE = "\033[7m"
NO_REVERSE = "\033[27m"


def path(path: Union[str, pathlib.Path]):
    return pathlib.Path(path).resolve()


def wxbasepath():
    import winreg

    try:
        with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Software\Tencent\Weixin"
        ) as key:
            return path(winreg.QueryValueEx(key, "InstallPath")[0])
    except FileNotFoundError:
        print(f"{RED}[ERR] WX 4.0 reg not found, can't auto-detect path{RESET}")
        pause()
        exit()


def dllpath(dllpath: str):
    if not dllpath:
        base = wxbasepath()
        for version in base.iterdir():
            if version.is_dir() and version.name.startswith("4."):
                print(f"{GREEN}[auto]{RESET} {version / 'Weixin.dll'}")
                return version / "Weixin.dll"
        print(f"{RED}[ERR] Weixin.dll not found in '{base}'{RESET}")
        pause()
        exit()
    dllpath = dllpath.strip('"').strip("'")
    return path(dllpath)


def exepath(exepath: str):
    if not exepath:
        base = wxbasepath()
        print(f"{GREEN}[auto]{RESET} {base / 'Weixin.exe'}")
        return base / "Weixin.exe"
    exepath = exepath.strip('"').strip("'")
    return path(exepath)


def wavpath(soundpath: str):
    if not soundpath:
        return None
    soundpath = soundpath.strip('"').strip("'")
    return path(soundpath)


def pause():
    input(f"\n{REVERSE}Press Enter to continue...{NO_REVERSE}")


def title(title: str):
    print(f"{GREEN}<== [{RESET}BetterWX {title}{GREEN}] ==>{RESET}")


def bformat(data: bytes, max: int = 32):
    string = data.decode("utf-8", "ignore")
    if max and len(string) > max:
        string = string[:max] + "..."
    return string


def patt2hex(pattern: list, max: int = 32):
    hex = ""
    if pattern[0] is ...:
        hex += "suffix "
        pattern = pattern[1:]
    elif pattern[-1] is ...:
        hex += "prefix "
        pattern = pattern[:-1]
    hex = "".join(pattern)
    if max and len(hex) > max:
        hex = hex[:max] + "..."
    return hex


def load(path: pathlib.Path):
    with open(path, "rb") as f:
        return f.read()


def save(path: pathlib.Path, data: bytes):
    print(f"\n> Save {path}")
    try:
        with open(path, "wb") as f:
            f.write(data)
            print(f"{GREEN}[√] File saved{RESET}")
    except PermissionError:
        print(
            f"{RED}[ERR] The file '{path}' is in use, please close it and try again{RESET}"
        )
        pause()
        exit()


def backup(path: pathlib.Path):
    print(f"\n> Backing up '{path.name}'")
    bakfile = path.with_name(path.name + ".bak")
    if not os.path.exists(bakfile):
        try:
            shutil.copy2(path, bakfile)
        except PermissionError:
            print(
                f"{RED}[ERR] Write failed, please run as administrator and try again{RESET}"
            )
            pause()
            exit()
        print(f"{GREEN}[√] Backup created: '{bakfile.name}'{RESET}")
    else:
        print(f"{BLUE}[i] Backup '{bakfile.name}' already exists, good{RESET}")


def search(data: bytes, pattern: Union[str, bytes]) -> List[int]:
    if isinstance(pattern, str):
        pattern = pattern.encode()
    assert isinstance(pattern, bytes)
    pattern = b"".join(
        b"." if bytes([c]) == b"?" else re.escape(bytes([c])) for c in pattern
    )
    print(f"> {bformat(pattern, 0)}")

    regex = re.compile(pattern, re.DOTALL)
    matches = [m.start() for m in regex.finditer(data)]

    if not matches:
        print(f"{YELLOW}[WARN] Pattern <{bformat(pattern)}> not found{RESET}")
        return []
    print(
        f"{GREEN}[√] Found {len(matches)} pattern{'' if len(matches) == 1 else 's'}{RESET}"
    )
    return matches


def replace(data: bytes, pattern: Union[str, bytes], replace: Union[str, bytes]):
    if isinstance(pattern, str):
        pattern = pattern.encode()
    if isinstance(replace, str):
        replace = replace.encode()
    print(f"> {bformat(pattern, 0)} => {bformat(replace, 0)}")

    count = data.count(pattern)
    patched_count = data.count(replace)

    if count == 0:
        if patched_count > 0:
            print(
                f"{BLUE}[i] Found {patched_count} pattern{'' if patched_count == 1 else 's'} already patched{RESET}"
            )
            return data
        print(f"{YELLOW}[WARN] Pattern <{bformat(pattern)}> not found, SKIPPED!{RESET}")
        return data

    data = data.replace(pattern, replace)
    if patched_count > 0:
        print(
            f"{GREEN}[√] Patched {count} pattern{'' if count == 1 else 's'}, found {patched_count} already patched{RESET}"
        )
    else:
        print(f"{GREEN}[√] Patched {count} pattern{'' if count == 1 else 's'}{RESET}")
    return data


def wildcard_tokenize(wildcard: str) -> list:
    wildcard = re.sub(r"\s+", "", wildcard).upper()

    tokens = []
    if wildcard.startswith("..."):
        wildcard = wildcard[3:]
        tokens.append(...)
    elif wildcard.endswith("..."):
        wildcard = wildcard[:-3]

    if len(wildcard) % 2 != 0:
        print(
            f"{RED}[ERR] Wildcard <{wildcard}> has invalid byte {wildcard[-1]}_{RESET}"
        )
        pause()
        exit()
    for i in range(0, len(wildcard), 2):
        a = wildcard[i]
        b = wildcard[i + 1]
        if a not in "0123456789ABCDEF?" or b not in "0123456789ABCDEF?":
            print(f"{RED}[ERR] Wildcard <{wildcard}> has invalid byte {a}{b}{RESET}")
            pause()
            exit()
        elif "?" == a == b:
            tokens.append("??")
        elif a == "?" or b == "?":
            print(f"{RED}[ERR] Wildcard <{wildcard}> has invalid byte {a}{b}{RESET}")
            pause()
            exit()
        else:
            tokens.append(f"{a}{b}")
    return tokens


def wildcard_replace(data: bytes, pattern: Union[str, list], replace: Union[str, list]):
    if isinstance(pattern, str):
        pattern = wildcard_tokenize(pattern)
    if isinstance(replace, str):
        replace = wildcard_tokenize(replace)

    if replace[0] is ...:
        # print(f"{BLUE}[i] Wildcard <{patt2hex(replace)}> used as suffix{RESET}")
        replace = ["??"] * (len(pattern) - len(replace) + 1) + replace[1:]
    else:
        if ... in pattern:
            print(
                f"{RED}[ERR] Wildcard <{patt2hex(pattern)}> has invalid token ...{RESET}"
            )
            pause()
            exit()
        elif ... in replace:
            print(
                f"{RED}[ERR] Wildcard <{patt2hex(replace)}> has invalid token ...{RESET}"
            )
            pause()
            exit()

    if len(replace) < len(pattern):
        # print(f"{BLUE}[i] Wildcard <{patt2hex(replace)}> used as prefix{RESET}")
        replace += ["??"] * (len(pattern) - len(replace))

    if len(replace) != len(pattern):
        print(f"{RED}[ERR] Pattern and replace length mismatch{RESET}")
        pause()
        exit()
    print(f"> {patt2hex(pattern, 0)} => {patt2hex(replace, 0)}")

    regex_bytes = b""
    patched_bytes = b""
    repl_bytes = b""
    group_count = 1

    for p, r in zip(pattern, replace):
        if p == "??":
            regex_bytes += b"(.)"
            patched_bytes += b"(.)"
            if r == "??":
                repl_bytes += b"\\" + str(group_count).encode()
            else:
                repl_bytes += bytes.fromhex(r)
                patched_bytes += re.escape(bytes.fromhex(r))
            group_count += 1
        else:
            regex_bytes += re.escape(bytes.fromhex(p))
            if r == "??":
                repl_bytes += bytes.fromhex(p)
                patched_bytes += re.escape(bytes.fromhex(p))
            else:
                repl_bytes += bytes.fromhex(r)
                patched_bytes += re.escape(bytes.fromhex(r))

    regex = re.compile(regex_bytes, re.DOTALL)
    patched = re.compile(patched_bytes, re.DOTALL)

    original_matches = len(list(regex.finditer(data)))
    patched_matches = len(list(patched.finditer(data)))

    if original_matches == 0:
        if patched_matches > 0:
            print(
                f"{BLUE}[i] Found {patched_matches} pattern{'' if patched_matches == 1 else 's'} already patched{RESET}"
            )
            return data
        print(
            f"{YELLOW}[WARN] Pattern <{patt2hex(pattern)}> not found, SKIPPED!{RESET}"
        )
        return data

    new_data, count = regex.subn(repl_bytes, data)
    if patched_matches > 0:
        print(
            f"{GREEN}[√] Patched {count} pattern{'' if count == 1 else 's'}, found {patched_matches} already patched{RESET}"
        )
    else:
        print(f"{GREEN}[√] Patched {count} pattern{'' if count == 1 else 's'}{RESET}")
    return new_data


def debugged_wildcard_replace(data: bytes, pattern: Union[str, list], replace: Union[str, list]):
    """这个方法详细解释了替换过程，便于调试"""

    def bytes_to_hex_str(byte_data: bytes) -> str:
        """将 bytes 转换为 'xx xx xx' 形式的十六进制字符串"""
        return ' '.join([f"{byte:02x}" for byte in byte_data])

    def get_replacement_pairs(regex, repl_bytes, data):
        matches = list(regex.finditer(data))
        replacement_pairs = []

        for match in matches:
            original = match.group()  # 原始匹配的字节串
            replaced = regex.sub(repl_bytes, original)  # 替换后的字节串
            replacement_pairs.append((original, replaced))

        return replacement_pairs

    data = b'\x89\xF3\x12\xA0\x75\x21\x48\xB8\x72\x65\x76\x6F\x6B\x65\x6D\x73\x48\x89\x05\x3A\xDB\x7F\x00\x66\xC7\x05\x44\x12\x91\xFF\x67\x00\xC6\x05\x88\x42\x33\x11\x01\x48\x8D\xF0\xCC\x21\x9E'
    data_str = bytes_to_hex_str(data)
    pattern = "75 21 48 B8 72 65 76 6F 6B 65 6D 73 48 89 05 ?? ?? ?? ?? 66 C7 05 ?? ?? ?? ?? 67 00 C6 05 ?? ?? ?? ?? 01 48 8D"
    # replace = "EB 21..."
    replace = "... 48 9D"
    print(f"原始数据: {data_str}")
    print(f"原始特征码: {pattern}")
    print(f"补丁特征码: {replace}")
    print("--------------------------------------------------------")
    # print("分词器处理:去除末尾的省略号;若开头有省略号,则识别为{省略号}")
    pattern = wildcard_tokenize(pattern)
    replace = wildcard_tokenize(replace)
    # print(pattern)
    # print(replace)
    # print("判断类型:若...在开头,则以??补充至相同长度;...仅能出现在开头或不存在,否则报错")
    if replace[0] is ...:
        print(f"{BLUE}[i] Wildcard <{patt2hex(replace)}> used as suffix{RESET}")
        replace = ["??"] * (len(pattern) - len(replace) + 1) + replace[1:]
    else:
        if ... in pattern:
            print(
                f"{RED}[ERR] Wildcard <{patt2hex(pattern)}> has invalid token ...{RESET}"
            )
        elif ... in replace:
            print(
                f"{RED}[ERR] Wildcard <{patt2hex(replace)}> has invalid token ...{RESET}"
            )
    # print(pattern)
    # print(replace)
    # print("对...不在开头的情况,在末尾补充??至相同长度")
    if len(replace) < len(pattern):
        print(f"{BLUE}[i] Wildcard <{patt2hex(replace)}> used as prefix{RESET}")
        replace += ["??"] * (len(pattern) - len(replace))
    if len(replace) != len(pattern):
        print(f"{RED}[ERR] Pattern and replace length mismatch{RESET}")
    # print(pattern)
    # print(replace)
    print(f"> 特征码翻译: {patt2hex(pattern, 0)} => {patt2hex(replace, 0)}")
    print("--------------------------------------------------------")
    # print(f"对原始的:将??替换为(.);对补丁和替换:非??则保持,对??的话,若原始为??,则替换为(.)和补位符号,否则摘抄原始值")
    regex_bytes = b""
    patched_bytes = b""
    repl_bytes = b""
    group_count = 1
    for p, r in zip(pattern, replace):
        if p == "??":
            regex_bytes += b"(.)"
            patched_bytes += b"(.)"
            if r == "??":
                repl_bytes += b"\\" + str(group_count).encode()
            else:
                repl_bytes += bytes.fromhex(r)
                patched_bytes += re.escape(bytes.fromhex(r))
            group_count += 1
        else:
            regex_bytes += re.escape(bytes.fromhex(p))
            if r == "??":
                repl_bytes += bytes.fromhex(p)
                patched_bytes += re.escape(bytes.fromhex(p))
            else:
                repl_bytes += bytes.fromhex(r)
                patched_bytes += re.escape(bytes.fromhex(r))
    print(f"regex_bytes: {regex_bytes}")
    print(f"patched_bytes: {patched_bytes}")
    print(f"repl_bytes: {repl_bytes}")
    # print(f"regex_hex: {bytes_to_hex_str(regex_bytes)}")
    # print(f"patched_hex: {bytes_to_hex_str(patched_bytes)}")
    # print(f"repl_hex: {bytes_to_hex_str(repl_bytes)}")
    regex = re.compile(regex_bytes, re.DOTALL)
    patched = re.compile(patched_bytes, re.DOTALL)
    print("匹配到原始串:")
    print(list(regex.finditer(data)))
    print("匹配到补丁串:")
    print(list(patched.finditer(data)))
    pairs = get_replacement_pairs(regex, repl_bytes, data)
    print(pairs)
    for original, replaced in pairs:
        print(f"Original: {bytes_to_hex_str(original)}")
        print(f"Replaced: {bytes_to_hex_str(replaced)}")
        print("---")
    original_matches = len(list(regex.finditer(data)))
    patched_matches = len(list(patched.finditer(data)))
    if original_matches == 0:
        if patched_matches > 0:
            print(
                f"{BLUE}[i] Found {patched_matches} pattern{'' if patched_matches == 1 else 's'} already patched{RESET}"
            )
        else:
            print(
                f"{YELLOW}[WARN] Pattern <{patt2hex(pattern)}> not found, SKIPPED!{RESET}"
            )
        print(data)
        print(bytes_to_hex_str(data))  # 可选调试输出
        # return data  # 保持返回值
    else:
        new_data, count = regex.subn(repl_bytes, data)
        if patched_matches > 0:
            print(
                f"{GREEN}[√] Patched {count} pattern{'' if count == 1 else 's'}, found {patched_matches} already patched{RESET}"
            )
        else:
            print(f"{GREEN}[√] Patched {count} pattern{'' if count == 1 else 's'}{RESET}")
        print(new_data)
        print(bytes_to_hex_str(new_data))
        # return new_data
