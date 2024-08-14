import os
from datetime import datetime

import functions.func_path as func_get_path
import utils.json_utils as json_utils


def get_config_status(account):
    data_path = func_get_path.get_wechat_data_path()
    if not data_path:
        return "无法获取配置路径"

    config_path = os.path.join(data_path, "All Users", "config", f"{account}.data")
    if os.path.exists(config_path):
        mod_time = os.path.getmtime(config_path)
        dt = datetime.fromtimestamp(mod_time)
        return dt.strftime("%m-%d %H:%M:%S 的配置")
    else:
        return "无配置"


def is_account_logged_in(account_path):
    # TODO:准备修改
    msg_folder = os.path.join(account_path, 'Msg')
    if not os.path.exists(msg_folder):
        return False

    shm_count = 0
    wal_count = 0

    for file in os.listdir(msg_folder):
        if file.endswith('.db-shm'):
            shm_count += 1
        elif file.endswith('.db-wal'):
            wal_count += 1

        if shm_count >= 5 and wal_count >= 5:
            return True

    return False


class AccountManager:
    def __init__(self, account_data_file):
        self.account_data_file = account_data_file
        self.account_data = json_utils.load_json_data(self)

    def get_account_list(self):
        data_path = func_get_path.get_wechat_data_path()
        if not data_path:
            return None, None

        logged_in = []
        not_logged_in = []

        excluded_folders = {'All Users', 'Applet', 'Plugins', 'WMPF'}

        for folder in os.listdir(data_path):
            folder_path = os.path.join(data_path, folder)
            if os.path.isdir(folder_path) and folder not in excluded_folders:
                if is_account_logged_in(folder_path):
                    logged_in.append(folder)
                else:
                    not_logged_in.append(folder)

        for account in logged_in + not_logged_in:
            if account not in self.account_data:
                self.account_data[account] = {"note": ""}
        return logged_in, not_logged_in

    def update_account_note(self, account, note):
        # TODO:需要添加属性
        if account not in self.account_data:
            self.account_data[account] = {}
        self.account_data[account]["note"] = note
        json_utils.save_json_data(self)

    def get_account_display_name(self, account):
        note = self.get_account_note(account)
        if note:
            return f"{account}\n{note}"
        return f"{account}\n"

    def get_account_note(self, account):
        return self.account_data.get(account, {}).get("note", "")
