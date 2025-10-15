from inner_utils import *


def main(n, exe_path, dll_path):
    # [Weixin.exe]
    # title("Coexist")
    # print("\n - Create multiple WeChat executables to use different accounts.")

    # # Number
    # n = input(f"\n{BOLD}Wechat Number{NO_BOLD} (0~9): ")
    # if len(n) != 1 or not n in "0123456789":
    #     print(f"{RED}[ERR] Invalid number{RESET}")
    #     pause()
    #     exit()

    # [Weixin.exe]
    exe = exepath(exe_path)
    data = load(exe)
    # Redirect Weixin.dll -> Weixin.dl2
    print(f"\n> Redirecting Weixin.dll -> Weixin.dl{n}")
    EXE_PATTERN = "\x00".join("Weixin.dll")
    EXE_REPLACE = "\x00".join(f"Weixin.dl{n}")
    data = replace(data, EXE_PATTERN, EXE_REPLACE)
    # Rename Weixin.exe -> Weixin2.exe
    new_exe = exe.with_name(f"Weixin{n}.exe")
    save(new_exe, data)

    # [Weixin.dll]
    dll = dllpath(dll_path)
    data = load(dll)
    # Redirect global_config -> global_conf2g
    # Just search 'global_config' and you'll find the pattern.
    # 48 B8:     67 6C 6F 62 61 6C 5F 63   // MOV RAX, "global_c" (0x5F6C61626F6C676)
    # 48 89 05: [07 78 C3 07]              // MOV [RIP+offset], RAX
    # C7 05:    [05 78 C3 07] 6F 6E 66 69  // MOV dword [RIP+offset], "onfi" (0x69666E6F)
    # 66 C7 05: [00 78 C3 07] 67 00        // MOV word [RIP+offset], "g\0" (0x0067)
    # Change "onfi" to "onf{n}" so we have "global_conf{n}g\0"
    print(f"\n> Redirecting global_config -> global_conf{n}g")
    COEXIST_CONFIG_PATTERN = """
    48 B8 67 6C 6F 62 61 6C 5F 63
    48 89 05 ?? ?? ?? ??
    C7 05 ?? ?? ?? ?? 6F 6E 66 69
    66 C7 05 ?? ?? ?? ?? 67 00
    """
    COEXIST_CONFIG_REPLACE = f"""
    ...
    C7 05 ?? ?? ?? ?? 6F 6E 66 {ord(n):02X}
    66 C7 05 ?? ?? ?? ?? 67 00
    """
    data = wildcard_replace(data, COEXIST_CONFIG_PATTERN, COEXIST_CONFIG_REPLACE)
    # Redirect host-redirect.xml -> host-redirect.xm2
    # This file affects the auto-login feature.
    print(f"\n> Redirecting host-redirect.xml -> host-redirect.xm{n}")
    AUTOLOGIN_PATTERN = "host-redirect.xml"
    AUTOLOGIN_REPLACE = f"host-redirect.xm{n}"
    data = replace(data, AUTOLOGIN_PATTERN, AUTOLOGIN_REPLACE)
    # Change Mutex Name
    print("\n> Renaming instance mutex")
    MUTEX_PATTERN = "\0".join("XWeChat_App_Instance_Identity_Mutex_Name")
    MUTEX_REPLACE = "\0".join(f"XWeChat_App_Instance_Identity_Mutex_Nam{n}")
    data = replace(data, MUTEX_PATTERN, MUTEX_REPLACE)
    # Rename Weixin.dll -> Weixin.dl2
    new_dll = dll.with_name(f"Weixin.dl{n}")
    save(new_dll, data)
    pause()


if __name__ == "__main__":
    n = "1"
    exe_path = r"D:\software\Tencent\Weixin\Weixin.exe"
    dll_path = r"D:\software\Tencent\Weixin\4.0.6.21\Weixin.dll"
    main(n, exe_path, dll_path)
