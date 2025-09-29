import os
import shutil
import time
import tkinter as tk
from unittest import TestCase

import psutil
import uiautomation
import win32con
import win32gui

from functions import subfunc_file, sw_func
from functions.acc_func import AccOperator
from functions.sw_func import SwInfoUtils, SwOperator
from public import Config
from ui.sidebar_ui import SidebarUI, WndProperties
from utils import handle_utils, hwnd_utils
from utils.file_utils import IniUtils
from utils.hwnd_utils import Win32HwndGetter
from utils.logger_utils import Printer


class Test(TestCase):
    def test_get_wnd_by_classname(self):
        hwnds = Win32HwndGetter.win32_wait_hwnd_by_class("Qt51514QWindowIcon")
        print(hwnds)

    def test_multi_new_weixin(self):
        executable_name, cfg_handles = subfunc_file.get_remote_cfg(
            "Weixin", executable=None, cfg_handle_regex_list=None)
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

    # def test_unlock(self):
    #     # [Weixin.dll]
    #     dll = path(input("\nWeixin.dll: "))
    #     data = load(dll)
    #     # Block multi-instance check (lock.ini)
    #     # Search 'lock.ini' and move down a bit, find something like:
    #     # `if ( sub_7FFF9EDBF6E0(&unk_7FFFA6A09B48) && !sub_7FFF9EDC0880(&unk_7FFFA6A09B48, 1LL) )`
    #     # The second function is the LockFileHandler, check it out, find:
    #     # ```
    #     # if ( !LockFileEx(v4, 2 * (a2 != 0) + 1, 0, 0xFFFFFFFF, 0xFFFFFFFF, &Overlapped) )
    #     # {
    #     #   LastError = GetLastError();
    #     #   v5 = sub_7FFF9EDC09C0(LastError);
    #     # }
    #     # ```
    #     # Hex context:
    #     # C7 44 24: [20] FF FF FF FF  // MOV [RSP+20], 0xFFFFFFFF
    #     #                                  Overlapped.Offset = -1
    #     # 31 F6                       // XOR ESI, ESI
    #     # 45 31 C0                    // XOR R8D, R8D
    #     # 41 B9:     FF FF FF FF      // MOV R9D, 0xFFFFFFFF
    #     #                                  Overlapped.OffsetHigh = -1
    #     # FF 15:    [CB 31 48 06]     // CALL [<LockFileEx>]
    #     # 85 C0                       // TEST EAX, EAX
    #     # 75:       [0F]              // JNE [+0F], the if statement
    #     # Change JNZ to JMP in order to force check pass.
    #     print(f"\n> Blocking multi-instance check")
    #     UNLOCK_PATTERN = """
    #     C7 44 24 ?? FF FF FF FF
    #     31 F6
    #     45 31 C0
    #     41 B9 FF FF FF FF
    #     FF 15 ?? ?? ?? ??
    #     85 C0
    #     75 0F
    #     """
    #     UNLOCK_REPLACE = """
    #     ...
    #     EB 0F
    #     """
    #     data = wildcard_replace(data, UNLOCK_PATTERN, UNLOCK_REPLACE)
    #     # Backup and save
    #     backup(dll)
    #     save(dll, data)
    #     pause()

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

    def test_get_wnd_state(self):
        hwnd = 334080
        while True:
            curr_linked_wnd_state = SidebarUI.get_linked_wnd_state(hwnd)
            print(f"{hwnd}当前状态: "
                  f"最小化={curr_linked_wnd_state[WndProperties.IS_MINIMIZED]}, "
                  f"最大化={curr_linked_wnd_state[WndProperties.IS_MAXIMIZED]}, "
                  f"前台={curr_linked_wnd_state[WndProperties.IS_FOREGROUND]}, "
                  f"隐藏={curr_linked_wnd_state[WndProperties.IS_HIDDEN]},"
                  f"位置={curr_linked_wnd_state[WndProperties.RECT]}")  # 每次监听都打印状态

    def test_get_widget_by_name(self):
        main_hwnd = 93198856
        hwnd_utils.restore_window(main_hwnd)
        time.sleep(0.2)
        hwnd_utils.do_click_in_wnd(main_hwnd, 8, 8)
        hwnd_utils.do_click_in_wnd(main_hwnd, 8, 8)

    def test_get_WXWork_mmap(self):
        for f in psutil.Process(27644).memory_maps():
            print(f)

    def test_get_all_sw_mutant_handles(self):
        sw = "Weixin"
        mutant_handles = SwOperator.try_kill_mutex_if_need_and_return_remained_pids(sw)
        Printer().debug(mutant_handles)

    def test_get_handles_by_pids_and_handle_name_wildcards(self):
        pids = [47632]
        handle_names = ['_WeChat_App_Instance_Identity_Mutex_Name']
        handles = handle_utils.pywinhandle_find_handles_by_pids_and_handle_name_wildcards(pids, handle_names)
        print(handles)

    def test_my_find_handle_in_pid(self):
        pid = 30556
        handle_names = ["global_config"]
        result = handle_utils.pywinhandle_find_handles_by_pids_and_handle_names(
            [pid],
            handle_names
        )
        print(result)

    def test_search_from_features(self):
        dll_path = r'D:\software\Tencent\Weixin\4.0.5.13\Weixin.dll'
        original_features = [
            "E9 68 02 00 00 0F 1F 84 00 00 00 00 00",
            "6b ?? ?? 73 48 89 05 3a db 7f 00 66",
            "E4 B8 8D E6 94 AF E6 8C 81 E7 B1 BB E5 9E 8B E6 B6 88 E6 81 AF 5D 00",
            "9A 82 E4 B8 8D E6 94 AF E6 8C 81 E8 AF A5 E5 86 85 E5 AE B9 EF BC 8C"
        ]
        modified_features = [
            "3D 12 27 00 00 0F 85 62 02 00 00 90 90",
            "8B B5 20 04 00 00 81 C6 12 27 00 00",
            "E6 92 A4 E5 9B 9E E4 BA 86 E4 B8 80 E6 9D A1 E6 B6 88 E6 81 AF 5D 00",
            "92 A4 E5 9B 9E E4 BA 86 E4 B8 80 E6 9D A1 E6 B6 88 E6 81 AF 00 BC 8C"
        ]
        features_tuple = (original_features, modified_features)
        res = SwInfoUtils.search_pattern_dicts_by_original_and_modified(dll_path, features_tuple)
        print(res)

    def test_create_lnk_for_account(self):
        AccOperator._create_starter_lnk_for_acc("WeChat", "wxid_5daddxikoccs22")
        AccOperator._create_starter_lnk_for_acc("WeChat", "wxid_h5m0aq1uvr2f22")

    def test_uiautomation_control_wnd(self):
        """测试通过uiautomation来控制窗口"""
        hwnd = 463030
        wnd_ctrl = uiautomation.ControlFromHandle(hwnd)
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)

        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOP,
            100, 100, 800, 600,
            win32con.SWP_SHOWWINDOW
        )
        hwnd_utils.do_click_in_wnd(hwnd, 8, 8)
        hwnd_utils.do_click_in_wnd(hwnd, 8, 8)

    def test_render_custom_patches_demo(self):
        sample_data = [
            {
                "addr": "%dll_dir%/Weixin.dll",
                "patches": [
                    {
                        "offset": 140533195,
                        "original": "5b e4 b8 8d e6 94 af e6 8c 81 e7 b1 bb e5 9e 8b e6 b6 88 e6 81 af 5d 00",
                        "modified": "5b e6 92 a4 e5 9b 9e e4 ba 86 e4 b8 80 e6 9d a1 e6 b6 88 e6 81 af 5d 00",
                        "encoding": "utf-8",
                        "tip": "列表撤回提示消息, 显示格式为xxx, xxx部分可修改",
                        "note": "[不支持类型消息] -> [撤回了一条消息]",
                        "customizable": True
                    },
                    {
                        "offset": 140579905,
                        "original": "e6 9a 82 e4 b8 8d e6 94 af e6 8c 81 e8 af a5 e5 86 85 e5 ae b9 ef bc 8c e8 af b7 e5 9c a8 e6 89 8b e6 9c ba e4 b8 8a e6 9f a5 e7 9c 8b 00",
                        "modified": "e6 92 a4 e5 9b 9e e4 ba 86 e4 b8 80 e6 9d a1 e6 b6 88 e6 81 af 00 bc 8c e8 af b7 e5 9c a8 e6 89 8b e6 9c ba e4 b8 8a e6 9f a5 e7 9c 8b 00",
                        "encoding": "utf-8",
                        "tip": "窗口撤回提示消息, 显示格式为[xxx], xxx部分可修改",
                        "note": "暂不支持该内容，请在手机上查看 -> 撤回了一条消息",
                        "customizable": True
                    }
                ]
            }
        ]

        root = tk.Tk()
        root.title("补丁自定义界面 Demo")

        frame = tk.Frame(root)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        sw_func.render_custom_patches(frame, sample_data)

        root.mainloop()

    def test_show_popup(self):
        import tkinter as tk

        root = tk.Tk()

        frame = tk.Frame(root, width=200, height=100, bg="lightblue")
        frame.pack(padx=20, pady=20)

        # popup 的 parent 写 frame
        popup = tk.Menu(frame, tearoff=0)
        popup.add_command(label="Cut")
        popup.add_command(label="Copy")

        def show_popup(event):
            popup.post(event.x_root, event.y_root)

        root.bind("<Button-3>", show_popup)

        root.mainloop()
