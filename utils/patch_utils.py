#!/usr/bin/env python3
# ------------------------------------------------------------------
# 包含来自 BetterWX (https://github.com/zetaloop/BetterWX) 的二进制通配符处理逻辑
# 原始代码采用 Unlicense 协议发布，此文件后续修改部分同样放弃版权
# ------------------------------------------------------------------

# TODO: 特征码匹配加入项目

import os
import re
import shutil
import pathlib
from typing import Union

if os.name == "nt":
    # ANSI Support for OLD Windows
    os.system("color")

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[96m"
RESET = "\033[0m"

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
                print(f"{BLUE}[auto] Weixin.dll: {version / 'Weixin.dll'}{RESET}")
                return version / "Weixin.dll"
        print(f"{RED}[ERR] Weixin.dll not found in '{base}'{RESET}")
        pause()
        exit()
    return path(dllpath)


def exepath(exepath: str):
    if not exepath:
        base = wxbasepath()
        print(f"{BLUE}[auto] Weixin.exe: {base / 'Weixin.exe'}{RESET}")
        return base / "Weixin.exe"
    return path(exepath)


def pause():
    input(f"\n{REVERSE}Press Enter to continue...{NO_REVERSE}")


def b2hex(data: bytes, max: int = 32):
    hex = "".join(f"{b:02X}" for b in data)
    if max and len(hex) > max:
        hex = hex[:max] + "..."
    return hex


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


def replace(data: bytes, pattern: Union[str, list], replace: Union[str, list]):
    if isinstance(pattern, str):
        pattern = pattern.encode()
    if isinstance(replace, str):
        replace = replace.encode()
    print(f"> {b2hex(pattern, 0)} => {b2hex(replace, 0)}")

    count = data.count(pattern)
    patched_count = data.count(replace)

    if count == 0:
        if patched_count > 0:
            print(
                f"{BLUE}[i] Found {patched_count} pattern{'' if patched_count == 1 else 's'} already patched{RESET}"
            )
            return data
        print(f"{YELLOW}[WARN] Pattern <{b2hex(pattern)}> not found, SKIPPED!{RESET}")
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