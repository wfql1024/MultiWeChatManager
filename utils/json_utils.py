import json
import os


def load_json_data(account_data_file):
    if os.path.exists(account_data_file):
        # print("地址没错")
        with open(account_data_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_json_data(account_data_file, account_data):
    with open(account_data_file, 'w', encoding='utf-8') as f:
        json_string = json.dumps(account_data, ensure_ascii=False, indent=4)
        f.write(json_string)
