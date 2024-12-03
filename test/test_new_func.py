import os
import shutil
import time
from resources import Config
from unittest import TestCase
from utils import handle_utils
from utils.patch_utils import *
import tkinter.font as tkFont


class Test(TestCase):
    def test_multi_new_weixin(self):
        handle_utils.close_all_new_weixin_mutex_by_handle(Config.HANDLE_EXE_PATH)
        # 构建源文件和目标文件路径
        # source_dir = r"E:\Now\Desktop\不吃鱼的猫"
        source_dir = r"E:\Now\Desktop\极峰创科"
        target_dir = r'E:\data\Tencent\xwechat_files\all_users\config'

        # 如果目录存在，先删除
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)

        time.sleep(1)

        # 复制配置文件
        try:
            shutil.copytree(source_dir, target_dir)
        except Exception as e:
            print(f"复制配置文件失败: {e}")

        os.startfile('D:\software\Tencent\Weixin\Weixin.exe')

    def test_unlock(self):
        # [Weixin.dll]
        dll = path(input("\nWeixin.dll: "))
        data = load(dll)
        # Block multi-instance check (lock.ini)
        # Search 'lock.ini' and move down a bit, find something like:
        # `if ( sub_7FFF9EDBF6E0(&unk_7FFFA6A09B48) && !sub_7FFF9EDC0880(&unk_7FFFA6A09B48, 1LL) )`
        # The second function is the LockFileHandler, check it out, find:
        # ```
        # if ( !LockFileEx(v4, 2 * (a2 != 0) + 1, 0, 0xFFFFFFFF, 0xFFFFFFFF, &Overlapped) )
        # {
        #   LastError = GetLastError();
        #   v5 = sub_7FFF9EDC09C0(LastError);
        # }
        # ```
        # Hex context:
        # C7 44 24: [20] FF FF FF FF  // MOV [RSP+20], 0xFFFFFFFF
        #                                  Overlapped.Offset = -1
        # 31 F6                       // XOR ESI, ESI
        # 45 31 C0                    // XOR R8D, R8D
        # 41 B9:     FF FF FF FF      // MOV R9D, 0xFFFFFFFF
        #                                  Overlapped.OffsetHigh = -1
        # FF 15:    [CB 31 48 06]     // CALL [<LockFileEx>]
        # 85 C0                       // TEST EAX, EAX
        # 75:       [0F]              // JNE [+0F], the if statement
        # Change JNZ to JMP in order to force check pass.
        print(f"\n> Blocking multi-instance check")
        UNLOCK_PATTERN = """
        C7 44 24 ?? FF FF FF FF
        31 F6
        45 31 C0
        41 B9 FF FF FF FF
        FF 15 ?? ?? ?? ??
        85 C0
        75 0F
        """
        UNLOCK_REPLACE = """
        ...
        EB 0F
        """
        data = wildcard_replace(data, UNLOCK_PATTERN, UNLOCK_REPLACE)
        # Backup and save
        backup(dll)
        save(dll, data)
        pause()