import os
import shutil
import time
from resources import Config
from unittest import TestCase
from utils import handle_utils
import tkinter as tk
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