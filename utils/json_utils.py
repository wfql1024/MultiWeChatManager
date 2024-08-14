import json
import os


def load_json_data(self):
    if os.path.exists(self.account_data_file):
        with open(self.account_data_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_json_data(self):
    with open(self.account_data_file, 'w', encoding='utf-8') as f:
        json.dump(self.account_data, f, ensure_ascii=False, indent=4)