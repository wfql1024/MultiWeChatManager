import os
import sqlite3

import requests

from functions import func_setting
from resources.config import Config
from utils import json_utils, wechat_decrypt_utils


def fetch_acc_detail_by_pid(pid, account, before, after):
    before()
    print("开始解密...")
    wechat_decrypt_utils.decrypt_acc_and_copy_by_pid(pid, account)
    print("连接数据库...")
    user_directory = Config.PROJ_USER_PATH
    db_file = user_directory + rf"/{account}/edit_{account}_MicroMsg.db"

    data_path = func_setting.get_wechat_data_path()
    excluded_folders = {'All Users', 'Applet', 'Plugins', 'WMPF'}
    folders = set(
        folder for folder in os.listdir(data_path)
        if os.path.isdir(os.path.join(data_path, folder))
    ) - excluded_folders
    for folder in folders:
        account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        sql_contact = f"SELECT UserName, Alias, NickName FROM 'Contact' WHERE UserName = '{folder}';"
        sql_contact_head_img_url = f"SELECT UsrName, bigHeadImgUrl FROM 'ContactHeadImgUrl' WHERE UsrName = '{folder}';"
        try:
            cursor.execute(sql_contact)
            contact_results = cursor.fetchall()
            user_name, alias, nickname = contact_results[0]
            if alias == "":
                account_data[user_name]["alias"] = user_name
            else:
                account_data[user_name]["alias"] = alias
            account_data[user_name]["nickname"] = nickname

            cursor.execute(sql_contact_head_img_url)
            avatar_results = cursor.fetchall()
            usr_name, url = avatar_results[0]
            account_data[usr_name]["avatar_url"] = url
            save_path = os.path.join(Config.PROJ_USER_PATH, f"{usr_name}", f"{usr_name}.jpg").replace('\\', '/')
            if not os.path.exists(os.path.dirname(save_path)):
                os.makedirs(os.path.dirname(save_path))

            def download_image(img_url, path):
                try:
                    response = requests.get(img_url.rstrip(r'/0') + r'/132', stream=True)
                    response.raise_for_status()  # 确保请求成功

                    with open(path, 'wb') as file:
                        for chunk in response.iter_content(chunk_size=8192):
                            file.write(chunk)

                    print(f"图像已成功保存到 {path}")
                    return True
                except requests.RequestException as re:
                    print(f"下载图像时出错: {re}")
                    return False

            success = None

            if usr_name != account:
                if not os.path.exists(save_path):
                    success = download_image(url, save_path)
            else:
                success = download_image(url, save_path)

            if success:
                # 如果需要，这里可以添加额外的处理逻辑
                pass
            else:
                # 处理下载失败的情况
                print("无法下载图像，可能是不需要下载吧")
        except Exception as e:
            print("sql executed have some error", e)

        json_utils.save_json_data(Config.ACC_DATA_JSON_PATH, account_data)
        conn.close()
        after()
