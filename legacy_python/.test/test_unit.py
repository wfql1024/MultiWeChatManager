import ctypes
import glob
import json
import os
import random
import time
from datetime import datetime
from tkinter import messagebox
from unittest import TestCase

import psutil

from legacy_python.functions import subfunc_file
from legacy_python.functions.sw_func import SwInfoFunc, SwOperator, SwInfoUtils
from legacy_python.public import Config
from legacy_python.public.enums import MultirunMode, LocalCfg
from legacy_python.utils import hwnd_utils, handle_utils, process_utils, widget_utils
from legacy_python.utils import file_utils
from legacy_python.utils.hwnd_utils import Win32HwndGetter, HwndGetter


class Test(TestCase):
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
            subfunc_file.get_remote_cfg(
                "Weixin", executable=None, cfg_handle_regex_list=None))
        handle_utils.close_sw_mutex_by_handle(
            Config.HANDLE_EXE_PATH, executable_name, cfg_handles)

    def test_get_cfg_files(self):
        sw = "WeChat"
        acc = "wxid_t2dchu5zw9y022"
        data_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.DATA_DIR)
        if not data_path:
            return False, "无法获取WeChat数据路径"
        # config_path_suffix, cfg_basename_list = subfunc_file.get_remote_cfg(
        #     sw, config_path_suffix=None, config_file_list=None)

        config_addresses, = subfunc_file.get_remote_cfg(sw, config_addresses=None)
        if not isinstance(config_addresses, list):
            return False, "无法获取登录配置文件地址"
        for config_address in config_addresses:
            origin_cfg_path = SwInfoFunc.resolve_sw_path(sw, config_address)
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
        config_addresses, = subfunc_file.get_remote_cfg(sw, config_addresses=None)
        if not isinstance(config_addresses, list) or len(config_addresses) == 0:
            messagebox.showinfo("提醒", f"{sw}平台还没有适配")
            return
        # if (config_path_suffix is None or config_file_list is None or
        #         not isinstance(config_file_list, list) or len(config_file_list) == 0):
        #     messagebox.showinfo("提醒", f"{sw}平台还没有适配")
        #     return

        files_to_delete = []

        for addr in config_addresses:
            origin_cfg_path = SwInfoFunc.resolve_sw_path(sw, addr)
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
        path = SwInfoFunc.resolve_sw_path("Weixin", "%dll_dir%/Weixin.dll")
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
            result = SwInfoUtils.convert_hex_to_list_and_align_modified_to_original(
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

    def test_get_login_hwnds_of_sw(self):
        hwnds = SwInfoFunc.get_login_hwnds_of_sw("Weixin")
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
        SwInfoFunc.identify_dll_core("Weixin", "anti-revoke")

    def test_identify_coexist_dll(self):
        res = SwInfoFunc.identify_dll_core("WeChat", "anti-revoke", None, "default", "1")
        print(res)

    def test_switch_dll(self):
        SwOperator.switch_dll_core("Weixin", "anti-revoke", "alert")

    def test_update_adaptation_from_remote_to_cache(self):
        SwInfoFunc._update_adaptation_from_remote_to_cache("QQNT", "anti-revoke")

    def test_get_data(self):
        data = subfunc_file.get_remote_cfg("Weixin", "coexist", "channels", "default", "patch_wildcard")
        print(data)

    def test_create_coexist(self):
        SwOperator.create_coexist_exe_core("WXWork", "1")

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
        from legacy_python.components import CustomNotebook, NotebookDirection, CustomCornerBtn, CustomLabelBtn

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
