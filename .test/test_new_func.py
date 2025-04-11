from unittest import TestCase

from functions import subfunc_file
from resources import Config
from utils import handle_utils
from utils.file_utils import IniUtils
from utils.patch_utils import *


class Test(TestCase):
    def test_multi_new_weixin(self):
        redundant_wnd_list, login_wnd_class, executable_name, cfg_handles = subfunc_file.get_details_from_remote_setting_json(
            "Weixin", redundant_wnd_class=None, login_wnd_class=None, executable=None, cfg_handle_regex_list=None)
        # 关闭配置文件锁
        handle_utils.close_sw_mutex_by_handle(
            Config.HANDLE_EXE_PATH, executable_name, cfg_handles)
        # 构建源文件和目标文件路径
        # source_dir1 = r"E:\Now\Desktop\不吃鱼的猫\global_config".replace('\\', '/')
        # source_dir2 = r"E:\Now\Desktop\不吃鱼的猫\global_config.crc".replace('\\', '/')
        source_dir1 = r"E:\Now\Desktop\极峰创科\global_config".replace('\\', '/')
        source_dir2 = r"E:\Now\Desktop\极峰创科\global_config.crc".replace('\\', '/')
        target_dir1 = r'E:\data\Tencent\xwechat_files\all_users\config\global_config'.replace('\\', '/')
        target_dir2 = r'E:\data\Tencent\xwechat_files\all_users\config\global_config.crc'.replace('\\', '/')

        # 复制配置文件
        try:
            os.remove(target_dir1)
            os.remove(target_dir2)
            # shutil.rmtree(r'E:\data\Tencent\xwechat_files\all_users\config')
            # os.makedirs(r'E:\data\Tencent\xwechat_files\all_users\config')
            shutil.copy2(source_dir1, target_dir1)
            shutil.copy2(source_dir2, target_dir2)
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

    def test_set_parent_wnd(self):
        import ctypes
        from ctypes import wintypes
        import time

        # 定义 Windows API 函数
        user32 = ctypes.windll.user32

        # 获取目标窗口句柄和你的窗口句柄
        hwnd_target = user32.FindWindowW(None, "微信 - 吾峰起浪")
        hwnd_my_window = user32.FindWindowW(None, "微信多开管理器")

        # 获取你的窗口大小
        my_window_rect = wintypes.RECT()
        user32.GetWindowRect(hwnd_my_window, ctypes.byref(my_window_rect))
        my_window_width = my_window_rect.right - my_window_rect.left
        my_window_height = my_window_rect.bottom - my_window_rect.top

        # 记录目标窗口的初始位置
        last_rect = wintypes.RECT()
        user32.GetWindowRect(hwnd_target, ctypes.byref(last_rect))

        # 调整你的窗口初始位置（位于目标窗口左侧）
        user32.SetWindowPos(
            hwnd_my_window,
            None,  # 无 Z 序调整
            last_rect.left - my_window_width,  # 目标窗口左侧
            last_rect.top,  # 与目标窗口顶部对齐
            0, 0,  # 不调整窗口大小
            0x0001  # SWP_NOSIZE
        )

        # 定期检查目标窗口位置
        while True:
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd_target, ctypes.byref(rect))

            # 如果目标窗口位置发生变化，调整你的窗口位置
            if rect.left != last_rect.left or rect.top != last_rect.top:
                # 计算你的窗口位置（位于目标窗口左侧）
                user32.SetWindowPos(
                    hwnd_my_window,
                    None,  # 无 Z 序调整
                    rect.left - my_window_width,  # 目标窗口左侧
                    rect.top,  # 与目标窗口顶部对齐
                    0, 0,  # 不调整窗口大小
                    0x0001  # SWP_NOSIZE
                )
                last_rect = rect

            # 设置检查间隔（100ms）
            time.sleep(0.02)

    def test_get_ini_config(self):
        config = IniUtils.load_ini_as_dict(Config.SETTING_INI_PATH)
        print(config.__dict__)
