import os
import shutil
import time
import tkinter as tk
from datetime import datetime
from unittest import TestCase

import mss
import psutil
import uiautomation
import uiautomation as auto
import win32con
import win32gui
import winshell

from func_core.acc_func_core import AccOperatorCore
from func_core.sw_func_core import SwOperatorCore, SwInfoFuncCore
from functions import sw_func
from functions.sw_func import Sw
from public import Config
from public.enums import RemoteSwKey
from ui.sidebar_ui import SidebarUI, WndProperties
from utils import handle_utils, hwnd_utils
from utils.hwnd_utils import Win32HwndGetter
from utils.logger_utils import Printer


class Test(TestCase):
    def test_get_wnd_by_classname(self):
        hwnds = Win32HwndGetter.win32_wait_hwnd_by_class("Qt51514QWindowIcon")
        print(hwnds)

    def test_multi_new_weixin(self):
        executable_name, cfg_handles = Sw("Weixin").get_remote(
            **{RemoteSwKey.EXE: None, RemoteSwKey.CONFIG_HANDLES: None})
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

    # def test_get_ini_config(self):
    #     ini_path = fr'{Config.PROJ_USER_PATH}/setting.ini'
    #     config = IniUtils.load_ini_as_dict(ini_path)
    #     print(config.__dict__)

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
        mutant_handles = SwOperatorCore.try_kill_mutex_if_need_and_return_remained_pids(sw)
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
        res = SwInfoFuncCore.search_pattern_dicts_by_original_and_modified(dll_path, features_tuple)
        print(res)

    def test_create_lnk_for_account(self):
        AccOperatorCore._create_starter_lnk_for_acc("WeChat", "wxid_5daddxikoccs22")
        AccOperatorCore._create_starter_lnk_for_acc("WeChat", "wxid_h5m0aq1uvr2f22")

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

    def test_get_mmap_info(self):
        import re

        def match_and_capture(path: str, pattern: str):
            m = re.match(pattern, path)
            # print(m)
            return m.group(1) if m else None

        pid = 26172
        for f in psutil.Process(pid).memory_maps():
            normalized_path = f.path.replace('\\', '/')
            print(normalized_path)
            # print(match_and_capture(normalized_path, r"^(.*?)/Profiles/[0-9A-Fa-f]+(/.*)?$"))

    # def test_gdi_sct(self):
    #     ### 已经移入工具类
    #     import uiautomation as auto
    #     import os
    #
    #     # ----------------------------
    #     # 假设已拿到 hwnd
    #     # ----------------------------
    #     hwnd = 69372
    #
    #     win = auto.ControlFromHandle(hwnd)
    #
    #     # 查找目标控件（按 Name，按需修改）
    #     target = win.Control(ClassName="mmui::MainTabBar")
    #     rect = target.BoundingRectangle
    #     left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
    #     width, height = right - left, bottom - top
    #
    #     # 窗口矩形（屏幕坐标）
    #     win_left, win_top, win_right, win_bottom = win32gui.GetWindowRect(hwnd)
    #
    #     # 计算控件相对窗口的坐标
    #     rel_left = left - win_left
    #     rel_top = top - win_top
    #
    #     # 获取真实桌面路径
    #     desktop = winshell.desktop()
    #     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #     save_path = os.path.join(desktop, f"capture_{timestamp}.png")
    #
    #     # 截控件区域（GDI，窗口可被遮挡或最小化）
    #     hwnd_dc = win32gui.GetWindowDC(hwnd)
    #     mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    #     save_dc = mfc_dc.CreateCompatibleDC()
    #
    #     bitmap = win32ui.CreateBitmap()
    #     bitmap.CreateCompatibleBitmap(mfc_dc, 43, 43)
    #     save_dc.SelectObject(bitmap)
    #
    #     # 从窗口缓冲区拷贝指定矩形
    #     save_dc.BitBlt((-30,-30), (43, 43), mfc_dc, (rel_left+15, rel_top+31), win32con.SRCCOPY)
    #
    #     # 转为 PIL Image 并保存
    #     bmpinfo = bitmap.GetInfo()
    #     bmpstr = bitmap.GetBitmapBits(True)
    #     im = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
    #                           bmpstr, 'raw', 'BGRX', 0, 1)
    #     im.save(save_path)
    #
    #     print(f"控件区域已保存到: {save_path}")

    def test_capture_in_hwnd(self):
        desktop = winshell.desktop()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(desktop, f"capture_{timestamp}.png")

        # # Weixin
        # weixin_cfg = [
        #     {
        #         "type": "kwargs",
        #         "rule": {"ClassName": "mmui::MainTabBar"}
        #     }
        # ]
        # image_utils.capture_in_hwnd(
        #     69372, save_path,
        #     "20%w", "41%w", "-77%w", "-98%w",
        #     cfg=weixin_cfg
        # )

    #         # WeChat
    #         wechat_cfg = [
    #   {
    #     "type": "location",
    #     "rule": [
    #       { "control": "PaneControl", "kwargs": { "foundIndex": 2 } },
    #       { "control": "PaneControl", "kwargs": { "foundIndex": 1 } },
    #       { "control": "ToolBarControl", "kwargs": { "foundIndex": 1 } },
    #       { "control": "ButtonControl", "kwargs": { "foundIndex": 1 } }
    #     ]
    #   }
    # ]
    #         image_utils.capture_in_hwnd(
    #             267908, save_path,
    #             cfg=wechat_cfg)

    # # WXWork
    # wxwork_cfg = [
    #     {
    #         "type": "kwargs",
    #         "rule": {"ClassName": "TitleBarWindow"}
    #     }
    # ]
    # image_utils.capture_in_hwnd(
    #     268338, save_path,
    #     "60%h", "96%h", "-139%h", "-175%h",
    #     cfg=wxwork_cfg
    # )

    # # QQNT
    # qqnt_cfg = []
    # image_utils.capture_in_hwnd(
    #     133212, save_path,
    #     # "68*", "8*", "-91*", "-31*",
    #     cfg=qqnt_cfg
    # )

    # QQ
    # qq_cfg = [
    #     {
    #         "type": "location",
    #         "rule": [
    #           { "control": "PaneControl", "kwargs": { "foundIndex": 2 } },
    #           { "control": "PaneControl", "kwargs": { "foundIndex": 1 } },
    #           { "control": "PaneControl", "kwargs": { "foundIndex": 2 } },
    #           { "control": "PaneControl", "kwargs": { "foundIndex": 1 } },
    #           { "control": "PaneControl", "kwargs": { "foundIndex": 1 } },
    #           { "control": "PaneControl", "kwargs": { "foundIndex": 1 } },
    #           { "control": "PaneControl", "kwargs": { "foundIndex": 1 } },
    #           { "control": "ButtonControl", "kwargs": { "foundIndex": 1 } },
    #           { "control": "PaneControl", "kwargs": { "foundIndex": 1 } },
    #         ]
    #       }
    # ]
    # image_utils._get_capture_location_and_size(
    #     136624,
    #     10, 10, -20, -20,
    #     cfg=qq_cfg
    # )

    def test_print_tree(self):
        def print_tree(ctrl, depth=0):
            indent = "  " * depth
            print(
                f"{indent}{ctrl.ControlTypeName} Name={ctrl.Name!r} ClassName={ctrl.ClassName!r} Rect={ctrl.BoundingRectangle}")

            for child in ctrl.GetChildren():
                print_tree(child, depth + 1)

        win = auto.ControlFromHandle(333212)
        print_tree(win)

        # target = (
        #     win.PaneControl(foundIndex=2)
        #     .PaneControl(foundIndex=1)
        #     .ToolBarControl(foundIndex=1)
        #     .ButtonControl(foundIndex=1)
        # )
        # print(target)

    # def test_dxcam(self):
    #     ### 废弃...
    #     # 1) 你的窗口
    #     hwnd = 136624
    #     l, t, r, b = win32gui.GetWindowRect(hwnd)
    #
    #     # 2) 内部坐标
    #     local_left = 40
    #     local_top = 60
    #     w = 300
    #     h = 200
    #
    #     # 3) 计算全局坐标
    #     x1 = l + local_left
    #     y1 = t + local_top
    #     x2 = x1 + w
    #     y2 = y1 + h
    #
    #     # 4) ⬅ 转换为目标屏幕坐标（关键！）
    #     bbox = to_screen_local_coords(hwnd, x1, y1, x2, y2)
    #
    #     # 5) 使用正确屏幕实例化 dxcam
    #     idx = get_monitor_index_from_hwnd(hwnd)
    #     cam = dxcam.create(output_idx=idx)
    #
    #     # 6) 截图
    #     frame = cam.grab(bbox)
    #     print(frame)
    #     # 去掉 alpha
    #     bgr = frame[:, :, :3]
    #
    #     # gamma 矫正：linear -> sRGB
    #     gamma = 2.2
    #     corrected = ((bgr / 255.0) ** (1 / gamma)) * 255
    #     corrected = corrected.astype("uint8")
    #     frame = cv2.cvtColor(frame[:, :, :3], cv2.COLOR_BGRA2BGR)
    #
    #
    #     desktop = winshell.desktop()
    #     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #     save_path = os.path.join(desktop, f"capture_{timestamp}.png")
    #     cv2.imwrite(save_path, frame)
    #     print("已保存到:", save_path)

    def test_(self):
        def capture_window(hwnd, output):
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top

            with mss.mss() as sct:
                img = sct.grab({
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height
                })
                mss.tools.to_png(img.rgb, img.size, output=output)

        desktop = winshell.desktop()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(desktop, f"capture_{timestamp}.png")
        capture_window(136624, save_path)

    # import win32api

    # def get_monitor_index_from_hwnd(hwnd):
    #     l, t, r, b = win32gui.GetWindowRect(hwnd)
    #     cx = (l + r) // 2
    #     cy = (t + b) // 2
    #     monitors = win32api.EnumDisplayMonitors()
    #     for idx, (hMonitor, hdcMonitor, (ml, mt, mr, mb)) in enumerate(monitors):
    #         if ml <= cx <= mr and mt <= cy <= mb:
    #             return idx
    #     return 0

    # def to_screen_local_coords(hwnd, x1, y1, x2, y2):
    #     monitors = win32api.EnumDisplayMonitors()
    #     idx = get_monitor_index_from_hwnd(hwnd)
    #     (_, _, (ml, mt, mr, mb)) = monitors[idx]
    #     return (x1 - ml, y1 - mt, x2 - ml, y2 - mt)

    def test_listen_hwnd(self):
        root = tk.Tk()
        # root.overrideredirect(True)  # 无边框
        root.attributes("-topmost", True)
        root.geometry("120x40+0+0")

        label = tk.Label(root, text="Sidebar", bg="black", fg="white")
        label.pack(fill="both", expand=True)

        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        EVENT_OBJECT_LOCATIONCHANGE = 0x800B
        WINEVENT_OUTOFCONTEXT = 0x0000
        OBJID_WINDOW = 0

        WinEventProcType = ctypes.WINFUNCTYPE(
            None,
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.HWND,
            wintypes.LONG,
            wintypes.LONG,
            wintypes.DWORD,
            wintypes.DWORD,
        )

        target_hwnd = 264990  # ← 你绑定的窗口 hwnd
        latest_rect = None  # (l, t, r, b)

        def win_event_proc(hWinEventHook, event, hwnd,
                           idObject, idChild,
                           dwEventThread, dwmsEventTime):
            # 只关心窗口本体
            if idObject != OBJID_WINDOW:
                return

            # 只关心目标窗口
            if hwnd != target_hwnd:
                return

            if event == EVENT_OBJECT_LOCATIONCHANGE:
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                print("Target window moved:", rect.left, rect.top, rect.right, rect.bottom)

            rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                latest_rect = (rect.left, rect.top, rect.right, rect.bottom)
                l, t, r, b = latest_rect
                root.geometry(f"+{l}+{t}")

        callback = WinEventProcType(win_event_proc)

        hook = user32.SetWinEventHook(
            EVENT_OBJECT_LOCATIONCHANGE,
            EVENT_OBJECT_LOCATIONCHANGE,
            0,
            callback,
            0,
            0,
            WINEVENT_OUTOFCONTEXT,
        )

        if not hook:
            raise RuntimeError("SetWinEventHook failed")

        print("Hook installed for target window.")

        # root.mainloop()

        # 同步 Tk
        root.update_idletasks()
        root.update()

        msg = wintypes.MSG()
        last_applied = None

        while True:
            # 处理 WinEvent 消息（非阻塞）
            while user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

            # 同步 Tk
            root.update_idletasks()
            root.update()

            # 如果目标窗口位置变了，就贴过去
            if latest_rect and latest_rect != last_applied:
                l, t, r, b = latest_rect
                root.geometry(f"+{l}+{t}")
                last_applied = latest_rect
