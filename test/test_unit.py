from unittest import TestCase

from utils import hwnd_utils

class Test(TestCase):
    def SetUp(self):
        self.hwnd = hwnd_utils.get_window_handle("微信（测试版）")
        print(self.hwnd)
    def test_get_wnd_details_from_hwnd(self):
        details = hwnd_utils.get_wnd_details_from_hwnd(8784736)
        print(details['class'])