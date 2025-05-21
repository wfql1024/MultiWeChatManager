from _utils import *

title("Unmutex")
print("\n - Remove WeChat multi-instance check.")

# [Weixin.dll]
dll = dllpath(input(f"\n{BOLD}Weixin.dll{NO_BOLD} (leave blank = auto detect): "))
data = load(dll)
# Block multi-instance check (Mutex)
# Search 'XWeChat_App_Instance_Identity_Mutex_Name' to find the function.
# Just let it return.
print(f"\n> Blocking multi-instance check")
UNMUTEX_PATTERN = """
55
56
57
53
48 81 EC ?? ?? ?? ??
48 8D AC 24 ?? ?? ?? ??
48 C7 85 ?? ?? ?? ?? FE FF FF FF
48 C7 85 ?? ?? ?? ?? 00 00 00 00
B9 60 00 00 00
"""
UNMUTEX_REPLACE = """
C3
...
"""
data = wildcard_replace(data, UNMUTEX_PATTERN, UNMUTEX_REPLACE)
# Backup and save
backup(dll)
save(dll, data)
pause()
