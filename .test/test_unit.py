import ctypes
import glob
import json
import os
import random
import threading
import time
from datetime import datetime
from tkinter import messagebox
from unittest import TestCase

import psutil
import win32api
import win32con
import win32gui
import win32process

from components import ScrollableText
from data_access.setting import RootSetting, RemoteSw, LocalSetting
from func_core.sw_func_core import SwOperatorCore, SwInfoFuncCore
from functions.sw_func import Sw
from public import Config
from public.enums import MultirunMode, LocalCfgKey, RemoteSwKey
from utils import hwnd_utils, handle_utils, process_utils, file_utils, widget_utils
from utils.hwnd_utils import Win32HwndGetter, HwndGetter
from utils.logger_utils import Printer
from utils.sys_utils import SysPathUtils


class Test(TestCase):
    sw_list = ["WeChat", "Weixin", "QQ", "QQNT", "WXWork", "TIM"]

    def SetUp(self):
        self.hwnd = Win32HwndGetter._get_a_hwnd_by_title("微信（测试版）")
        print(self.hwnd)

    def test_get_wnd_details_from_hwnd(self):
        details = hwnd_utils.get_hwnd_details_of_(10100452)
        print(details['class'])

    def test_wait_for_wnd_open(self):
        Win32HwndGetter.win32_wait_hwnd_by_class("Qt51514QWindowIcon")

    def test_close_sw_mutex_by_handle(self):
        executable_name, cfg_handles = (
            Sw("Weixin").get_remote(
                **{RemoteSwKey.EXE: None, RemoteSwKey.CONFIG_HANDLES: None}))
        handle_utils.close_sw_mutex_by_handle(
            Config.HANDLE_EXE_PATH, executable_name, cfg_handles)

    def test_get_cfg_files(self):
        sw = "WeChat"
        acc = "wxid_t2dchu5zw9y022"
        data_path = Sw(sw).try_get_path(LocalCfgKey.DATA_DIR)
        if not data_path:
            return False, "无法获取WeChat数据路径"
        # config_path_suffix, cfg_basename_list = RemoteSetting().get_(
        #     sw, config_path_suffix=None, config_file_list=None)

        config_addresses, = Sw(sw).get_remote(**{RemoteSwKey.CONFIG_ADDRESSES: None})
        if not isinstance(config_addresses, list):
            return False, "无法获取登录配置文件地址"
        for config_address in config_addresses:
            origin_cfg_path = SwInfoFuncCore.resolve_sw_path(sw, config_address)
            acc_cfg_path = os.path.join(os.path.dirname(origin_cfg_path), f"{acc}_{os.path.basename(origin_cfg_path)}")
            acc_cfg_path = acc_cfg_path.replace("\\", "/")
            print("新方法:")
            print(origin_cfg_path)
            print(acc_cfg_path)

        # # 构建相关文件列表
        # for cfg_basename in cfg_basename_list:
        #     # 拼接出源配置路径
        #     origin_cfg_path = os.path.join(
        #         str(data_path), str(config_path_suffix), str(cfg_basename)).replace("\\", "/")
        #     acc_cfg_item = f"{acc}_{cfg_basename}"
        #     acc_cfg_path = (os.path.join(os.path.dirname(origin_cfg_path), acc_cfg_item)
        #                     .replace("\\", "/"))
        #     print("旧方法:")
        #     print(origin_cfg_path)
        #     print(acc_cfg_path)
        return None

    def test_new_get_cfg_files(self):
        sw = "WeChat"
        config_addresses, = Sw(sw).get_remote(**{RemoteSwKey.CONFIG_ADDRESSES: None})
        if not isinstance(config_addresses, list) or len(config_addresses) == 0:
            messagebox.showinfo("提醒", f"{sw}平台还没有适配")
            return
        # if (config_path_suffix is None or config_file_list is None or
        #         not isinstance(config_file_list, list) or len(config_file_list) == 0):
        #     messagebox.showinfo("提醒", f"{sw}平台还没有适配")
        #     return

        files_to_delete = []

        for addr in config_addresses:
            origin_cfg_path = SwInfoFuncCore.resolve_sw_path(sw, addr)
            origin_cfg_dir = os.path.dirname(origin_cfg_path)
            origin_cfg_basename = os.path.basename(origin_cfg_path)
            acc_cfg_path_glob_wildcard = os.path.join(origin_cfg_dir, f"*_{origin_cfg_basename}")
            acc_cfg_paths = glob.glob(acc_cfg_path_glob_wildcard)
            acc_cfg_paths = [f.replace("\\", "/") for f in acc_cfg_paths]
            files_to_delete.extend([f for f in acc_cfg_paths if f != origin_cfg_path])

        print(files_to_delete)

    def test_get_all_open_files(self):
        pids = process_utils.get_process_ids_by_precise_name_impl_by_tasklist("Weixin")
        for pid in pids:
            for f in psutil.Process(pid).memory_maps():
                print(pid, f)

    def test_get_factor(self):
        SCALE_FACTOR = float(ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100)
        print(SCALE_FACTOR)
        awareness = ctypes.c_int()
        ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness))
        print(f"DPI Awareness Level: {awareness.value}")

    def test_get_process_ids_by_name(self):
        pids = process_utils.get_process_ids_by_precise_name_impl_by_tasklist("WeChat.exe")
        print(pids)

    def test_lowercase(self):
        text = "3C63CD2D88D247F930BB3E970EC73043"
        print(text.lower())

    def test_move_to_recycle_bin(self):
        file_to_delete = r"E:\Now\Desktop\微信多开管理器_调试版.lnk"
        file_utils.move_files_to_recycle_bin([file_to_delete])

    def test_calculate_md5(self):
        file_path = r"E:\Now\QuickCenter\WorkBench\技术梦想\项目\MultiWeChatManager\Releases\JhiFengMultiChat_win7_x64_v3.3.0.3718-Beta.zip"
        md5 = file_utils.calculate_md5(file_path)
        print(md5)

    def test_get_now_datetime(self):
        now = datetime.now()
        print(now)

    def test_get_nested_value(self):
        print("测试单次获取嵌套值----------------------------------------------------------------------------")
        # 获取嵌套值
        # 定义参数可用值列表
        data_values = [
            None,  # data 为 None
            2,  # data 为非字典类型
            {"a": {"b": {"c": 1}}}  # data 为嵌套字典
        ]

        key_path_values = [
            None,  # key_path 为 None
            "",  # key_path 为空字符串
            1,  # key_path 为非字符串类型
            "a",  # key_path 为单层路径
            "a/b",  # key_path 为多层路径
            "a/b/c",  # key_path 为多层路径
            "a/b/c/d"  # key_path 为不存在的路径
        ]

        # 遍历所有参数组合
        for data in data_values:
            for key_path in key_path_values:
                # 调用方法并获取结果
                result = file_utils.DictUtils._get_nested_value(data, key_path, default_value="default")
                # 输出参数和结果
                print(f"data: {data}, key_path: {key_path}, result: {result}")

    def test_six_randoms(self):
        for i in range(6):
            print(random.randint(0, 3))

    def test_equals(self):
        print(MultirunMode.BUILTIN == "python")

    def test_win32_and_uiautomation_get_hwnds(self):
        target_pid = 30556  # 这里替换成实际的 pid
        start_time = time.time()
        windows = hwnd_utils.get_wnd_dict_by_pid(target_pid)
        for w in windows:
            print(
                f"Handle: {w['hwnd']}, Name: {w['Name']}, ClassName: {w['ClassName']}, ControlType: {w['ControlType']}")
        print(f"用时: {time.time() - start_time}")
        start_time = time.time()
        hwnds = Win32HwndGetter.win32_get_hwnds_by_pid_and_class_wildcards(target_pid)
        print(hwnds)
        print(f"用时: {time.time() - start_time}")

    def test_resolve_addr(self):
        path = SwInfoFuncCore.resolve_sw_path("Weixin", "%dll_dir%/Weixin.dll")
        print(path)

    def test_convert_hex_to_list_and_align_modified_to_original(self):
        # 假设 SwInfoUtils 已经导入
        tests = [
            # 正常前向补齐
            {"original": "11 22 33 44 55 66 77 88", "modified": "... 55 66", "left_cut": 0, "right_cut": 0},
            # 正常后向补齐
            {"original": "11 22 33 44 55", "modified": "AA BB ...", "left_cut": 0, "right_cut": 0},
            # 原始串含非法...
            {"original": "11 22 ... 33", "modified": "AA", "left_cut": 0, "right_cut": 0},
            # 修改串过长-前向
            {"original": "11 22 33", "modified": "... 11 22 33 44", "left_cut": 0, "right_cut": 0},
            # 修改串过长-后向
            {"original": "11 22 33", "modified": "11 22 33 44 ...", "left_cut": 0, "right_cut": 0},
            # 修改串中间出现...
            {"original": "11 22 33 44", "modified": "11 ... 44", "left_cut": 0, "right_cut": 0},
            # 左右 cut
            {"original": "11 22 33 44 55 66", "modified": "AA BB CC DD EE", "left_cut": 1, "right_cut": 1},
            # 修改串为空
            {"original": "11 22 33", "modified": "", "left_cut": 0, "right_cut": 0},
            # 原始串太短不够 cut
            {"original": "11 22", "modified": "AA", "left_cut": 1, "right_cut": 2},
        ]

        for i, case in enumerate(tests, 1):
            print(f"\n=== Test Case {i} ===")
            result = SwInfoFuncCore.convert_hex_to_list_and_align_modified_to_original(
                case["original"],
                case["modified"],
                left_cut=case.get("left_cut", 0),
                right_cut=case.get("right_cut", 0)
            )
            if result is None:
                print("Result: None (Error)")
            else:
                listed_orig, listed_mod = result
                print(f"Original List: {listed_orig}")
                print(f"Modified List: {listed_mod}")

    def test_get_relations_of_channel(self):

        res = SwOperatorCore.get_relations_of_channel("Weixin", RemoteSwKey.REVOKE, "custom_alert")
        print(res)

    def test_get_login_hwnds_of_sw(self):
        hwnds = SwInfoFuncCore.get_login_hwnds_of_sw("Weixin")
        print(hwnds)

    def test_get_hwnds_sorted_by_zOrder(self):
        hwnds = Win32HwndGetter.get_visible_windows_by_zOrder()
        print(hwnds)

    def test_wait_hwnd_exclusively_by_class(self):
        sw_hwnd = Win32HwndGetter.win32_wait_hwnd_exclusively_by_class([], "mmui::MainWindow", 1)
        print(sw_hwnd)
        if sw_hwnd is None:
            # 从精确类名未能获取,只能用类名通配模式来获取,并缓存起来
            sw_hwnd, class_name = HwndGetter._uiautomation_wait_hwnd_exclusively_by_pid_and_class_wildcards(
                [], 34288, ["mmui::MainWindow"])
            print(sw_hwnd, class_name)

    def test_identify_dll(self):
        Sw("Weixin").identify_patch("anti-revoke")

    def test_identify_coexist_dll(self):
        res = Sw("WeChat").identify_patch("anti-revoke", None, "default", "1")
        print(res)

    def test_switch_dll(self):
        SwOperatorCore.switch_dll_core("Weixin", "anti-revoke", "alert")

    def test_update_adaptation_from_remote_to_cache(self):
        SwInfoFuncCore._update_adaptation_from_remote_to_cache("QQNT", "anti-revoke")

    def test_get_data(self):
        data = Sw("Weixin").get_remote("coexist", "channels", "default", "patch_wildcard")
        print(data)

    def test_create_coexist(self):
        SwOperatorCore.create_coexist_exe_core("WXWork", "1")

    def test_expand_records(self):
        def expand_records(data):
            expanded = []
            for item in data:
                item_type = item.get("type", "")
                originals = item.get("original", [])
                modifieds = item.get("modified", [])
                descripts = item.get("descript", [])

                # 三个数组长度应该一致，否则用最短的
                for o, m, d in zip(originals, modifieds, descripts):
                    expanded.append({
                        "type": item_type,
                        "original": o,
                        "modified": m,
                        "descript": d
                    })
            return expanded

        raw_data = [
            {
                "type": "simple",
                "original": [
                    "80 79 08 00 74 16 83 C1 0C 83 79 14 07 76 02 8B 09 51 8D 4A 18 51 FF 15 ?? ?? ?? 06 8D 8B DC 00 00 00 51 E8 ?? ?? ?? 01 8B 45 08 59",
                    "74 5D 39 B3 C4 00 00 00 74 55 8B CB E8 ?? D5 FF FF 8B CB E8 49 D0 FF FF 84 C0 75 43 8B BB CC 00 00 00 8B 07 C7 45 CC ?? ?? ?? 06 C7",
                    "73 76 69 64 3A 20 00 63 6F 6E 66 69 67 2E 64 62",
                    "43 6F 6E 66 69 67 2E 63 66 67",
                    "57 00 65 00 57 00 6F 00 72 00 6B 00 2E 00 41 00 63 00 74 00 69 00 76 00 61 00 74 00 65 00 41 00 70 00 70 00 6C 00 69 00 63 00 61 00 74 00 69 00 6F 00 6E 00",
                    "43 00 6F 00 6E 00 66 00 69 00 67 00 2E 00 63 00 66 00 67 00",
                    "63 00 6F 00 72 00 70 00 5F 00 6C 00 6F 00 67 00 6F 00",
                    "54 00 65 00 6E 00 63 00 65 00 6E 00 74 00 2E 00 57 00 65 00 57 00 6F 00 72 00 6B 00 2E 00 45 00 78 00 63 00 6C 00 75 00 73 00 69 00 76 00 65 00",
                    "63 6F 72 70 5F 6C 6F 67 6F",
                    "71 72 63 6F 64 65 5F 6C 6F 67 69 6E 5F 75 73 65 72 5F 61 76 61 74 6F 72",
                    "68 74 74 70 64 6E 73 2E 63 66 67 00 77 65 77 6F 72 6B"
                ],
                "modified": [
                    "83 42 08 !! 83 42 08 10 83 6A 0C 20 90 EB 0D ...",
                    "EB ...",
                    "... !! 2E 64 62",
                    "... !! 2E 63 66 67",
                    "... !! 00",
                    "... !! 00 2E 00 63 00 66 00 67 00",
                    "... !! 00",
                    "... !! 00 73 00 69 00 76 00 65 00",
                    "... !!",
                    "... !!",
                    "68 74 74 70 64 6E !! ..."
                ],
                "descript": [
                    " ̲.  ̲B  .  ̲0  ̲.  ̲B  ̲.  ̲.  ̲.  ̲j  ̲.  ̲   ̲.  ̲.  ̲.  .  .  Q  .  J  .  Q  .  .  .     \"  .  .  .  .  .  .  .  Q  .  .  .  .  .  .  E  .  Y",
                    " ̲t  ]  9  .  .  .  .  .  t  U  .  .  .  .  .  .  .  .  .  .  I  .  .  .  .  .  u  C  .  .  .  .  .  .  .  .  .  E  .  .  .  .  .  .",
                    " s  v  i  d  :     .  c  o  n  f  i  ̲g  .  d  b",
                    " C  o  n  f  i  ̲g  .  c  f  g",
                    " W  .  e  .  W  .  o  .  r  .  k  .  .  .  A  .  c  .  t  .  i  .  v  .  a  .  t  .  e  .  A  .  p  .  p  .  l  .  i  .  c  .  a  .  t  .  i  .  o  .  ̲n  .",
                    " C  .  o  .  n  .  f  .  i  .  ̲g  .  .  .  c  .  f  .  g  .",
                    " c  .  o  .  r  .  p  .  _  .  l  .  o  .  g  .  ̲o  .",
                    " T  .  e  .  n  .  c  .  e  .  n  .  t  .  .  .  W  .  e  .  W  .  o  .  r  .  k  .  .  .  E  .  x  .  c  .  l  .  ̲u  .  s  .  i  .  v  .  e  .",
                    " c  o  r  p  _  l  o  g  ̲o",
                    " q  r  c  o  d  e  _  l  o  g  i  n  _  u  s  e  r  _  a  v  a  t  o  ̲r",
                    " h  t  t  p  d  n  ̲s  .  c  f  g  .  w  e  w  o  r  k"
                ]
            }
        ]

        expanded_data = expand_records(raw_data)
        print(json.dumps(expanded_data, ensure_ascii=False, indent=4))

    def test_custom_notebook_and_custom_btn(self):
        import tkinter as tk
        from tkinter import ttk
        from components import CustomNotebook, NotebookDirection, CustomCornerBtn, CustomLabelBtn

        tk_root = tk.Tk()
        tk_root.geometry("400x300")

        def printer(click_time):
            print("按钮功能:连点次数为", click_time)

        # 创建竖向Notebook（左侧）
        my_nb_cls = CustomNotebook(tk_root, tk_root, direction=NotebookDirection.LEFT)

        # 创建横向Notebook（顶部）
        # my_nb_cls = CustomNotebook(tk_root, tk_root, direction=NotebookDirection.TOP)

        # 设置颜色（使用正绿色）
        my_nb_cls.set_major_color(selected_bg='#00FF00')

        nb_frm_pools = my_nb_cls.frames_pool

        # 创建标签页
        frame1 = ttk.Frame(nb_frm_pools)
        frame2 = ttk.Frame(nb_frm_pools)
        frame3 = ttk.Frame(nb_frm_pools)
        frame4 = ttk.Frame(nb_frm_pools)

        # 在标签页1中添加CustomLabelBtn
        btn1 = CustomCornerBtn(frame1, text="标签按钮1")
        # btn1.on_click(lambda: print("按钮1被点击"))
        btn1.pack(pady=10)
        widget_utils.UnlimitedClickHandler(
            tk_root, btn1,
            printer
        )
        btn2 = CustomLabelBtn(frame1, text="标签按钮2")
        # btn2.on_click(lambda: print("按钮2被点击"))
        btn2.pack(pady=10)

        # 在标签页2中添加CustomLabelBtn和标签
        ttk.Label(frame2, text="这是标签页2").pack(pady=10)
        btn3 = CustomLabelBtn(frame2, text="标签按钮3")
        # btn3.on_click(lambda: print("按钮3被点击"))
        btn3.pack(pady=10)

        # 在标签页3中添加CustomLabelBtn组
        btn_frame = ttk.Frame(frame3)
        btn_frame.pack(pady=20)
        btn4 = CustomLabelBtn(btn_frame, text="标签按钮4")
        # btn4.on_click(lambda: print("按钮4被点击"))
        btn4.pack(side='left', padx=5)
        btn5 = CustomLabelBtn(btn_frame, text="标签按钮5")
        # btn5.on_click(lambda: print("按钮5被点击"))
        btn5.pack(side='left', padx=5)

        # 添加标签页
        my_nb_cls.add("tab1", "标签1", frame1)
        my_nb_cls.add("tab2", "标签2", frame2)
        my_nb_cls.add("tab3", "标签3", frame3)
        my_nb_cls.all_set_bind_func(printer).all_apply_bind(tk_root)

        my_nb_cls.add("tab4", "标签4", frame4)

        btn = CustomCornerBtn(frame1, text="MI", corner_radius=100, width=300)
        btn.set_major_colors("#ffc500").redraw()
        btn.pack(padx=20, pady=20)
        print(btn.__dict__)

        tk_root.mainloop()

    @staticmethod
    def test_postmessage_restore():
        """方案1：用 PostMessage 异步恢复窗口"""
        hwnd = 18881850
        print("==> 测试 PostMessage 异步恢复窗口")

        win32gui.PostMessage(hwnd, win32con.WM_SYSCOMMAND, win32con.SC_RESTORE, 0)
        win32gui.PostMessage(hwnd, win32con.WM_SETFOCUS, 0, 0)
        win32gui.SetForegroundWindow(hwnd)
        print("窗口已发送恢复与前台请求")

    @staticmethod
    def test_invoke_threadsafe():
        """方案2：模拟 Qt 主线程调用（仅演示结构）"""
        hwnd = 18881850
        print("==> 测试 Qt 主线程安全调用（示意）")

        # 在真实 PyQt 程序中应使用 QMetaObject.invokeMethod()
        # 这里只模拟主线程执行的逻辑
        def show_window():
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            print("窗口在主线程中被恢复并激活")

        threading.Timer(0, show_window).start()

    @staticmethod
    def test_foreground_external():
        """方案3：唤起外部 Qt 程序窗口"""
        hwnd = 18881850
        print("==> 测试外部程序窗口唤起")

        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception as e:
            print("前台置顶失败:", e)
            win32gui.FlashWindow(hwnd, True)
        else:
            print("窗口已置顶")

    @staticmethod
    def test_async_thread_postmessage():
        """方案4：子线程中执行异步 PostMessage"""
        hwnd = 18881850
        print("==> 测试子线程中执行 PostMessage")

        def worker():
            print("[子线程] 开始发送窗口恢复消息")
            win32gui.PostMessage(hwnd, win32con.WM_SHOWWINDOW, 1, 0)
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            print("[子线程] 窗口唤起完成")

        threading.Thread(target=worker, daemon=True).start()
        time.sleep(0.5)  # 给线程时间完成

    @staticmethod
    def test_attach_thread_input():
        """方案5：使用 AttachThreadInput 提升前台权限"""
        hwnd = 18881850
        print("==> 测试 AttachThreadInput 方式")

        try:
            fg_thread = win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[0]
            this_thread = win32api.GetCurrentThreadId()
            win32process.AttachThreadInput(fg_thread, this_thread, True)

            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            print("窗口已通过 AttachThreadInput 唤起")

        except Exception as e:
            print("AttachThreadInput 失败:", e)

        finally:
            win32process.AttachThreadInput(fg_thread, this_thread, False)
            print("已解除线程输入附加")

    def test_use_root_config(self):
        RootSetting().update_("user_path", r".\user_files")

    def test_setting_obj(self):
        """测试设置对象"""
        setting = RootSetting()
        print(setting)
        print(setting.load())
        setting = RootSetting()
        print(setting)
        print(setting.load())
        # setting = RootSetting(Config.ROOT_CONFIG_PATH)
        # print(setting)
        # print(setting.load())
        setting = RootSetting(RemoteSw().get_file_path_from_root_cfg())
        print(setting)
        print(setting.load())
        setting = RootSetting()
        print(setting)
        print(setting.load())

    def test_local_setting_obj(self):
        """测试本地设置对象"""
        setting = LocalSetting()
        print(setting)
        print(setting.load())
        setting = LocalSetting()
        print(setting)
        print(setting.load())
        setting = LocalSetting(LocalSetting().get_file_path_from_root_cfg())
        print(setting)
        print(setting.load())
        setting = LocalSetting(RemoteSw().get_file_path_from_root_cfg())
        print(setting)
        print(setting.load())
        setting = LocalSetting()

    def test_get_environ(self):
        """测试获取环境变量"""
        print(os.environ.get('ProgramFiles(x86)'))

    def test_get_sw_data_dir_from_user_register(self):
        print("inst_path", "-------------------------")
        for sw in self.sw_list:
            # print(sw)
            # paths = SwInfoFuncCore.get_sw_inst_path_from_register(sw)
            # print(paths)
            # paths = SwInfoFuncCore.guess_sw_inst_path(sw)
            # print(paths)
            paths = SwInfoFuncCore._get_sw_inst_path_by_regex(sw)
            print(paths)

        print("data_dir", "-------------------------")
        for sw in self.sw_list:
            # print(sw)
            # paths = SwInfoFuncCore.get_sw_data_dir_from_register(sw)
            # print(paths)
            # paths = SwInfoFuncCore.guess_sw_data_dir(sw)
            # print(paths)
            paths = SwInfoFuncCore._get_sw_data_dir_by_regex(sw)
            print(paths)

        print("dll_dir", "-------------------------")
        for sw in self.sw_list:
            # print(sw)
            # paths = SwInfoFuncCore.get_sw_dll_dir_from_register(sw)
            # print(paths)
            # paths = SwInfoFuncCore.guess_sw_dll_dir(sw)
            # print(paths)
            paths = SwInfoFuncCore._get_sw_dll_dir_by_regex(sw)
            print(paths)

    def test_get_documents(self):
        path = SysPathUtils.get_documents_path()
        print(path)

    def test_try_capt_avatar_for_sw_when(self):
        SwInfoFuncCore.try_capt_avatar_for_sw_when("Weixin", "main", 68304)

    def test_print_hwnds_to_md(self):
        HwndGetter._print_hwnds_to_md([19469250, 2692900, 2228330, 2034380, 986616])

    def test_gitee_download(self):
        from curl_cffi import requests as cffi_requests
        import os

        def impersonated_download(url, save_path):
            """
            使用curl_cffi模拟浏览器进行下载，绕过指纹检测。
            """
            try:
                # 关键：impersonate参数指定模拟的浏览器版本
                response = cffi_requests.get(
                    url,
                    impersonate="chrome110",  # 可改为 "chrome", "edge", "safari" 等
                    stream=True,
                    timeout=60
                )
                response.raise_for_status()

                # 获取文件大小用于显示进度
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                block_size = 8192

                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=block_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                print(f"\r下载进度: {percent:.1f}% ({downloaded}/{total_size} bytes)", end='',
                                      flush=True)
                print(f"\n✅ 文件已成功下载至: {save_path}")
                return True

            except Exception as e:
                print(f"❌ 下载失败: {e}")
                # 如果文件已部分下载，删除不完整文件
                if os.path.exists(save_path):
                    os.remove(save_path)
                return False

        # 使用你的原始链接
        file_url = "https://gitee.com/wfql1024/MultiWeChatManager/releases/download/v3.3.0.3718-Beta/JhiFengMultiChat_win10%20_x64_v3.3.0.3718-Beta.zip"
        save_location = "E:/Now/Desktop/JhiFengMultiChat.zip"

        impersonated_download(file_url, save_location)

    def test_print_simplify(self):
        msgs = ["初筛: []"] * 5 + ["下一步: 处理"] + ["初筛: []"]

        for m in msgs:
            Printer().print_simplify(m)
            time.sleep(0.2)  # 模拟处理时间

        # 最后一条消息换行
        Printer().print_simplify_stop()

        Printer().debug("测试结束")

    def test_scrollable_text(self):
        import tkinter as tk
        from tkinter import ttk

        root = tk.Tk()
        root.title("ScrollableText Test Bench")
        root.geometry("400x400")

        # ===============================
        # 测试区域（可清空）
        # ===============================
        test_area = tk.Frame(root, bg="#f0f0f0")
        test_area.pack(fill="both", expand=True)

        def clear_test_area():
            for w in test_area.winfo_children():
                w.destroy()

        # ===============================
        # 各个测试用例
        # ===============================
        def test_default_vertical():
            clear_test_area()
            text = ScrollableText(test_area)
            text.pack(fill="both", expand=True)
            for i in range(200):
                text.insert("end", f"Line {i}\n")

        def test_no_scrollbar():
            clear_test_area()
            text = ScrollableText(test_area, show_scrollbar=False)
            text.pack(fill="both", expand=True)
            for i in range(200):
                text.insert("end", f"Line {i}\n")

        def test_disable_auto_scroll():
            clear_test_area()
            text = ScrollableText(test_area)
            text.pack(fill="both", expand=True)
            for i in range(200):
                text.insert("end", f"Line {i}\n")
            text.disable_auto_scroll_y()

        def test_horizontal_scroll():
            print("清理前")
            clear_test_area()
            print("清理后")
            frame = tk.Frame(test_area)
            frame.pack(fill="both", expand=True)

            text = ScrollableText(frame, wrap="none")

            # 外部创建横向滚动条
            xbar = tk.Scrollbar(frame, orient="horizontal")
            xbar.pack(side="bottom", fill="x")
            text.set_scrollbar(xbar)
            # 外部创建纵向滚动条
            y_bar = tk.Scrollbar(frame, orient="vertical")
            y_bar.pack(side="right", fill="y")
            text.set_scrollbar(y_bar)

            text.enable_auto_scroll_x()

            text.pack(side="top", fill="both", expand=True)

            for i in range(50):
                text.insert(
                    "end",
                    ("This is a very very very very very long line → " * 2) + "\n"
                )

        def test_switch_axis_runtime():
            clear_test_area()

            frame = tk.Frame(test_area)
            frame.pack(fill="both", expand=True)

            text = ScrollableText(frame, wrap="none")
            text.pack(fill="both", expand=True)

            for i in range(200):
                text.insert("end", f"Line {i} " * 50 + "\n")

            def switch():
                xbar = ttk.Scrollbar(frame, orient="horizontal")
                xbar.pack(side="bottom", fill="x")
                text.add_scrollbar(xbar)

            # 3 秒后切换为横向滚动
            root.after(3000, switch)

        # ===============================
        # 底部按钮区
        # ===============================
        btn_bar = tk.Frame(root)
        btn_bar.pack(side="bottom", fill="x")

        buttons = [
            ("默认纵向滚动", test_default_vertical),
            ("无滚动条", test_no_scrollbar),
            ("禁用自动滚动", test_disable_auto_scroll),
            ("横向滚动", test_horizontal_scroll),
            ("运行时切换方向", test_switch_axis_runtime),
        ]

        for text, cmd in buttons:
            tk.Button(btn_bar, text=text, command=cmd).pack(
                side="left", padx=5, pady=5
            )

        # 默认先跑一个
        test_horizontal_scroll()

        root.mainloop()

    def test_safe_delete_scrollbar(self):
        import tkinter as tk

        def create_widgets():
            global text_area, v_scrollbar
            frame = tk.Frame(root)
            frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

            # 创建Text部件
            text_area = tk.Text(frame, wrap=tk.NONE)
            text_area.grid(row=0, column=0, sticky='nsew')

            # 创建Scrollbar并与Text绑定
            v_scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=text_area.yview)
            v_scrollbar.grid(row=0, column=1, sticky='ns')
            text_area.configure(yscrollcommand=v_scrollbar.set)

            # 配置网格权重，使Text可扩展
            frame.grid_rowconfigure(0, weight=1)
            frame.grid_columnconfigure(0, weight=1)

            # 创建一个用于销毁滚动条的按钮
            destroy_btn = tk.Button(root, text="安全销毁滚动条", command=safe_destroy_example)
            destroy_btn.pack(pady=5)

        def safe_destroy_example():
            """按钮调用的安全销毁函数"""
            if 'v_scrollbar' in globals() and v_scrollbar.winfo_exists():
                # 1. 关键：设置一个哑回调函数，吃掉所有调用
                def dummy_set(first, last):
                    pass  # 什么都不做，静默拦截

                text_area.configure(yscrollcommand=dummy_set)  # 替换，不是None!
                # 2. 从grid布局中移除
                v_scrollbar.grid_forget()
                # 3. 销毁对象
                v_scrollbar.destroy()

                # 可选：调整Text布局，让其重新填满原来滚动条的空间
                text_area.grid(columnspan=2)  # 假设原来占1列，现在扩展到2列

                print("滚动条已安全销毁。")
            else:
                print("滚动条不存在或已被销毁。")

        root = tk.Tk()
        root.title("安全销毁Scrollbar示例")
        create_widgets()
        root.mainloop()
