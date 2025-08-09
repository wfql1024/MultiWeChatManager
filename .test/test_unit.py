import ctypes
import random
import time
from datetime import datetime
from unittest import TestCase

import psutil

from functions import subfunc_file
from functions.sw_func import SwInfoFunc
from public_class.enums import MultirunMode
from resources import Config
from utils import hwnd_utils, handle_utils, process_utils, file_utils, widget_utils


class Test(TestCase):
    def SetUp(self):
        self.hwnd = hwnd_utils.get_a_hwnd_by_title("微信（测试版）")
        print(self.hwnd)

    def test_get_wnd_details_from_hwnd(self):
        details = hwnd_utils.get_hwnd_details_of_(10100452)
        print(details['class'])

    def test_get_sw_data_dir(self):
        print(SwInfoFunc.detect_sw_data_dir(sw="Weixin"))

    def test_wait_for_wnd_open(self):
        hwnd_utils.win32_wait_hwnd_by_class("Qt51514QWindowIcon")

    def test_close_sw_mutex_by_handle(self):
        redundant_wnd_list, login_wnd_class, executable_name, cfg_handles = (
            subfunc_file.get_remote_cfg(
                "Weixin", redundant_wnd_class=None, login_wnd_class=None, executable=None, cfg_handle_regex_list=None))
        handle_utils.close_sw_mutex_by_handle(
            Config.HANDLE_EXE_PATH, executable_name, cfg_handles)

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

    def test_hide_wnd(self):
        pid = 20468  # 替换为目标进程的 PID
        target_class = "WeChatMainWndForPC"  # 替换为目标窗口类名
        test_hwnd = hwnd_utils.get_hwnds_by_pid_and_class(pid, target_class)
        hwnd_utils.hide_all_by_wnd_classes([target_class])
        print("Found HWNDs:", test_hwnd)

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

    def test_get_nested_values(self):
        print("测试批量获取嵌套值----------------------------------------------------------------------------")
        default_value = "default"
        separator = "/"
        # 批量获取嵌套值
        # 定义参数可用值列表
        data_values = [
            None,  # data 为 None
            2,  # data 为非字典类型
            {"a": {"b": {"c": 1}}}  # data 为嵌套字典
        ]

        front_addr_lists = [
            None,
            [""],
            [1],
            ["a", 1],
            ["a/b", ""],
            ["a/b", "c"],
            ["a", "b", "c"]
        ]

        default_dicts = [
            None,
            {"": "default"},
            {"a": "default"},
            {"b/d": "default"},
            {"c/a": "default"}
        ]

        # 遍历所有参数组合
        for data in data_values:
            for front_addr_list in front_addr_lists:
                # 调用方法并获取结果
                if front_addr_list is None:
                    for default_dict in default_dicts:
                        if default_dict is None:
                            result = file_utils.DictUtils.get_nested_values(data, default_value, separator)
                        else:
                            result = file_utils.DictUtils.get_nested_values(data, default_value, separator,
                                                                            **default_dict)
                        # 输出参数和结果
                        print(
                            f"data: {data}, front_addr_list: {front_addr_list}, default_dict: {default_dict}, result: {result}")
                else:
                    for default_dict in default_dicts:
                        if default_dict is None:
                            result = file_utils.DictUtils.get_nested_values(data, default_value, separator,
                                                                            *front_addr_list)
                        else:
                            result = file_utils.DictUtils.get_nested_values(data, default_value, separator,
                                                                            *front_addr_list, **default_dict)
                        # 输出参数和结果
                        print(
                            f"data: {data}, front_addr_list: {front_addr_list}, default_dict: {default_dict}, result: {result}")

        # 修改嵌套值
        data = {"a": {"b": {"c": 1}}}
        self.assertEqual(file_utils.DictUtils._set_nested_value(None, None, 1), False)  # 无法修改

        data = {"a": {"b": {"c": 1}}}
        self.assertEqual(file_utils.DictUtils._set_nested_value(1, None, 1), False)  # 无法修改

        data = {"a": {"b": {"c": 1}}}
        self.assertEqual(file_utils.DictUtils._set_nested_value(data, 1, None), False)  # 无法修改

        data = {"a": {"b": {"c": 1}}}
        self.assertEqual(file_utils.DictUtils._set_nested_value(data, "a/b", None), True)  # 成功修改
        self.assertEqual(data, {"a": {"b": None}})  # b节点改为None

        data = {"a": {"b": {"c": 1}}}
        self.assertEqual(file_utils.DictUtils._set_nested_value(data, "a/b/c", 2), True)  # 成功修改
        self.assertEqual(data, {"a": {"b": {"c": 2}}})  # c节点改为2

        data = {"a": {"b": {"c": 1}}}
        self.assertEqual(file_utils.DictUtils._set_nested_value(data, "a/b/d/c", 2), True)  # 成功修改
        self.assertEqual(data, {"a": {"b": {"c": 1, "d": {"c": 2}}}})

        data = {"a": {"b": {"c": 1}}}
        self.assertEqual(file_utils.DictUtils._set_nested_value(data, "a/b/c/d", 2), True)  # 成功修改
        self.assertEqual(data, {"a": {"b": {"c": {"d": 2}}}})

        # 清空嵌套值
        data = {"a": {"b": {"c": 1}}}
        self.assertEqual(file_utils.DictUtils._clear_nested_value(None, None), False)  # 无法修改
        # data["a"]["b"].clear()

    def test_set_nested_values(self):
        data = {"a": {"b": {"c": 1}}, "": 3}
        # print(file_utils.DictUtils.get_nested_value(data, "", "/", "/"))
        # file_utils.DictUtils.set_nested_values(data, None, "/", **{"/b/c": 2})
        # file_utils.DictUtils.set_nested_value(data, "a/b/c/d", "/", "/")
        file_utils.DictUtils.clear_nested_values(data, *(), "a", "b/c")
        print(data)

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
        hwnds = hwnd_utils.win32_get_hwnds_by_pid_and_class_wildcards(target_pid)
        print(hwnds)
        print(f"用时: {time.time() - start_time}")

    def test_resolve_addr(self):
        path = SwInfoFunc.resolve_sw_path("Weixin", "%dll_dir%/Weixin.dll")
        print(path)

    def test_custom_notebook_and_custom_btn(self):
        import tkinter as tk
        from tkinter import ttk
        from public_class.custom_widget import CustomNotebook, NotebookDirection, CustomCornerBtn, CustomLabelBtn

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
