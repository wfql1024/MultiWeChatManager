import json
import os

from utils.logger_utils import mylogger as logger





def load_json_data(account_data_file):
    try:
        if os.path.exists(account_data_file):
            # print("地址没错")
            with open(account_data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(e)
        return {}


def save_json_data(account_data_file, account_data):
    try:
        with open(account_data_file, 'w', encoding='utf-8') as f:
            json_string = json.dumps(account_data, ensure_ascii=False, indent=4)
            f.write(json_string)
    except Exception as e:
        logger.error(e)
