import ctypes
from unittest import TestCase

import psutil

from functions import func_setting, subfunc_file
from resources import Config
from utils import hwnd_utils, handle_utils, process_utils, file_utils


class Test(TestCase):
    def SetUp(self):
        self.hwnd = hwnd_utils.get_a_hwnd_by_title("微信（测试版）")
        print(self.hwnd)

    def test_get_wnd_details_from_hwnd(self):
        details = hwnd_utils.get_hwnd_details_of_(10100452)
        print(details['class'])

    def test_get_sw_data_dir(self):
        print(func_setting.get_sw_data_dir(sw="Weixin"))

    def test_wait_for_wnd_open(self):
        hwnd_utils.wait_open_to_get_hwnd("Qt51514QWindowIcon")

    def test_close_sw_mutex_by_handle(self):
        redundant_wnd_list, login_wnd_class, executable_name, cfg_handles = (
            subfunc_file.get_details_from_remote_setting_json(
                "Weixin", redundant_wnd_class=None, login_wnd_class=None, executable=None, cfg_handle_regex_list=None))
        handle_utils.close_sw_mutex_by_handle(
            Config.HANDLE_EXE_PATH, executable_name, cfg_handles)

    def test_get_all_open_files(self):
        pids = process_utils.get_process_ids_by_name("Weixin")
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
        pids = process_utils.get_process_ids_by_name("WeChat.exe")
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
        test_hwnd = hwnd_utils.get_hwnd_list_by_pid_and_class(pid, target_class)
        hwnd_utils.hide_all_by_wnd_classes([target_class])
        print("Found HWNDs:", test_hwnd)
