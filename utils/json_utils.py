import json
import os


def load_json_data(account_data_file):
    if os.path.exists(account_data_file):
        # print("地址没错")
        with open(account_data_file, 'r', encoding='utf-8') as f:
            # print(f)
            print(f"┌————————————————读取json—————————————————")
            return json.load(f)
    return {}


def save_json_data(account_data_file, account_data):
    with open(account_data_file, 'w', encoding='utf-8') as f:
        json.dump(account_data, f, ensure_ascii=False, indent=4)
        print(f"└————————————————写入json—————————————————")
