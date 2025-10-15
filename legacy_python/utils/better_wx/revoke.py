from inner_utils import *

title("Anti Revoke")
print("\n - Prevent message revoke, keep revoke tip.")
# Anti Revoke from https://github.com/EEEEhex/RevokeHook
print(" - Modified from EEEEhex/RevokeHook v2.x")

# [Weixin.dll]
dll = dllpath(input(f"\n{BOLD}Weixin.dll{NO_BOLD} (leave blank = auto detect): "))
data = load(dll)
# Remove message delete operation
# DeleteMessage(v220, (__int64)&v175, 0);
# 48 8D 55 C0             lea rdx, [rbp+840h+originalMsgContainer]
# 45 31 C0                xor r8d, r8d
# E8 CC 53 71 FE          call DeleteMessage
# 48 85 FF
#
# Change it to:
# SrvID += 1 for revoke tip
# 48 8385 C0020000 01    add qword ptr [rbp+0x2C0], 1
# 90 90 90 90
# --------
# This pattern needs 4.0.3+
# --------
# In 4.0.5+ this will match both RevokeHandler and SimplifiedRevokeHandler
# (SimplifiedRevokeHandler does not have pat and file message logic)
print(f"\n> Prevent message deletion & make new revoke tip id")
REVOKE_PATTERN = """
48 8D 55 C0
45 31 C0
E8 ?? ?? ?? ??
48 85 FF
"""
REVOKE_REPLACE = """
...
48 8385 C0020000 01
90 90 90
"""
data = wildcard_replace(data, REVOKE_PATTERN, REVOKE_REPLACE)
# Allow using new SrvID for our revoke tip
# AddRevokeTipToDB -> AddMessageToDB_Arg0(v5, v9, a3, v6) -> CoAddMessageToDB(a1, a2, a3, a4, 0)
# 56                push rsi
# 48 83 EC 30       sub rsp, 0x30
# 48 89 D6          mov rsi, rdx
# C6 44 24 20 00    mov byte ptr [rsp + 0x20], 0  ->  change to 1 to allow new ID
# E8 DE D8 FF FF    call CoAddToDB
# 48 89 F0          mov rax, rsi
# 48 83 C4 30       add rsp, 0x30
# 5E                pop rsi
# C3                ret
print(f"\n> Allow new revoke tip id")
ALLOW_NEW_ID_PATTERN = """
56
48 83 EC 30
48 89 D6
C6 44 24 20 00
E8 ?? ?? ?? ??
48 89 F0
48 83 C4 30
5E
C3
"""
ALLOW_NEW_ID_REPLACE = """
56
48 83 EC 30
48 89 D6
C6 44 24 20 01
...
"""
data = wildcard_replace(data, ALLOW_NEW_ID_PATTERN, ALLOW_NEW_ID_REPLACE)
# Backup and save
backup(dll)
save(dll, data)
pause()
