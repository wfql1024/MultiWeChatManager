import os
import sqlite3

from functions import func_setting, func_file, subfunc_file
from resources.config import Config
from utils import wechat_decrypt_utils, image_utils


def fetch_acc_detail_by_pid(pid, account, before, after):
    """
    根据账号及对应的pid去获取账号详细信息
    :param pid: 对应的微信进程id
    :param account: 账号
    :param before: 开始前的操作：禁用按钮
    :param after: 结束后的操作：恢复按钮
    :return: 无
    """
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
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        sql_contact = f"SELECT UserName, Alias, NickName FROM 'Contact' WHERE UserName = '{folder}';"
        sql_contact_head_img_url = f"SELECT UsrName, bigHeadImgUrl FROM 'ContactHeadImgUrl' WHERE UsrName = '{folder}';"
        try:
            cursor.execute(sql_contact)
            contact_results = cursor.fetchall()
            user_name, alias, nickname = contact_results[0]
            cursor.execute(sql_contact_head_img_url)
            avatar_results = cursor.fetchall()
            usr_name, url = avatar_results[0]
            # alias的存储比较特殊，如果用户没有重新改过微信名，那么表中alias为空，但是软件希望alias存储的是当前的
            # 因此，若alias是空的，则原始名就是当前名
            subfunc_file.update_acc_details_to_acc_json(user_name, alias=alias, nickname=nickname, avatar_url=url)
            if alias == "":
                subfunc_file.update_acc_details_to_acc_json(user_name, alias=user_name)

            save_path = os.path.join(Config.PROJ_USER_PATH, f"{usr_name}", f"{usr_name}.jpg").replace('\\', '/')

            if not os.path.exists(os.path.dirname(save_path)):
                os.makedirs(os.path.dirname(save_path))

            success = None
            # 若不是当前账号且本地无缓存，才会下载
            if usr_name != account:
                if not os.path.exists(save_path):
                    success = image_utils.download_image(url, save_path)
                else:
                    print("已有缓存，不需要下载")
                    success = True
            # 是当前账号，直接下载更新
            else:
                success = image_utils.download_image(url, save_path)

            if not success:
                print("无法下载图像")

        except Exception as e:
            print("sql executed have some error", e)

        conn.close()
        after()
