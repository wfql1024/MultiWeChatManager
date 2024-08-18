import os
import sqlite3

from functions import func_path
from functions.func_decrypt import decrypt_and_copy
from resources.config import Config


def get_account_detail(pid, account):
    print("开始解密...")
    decrypt_and_copy(pid, account)
    print("连接数据库...")
    usrDir = Config.PROJECT_USER_PATH
    file_microMsg = usrDir + rf"\edit_{account}_MicroMsg.db"

    data_path = func_path.get_wechat_data_path()
    excluded_folders = {'All Users', 'Applet', 'Plugins', 'WMPF'}
    folders = set(
        folder for folder in os.listdir(data_path)
        if os.path.isdir(os.path.join(data_path, folder))
    ) - excluded_folders
    for account in folders:
        conn = sqlite3.connect(file_microMsg)
        cursor = conn.cursor()
        SQL_contact = f"SELECT UserName, Alias, NickName FROM 'Contact' WHERE UserName = '{account}';"
        SQL_contact_head_img_url = f"SELECT UsrName, bigHeadImgUrl FROM 'ContactHeadImgUrl' WHERE UsrName = '{account}';"
        try:
            cursor.execute(SQL_contact)
            results = cursor.fetchall()
            print(results)
            cursor.execute(SQL_contact_head_img_url)
            results = cursor.fetchall()
            print(results)
        except Exception as e:
            print("sql excute have some error", e)
        conn.close()


if __name__=='__main__':
    get_account_detail(35520, "wxid_t2dchu5zw9y022")
