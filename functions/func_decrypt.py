import os

import utils
from utils.wechat_decrypt_utils import get_current_wechat_key, myDecry
from utils import process_utils
from resources.config import Config


def decrypt_and_copy(pid, account):
    print("pid:", pid)
    # 获取pid对应账号的wechat key
    str_key = get_current_wechat_key(pid, account)
    # mylog.info(str_key)
    str_key_res = ' '.join([str_key[i:i + 2] for i in range(0, len(str_key), 2)])
    usrDir = Config.PROJECT_USER_PATH
    file_microMsg = usrDir + rf"\{account}\{account}_MicroMsg.db"
    print("pwd: file", file_microMsg)
    print("str key:", str_key)
    print("str key res:", str_key_res)

    try:
        myDecry(file_microMsg, str_key_res)
    except Exception as e:
        print("decrypt has error:", e)


if __name__ == '__main__':
    decrypt_and_copy(20544, 'wxid_t2dchu5zw9y022')
