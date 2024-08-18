import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from queue import Queue

import psutil

import functions.func_path as func_get_path
import utils.json_utils as json_utils
from utils import process_utils
from resources.config import Config


def get_config_status(account):
    data_path = func_get_path.get_wechat_data_path()
    if not data_path:
        return "无法获取配置路径"

    config_path = os.path.join(data_path, "All Users", "config", f"{account}.data")
    if os.path.exists(config_path):
        mod_time = os.path.getmtime(config_path)
        dt = datetime.fromtimestamp(mod_time)
        return dt.strftime("%m-%d %H:%M")
    else:
        return "无配置"


def update_account_detail_except_note(account_data, account, avatar_url, alias, nickname):
    print("正在保存数据", avatar_url, alias, nickname)
    if account not in account_data:
        account_data[account] = {}
    account_data[account]["avatar_url"] = avatar_url
    account_data[account]["alias"] = alias
    account_data[account]["nickname"] = nickname


class AccountManager:
    def __init__(self, account_data_file):
        self.account_data_file = account_data_file
        self.account_data = json_utils.load_json_data(self.account_data_file)

    def get_account_list(self):
        def get_files_by_pid_thread(process_id):
            try:
                db_paths = [f.path for f in psutil.Process(process_id).memory_maps() if
                            f.path.replace('\\', '/').startswith(data_path)]
                print("子进程：获取单个进程所有文件用时：", time.time() - start_time)
                if db_paths:  # 如果存在匹配的文件路径
                    db_file = db_paths[0]  # 取第一个匹配的文件路径
                    print(db_file)
                    path_parts = db_file.split(os.path.sep)
                    try:
                        wxid_index = path_parts.index(os.path.basename(data_path)) + 1
                        wxid = path_parts[wxid_index]
                        wechat_processes.append((wxid, process_id))
                        logged_in_wxids.add(wxid)
                        print("子进程：获取单个进程所需数据用时：", time.time() - start_time)
                        return logged_in_wxids
                    except ValueError:
                        pass
            except Exception as e:
                print(f"处理PID {process_id} 时发生错误: {e}")

        start_time = time.time()
        data_path = func_get_path.get_wechat_data_path()
        print(data_path)
        if not data_path:
            return None, None, None

        wechat_processes = []
        logged_in_wxids = set()

        pids = process_utils.get_process_ids_by_name("WeChat.exe")
        print(f"wechat_processes: {wechat_processes}")
        print(f"读取到微信所有进程，用时：{time.time() - start_time:.4f} 秒")
        if len(pids) != 0:
            pool = ThreadPoolExecutor(max_workers=len(pids) + 1)
            pool.map(get_files_by_pid_thread, pids)
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

    def update_note(self, account, note):
        self.account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
        if account not in self.account_data:
            self.account_data[account] = {}
        self.account_data[account]["note"] = note
        json_utils.save_json_data(self.account_data_file, self.account_data)

    def get_account_display_name(self, account):
        note = self.get_account_note(account)
        nickname = self.get_account_nickname(account)
        if note:
            return f"{account}\n{note}"
        return f"{account}\n"

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
