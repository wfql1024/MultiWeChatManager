import os
import time
from datetime import datetime

import psutil

import functions.func_setting as func_get_path
import utils.json_utils as json_utils
from resources.config import Config
from utils import process_utils, string_utils


class AccountManager:
    def __init__(self, account_data_file):
        self.account_data_file = account_data_file
        self.account_data = json_utils.load_json_data(self.account_data_file)

    def get_account_list(self):
        def get_account_by_pid(process_id):
            try:
                # 获取指定进程的内存映射文件路径
                for f in psutil.Process(process_id).memory_maps():
                    # 将路径中的反斜杠替换为正斜杠
                    normalized_path = f.path.replace('\\', '/')
                    # 检查路径是否以 data_path 开头
                    if normalized_path.startswith(data_path):
                        print(
                            f"┌———匹配到进程{process_id}使用的符合的文件，待对比，已用时：{time.time() - start_time:.4f}秒")
                        print(f"提取中：{f.path}")
                        path_parts = f.path.split(os.path.sep)
                        try:
                            wxid_index = path_parts.index(os.path.basename(data_path)) + 1
                            wxid = path_parts[wxid_index]
                            wechat_processes.append((wxid, process_id))
                            logged_in_wxids.add(wxid)
                            print(f"└———提取到进程{process_id}对应账号{wxid}，已用时：{time.time() - start_time:.4f}秒")
                            return logged_in_wxids
                        except ValueError:
                            pass
            except psutil.AccessDenied:
                print(f"无法访问进程ID为 {process_id} 的内存映射文件，权限不足。")
            except psutil.NoSuchProcess:
                print(f"进程ID为 {process_id} 的进程不存在或已退出。")
            except Exception as e:
                print(f"发生意外错误: {e}")

        start_time = time.time()
        data_path = func_get_path.get_wechat_data_path()
        if not data_path:
            return None, None, None

        wechat_processes = []
        logged_in_wxids = set()

        pids = process_utils.get_process_ids_by_name("WeChat.exe")
        print(f"读取到微信所有进程，用时：{time.time() - start_time:.4f} 秒")
        # if len(pids) != 0:
        #     pool = ThreadPoolExecutor(max_workers=len(pids) + 1)
        #     pool.map(get_files_by_pid_thread, pids)
        if len(pids) != 0:
            for pid in pids:
                get_account_by_pid(pid)
        print(f"完成判断进程对应账号，用时：{time.time() - start_time:.4f} 秒")

        # 获取文件夹并分类
        excluded_folders = {'All Users', 'Applet', 'Plugins', 'WMPF'}
        folders = set(
            folder for folder in os.listdir(data_path)
            if os.path.isdir(os.path.join(data_path, folder))
        ) - excluded_folders
        logged_in = list(logged_in_wxids & folders)
        not_logged_in = list(folders - logged_in_wxids)

        print("logged_in", logged_in)
        print("not_logged_in", not_logged_in)
        print(f"完成账号分类，用时：{time.time() - start_time:.4f} 秒")

        # 更新数据
        self.account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
        pid_dict = dict(wechat_processes)
        for acc in logged_in + not_logged_in:
            if acc not in self.account_data:
                self.account_data[acc] = {"note": ""}
            self.account_data[acc]["pid"] = pid_dict.get(acc)

        json_utils.save_json_data(self.account_data_file, self.account_data)
        print(f"完成记录账号对应pid，用时：{time.time() - start_time:.4f} 秒")

        return logged_in, not_logged_in, wechat_processes

    @staticmethod
    def get_config_status(account):
        data_path = func_get_path.get_wechat_data_path()
        if not data_path:
            return "无法获取配置路径"

        config_path = os.path.join(data_path, "All Users", "config", f"{account}.data")
        if os.path.exists(config_path):
            mod_time = os.path.getmtime(config_path)
            date = datetime.fromtimestamp(mod_time)
            return f"{date.month}-{date.day} {date.hour:02}:{date.minute:02}"
        else:
            return "无配置"

    def update_note(self, account, note):
        self.account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
        if account not in self.account_data:
            self.account_data[account] = {}
        self.account_data[account]["note"] = note
        json_utils.save_json_data(self.account_data_file, self.account_data)

    def get_account_display_name(self, account):
        note = self.account_data.get(account, {}).get("note", None)
        nickname = self.account_data.get(account, {}).get("nickname", None)
        alias = self.account_data.get(account, {}).get("alias", None)
        if note:
            display_name = f"{note}"
        elif nickname:
            display_name = f"{nickname}"
        elif alias:
            display_name = f"{alias}"
        else:
            display_name = f"{account}"

        return string_utils.balanced_wrap_text(display_name, 10)

    def get_account_note(self, account):
        return self.account_data.get(account, {}).get("note", "")

    def get_account_nickname(self, account):
        return self.account_data.get(account, {}).get("nickname", "")


if __name__ == '__main__':
    pass
    # account_manager = AccountManager("./account_data.json")
    # print(account_manager.account_data_file)
    # json_utils.save_json_data(account_manager)
    # print(account_manager.account_data)
    # print(account_manager.get_account_list())
