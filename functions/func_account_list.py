import json
import os
from datetime import datetime

import functions.func_get_path as func_get_path


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


class AccountManager:
    def __init__(self, account_data_file):
        self.account_data_file = account_data_file
        self.account_data = self.load_account_data()

    def load_account_data(self):
        if os.path.exists(self.account_data_file):
            with open(self.account_data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_account_data(self):
        with open(self.account_data_file, 'w', encoding='utf-8') as f:
            json.dump(self.account_data, f, ensure_ascii=False, indent=4)

    def get_account_list(self):
        data_path = func_get_path.get_wechat_data_path()
        if not data_path:
            return None, None

        logged_in, not_logged_in = self.get_wechat_accounts(data_path)

        for account in logged_in + not_logged_in:
            if account not in self.account_data:
                self.account_data[account] = {"note": ""}
        return logged_in, not_logged_in

    def update_account_note(self, account, note):
        if account not in self.account_data:
            self.account_data[account] = {}
        self.account_data[account]["note"] = note
        self.save_account_data()

    def get_account_display_name(self, account):
        note = self.account_data.get(account, {}).get("note", "")
        if note:
            return f"{account} ({note})"
        return account

    def get_account_note(self, account):
        return self.account_data.get(account, {}).get("note", "")

    def is_account_logged_in(self, account_path):
        msg_folder = os.path.join(account_path, 'Msg')
        print(f"检查 {msg_folder} 中")
        if not os.path.exists(msg_folder):
            return False

        shm_count = 0
        wal_count = 0

        for file in os.listdir(msg_folder):
            if file.endswith('.db-shm'):
                shm_count += 1
                print(f"有 {shm_count} 个 shm")
            elif file.endswith('.db-wal'):
                wal_count += 1

            if shm_count >= 5 and wal_count >= 5:
                print("CheckLogined：已经符合了")
                return True

        return False

    def get_wechat_accounts(self, data_path):
        logged_in = []
        not_logged_in = []

        excluded_folders = {'All Users', 'Applet', 'Plugins', 'WMPF'}

        for folder in os.listdir(data_path):
            folder_path = os.path.join(data_path, folder)
            if os.path.isdir(folder_path) and folder not in excluded_folders:
                if self.is_account_logged_in(folder_path):
                    logged_in.append(folder)
                else:
                    not_logged_in.append(folder)

        return logged_in, not_logged_in
