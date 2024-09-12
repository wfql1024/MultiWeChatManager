from resources.config import Config
from utils import wechat_decrypt_utils


def decrypt_acc_and_copy_by_pid(pid, account):
    print("pid:", pid)
    # 获取pid对应账号的wechat key
    str_key = wechat_decrypt_utils.get_acc_key_by_pid(pid, account)
    # mylog.info(str_key)
    str_key_res = ' '.join([str_key[i:i + 2] for i in range(0, len(str_key), 2)])
    usr_dir = Config.PROJ_USER_PATH
    file_mm = usr_dir + rf"\{account}\{account}_MicroMsg.db"
    print("pwd: file", file_mm)
    print("str key:", str_key)
    print("str key res:", str_key_res)

    try:
        wechat_decrypt_utils.decrypt_db_file_by_pwd(file_mm, str_key_res)
    except Exception as e:
        print("decrypt has error:", e)


# if __name__ == '__main__':
#     decrypt_and_copy(20544, 'wxid_t2dchu5zw9y022')
