from unittest import TestCase

import psutil

from functions import func_setting, subfunc_file
from resources import Config
from utils import hwnd_utils, handle_utils, process_utils


class Test(TestCase):
    def SetUp(self):
        self.hwnd = hwnd_utils.get_window_handle("微信（测试版）")
        print(self.hwnd)
    def test_get_wnd_details_from_hwnd(self):
        details = hwnd_utils.get_wnd_details_from_hwnd(10100452)
        print(details['class'])
    def test_get_sw_data_dir(self):
        print(func_setting.get_sw_data_dir(sw="Weixin"))
    def test_wait_for_wnd_open(self):
        hwnd_utils.wait_for_wnd_open("Qt51514QWindowIcon")
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