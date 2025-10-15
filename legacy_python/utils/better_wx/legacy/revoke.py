from _utils import *

title("Anti Revoke Legacy")
print("\n - Invalidate revokemsg system message.")

# [Weixin.dll]
dll = dllpath(input(f"\n{BOLD}Weixin.dll{NO_BOLD} (leave blank = auto detect): "))
data = load(dll)
# Anti Revoke
# Search 'revokemsg' and you'll find it.
# 75 21                               // JNZ +21
# 48 B8:     72 65 76 6F 6B 65 6D 73  // MOV RAX, "revokems"
# 48 89 05: [74 41 AF 06]             // MOV [RIP+offset], RAX
# 66 C7 05: [73 41 AF 06] 67 00       // MOV [RIP+offset], "g\0"
# C6 05:    [6E 41 AF 06] 01          // MOV [RIP+offset], 1
# 48 8D 3D: [5D 41 AF 06]             // LEA RDI, [RIP+offset]
# Change JNZ to JMP, so the message type will be unknown.
print(f"\n> Anti Revoke")
UNLOCK_PATTERN = """
75 21
48 B8 72 65 76 6F 6B 65 6D 73
48 89 05 ?? ?? ?? ??
66 C7 05 ?? ?? ?? ?? 67 00
C6 05 ?? ?? ?? ?? 01
48 8D
"""
UNLOCK_REPLACE = """
EB 21
...
"""
data = wildcard_replace(data, UNLOCK_PATTERN, UNLOCK_REPLACE)
# Backup and save
backup(dll)
save(dll, data)
pause()
