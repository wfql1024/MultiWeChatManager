import os
import pathlib
import re
import shutil


def path(path: str):
    return pathlib.Path(path).resolve()


def pause():
    input("\nPress Enter to continue...")


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
    print(f"\n> Saved {path}")
    try:
        with open(path, "wb") as f:
            f.write(data)
    except PermissionError:
        print(f"[ERR] The file '{path}' is in use, please close it and try again")
        pause()
        exit()


def backup(path: pathlib.Path):
    print(f"\n> Backing up '{path.name}'")
    bakfile = path.with_name(path.name + ".bak")
    if not os.path.exists(bakfile):
        shutil.copy2(path, bakfile)
        print(f"[√] Backup created: '{bakfile.name}'")
    else:
        print(f"[INFO] Backup '{bakfile.name}' already exists, good")


def replace(data: bytes, pattern, replace):
    if isinstance(pattern, str):
        pattern = pattern.encode()
    if isinstance(replace, str):
        replace = replace.encode()
    print(f"> {b2hex(pattern, 0)} => {b2hex(replace, 0)}")
    if pattern not in data:
        print(f"[WARN] Pattern <{b2hex(pattern)}> not found, SKIPPED!")
        return data
    count = data.count(pattern)
    data = data.replace(pattern, replace)
    print(f"[√] Patched {count} pattern{'' if count == 1 else 's'}")
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
        print(f"[ERR] Wildcard <{wildcard}> has invalid byte {wildcard[-1]}_")
        pause()
        exit()
    for i in range(0, len(wildcard), 2):
        a = wildcard[i]
        b = wildcard[i + 1]
        if a not in "0123456789ABCDEF?" or b not in "0123456789ABCDEF?":
            print(f"[ERR] Wildcard <{wildcard}> has invalid byte {a}{b}")
            pause()
            exit()
        elif "?" == a == b:
            tokens.append("??")
        elif a == "?" or b == "?":
            print(f"[ERR] Wildcard <{wildcard}> has invalid byte {a}{b}")
            pause()
            exit()
        else:
            tokens.append(f"{a}{b}")
    return tokens


def wildcard_replace(data: bytes, pattern, replace):
    if isinstance(pattern, str):
        pattern = wildcard_tokenize(pattern)
    if isinstance(replace, str):
        replace = wildcard_tokenize(replace)
    if replace[0] is ...:
        # print(f"[INFO] Wildcard <{patt2hex(replace)}> used as suffix")
        replace = ["??"] * (len(pattern) - len(replace) + 1) + replace[1:]
    else:
        if ... in pattern:
            print(f"[ERR] Wildcard <{patt2hex(pattern)}> has invalid token ...")
            pause()
            exit()
        elif ... in replace:
            print(f"[ERR] Wildcard <{patt2hex(replace)}> has invalid token ...")
            pause()
            exit()
    if len(replace) < len(pattern):
        # print(f"[INFO] Wildcard <{patt2hex(replace)}> used as prefix")
        replace += ["??"] * (len(pattern) - len(replace))

    if len(replace) != len(pattern):
        print("[ERR] Pattern and replace length mismatch")
        pause()
        exit()
    print(f"> {patt2hex(pattern, 0)} => {patt2hex(replace, 0)}")

    regex_bytes = b""
    repl_bytes = b""

    group_count = 1

    for p, r in zip(pattern, replace):
        if p == "??":
            regex_bytes += b"(.)"
            if r == "??":
                repl_bytes += b"\\" + str(group_count).encode()
            else:
                repl_bytes += bytes.fromhex(r)
            group_count += 1
        else:
            regex_bytes += re.escape(bytes.fromhex(p))
            if r == "??":
                repl_bytes += bytes.fromhex(p)
            else:
                repl_bytes += bytes.fromhex(r)

    regex = re.compile(regex_bytes, re.DOTALL)
    new_data, count = regex.subn(repl_bytes, data)
    if count:
        print(f"[√] Patched {count} pattern")
    else:
        print(f"[WARN] Pattern <{patt2hex(pattern)}> not found, SKIPPED!")
    return new_data
