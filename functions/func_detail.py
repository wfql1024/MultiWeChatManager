import os
import sqlite3
from tkinter import messagebox

from functions import func_setting, subfunc_file
from resources.config import Config
from utils import wechat_decrypt_utils, image_utils
from utils.logger_utils import mylogger as logger


def fetch_acc_detail_by_pid(pid, account, after):
    """
    根据账号及对应的pid去获取账号详细信息
    :param pid: 对应的微信进程id
    :param account: 账号
    :param after: 结束后的操作：恢复按钮
    :return: 无
    """
    print(f"pid：{pid}，开始找key...")
    error = wechat_decrypt_utils.decrypt_acc_and_copy_by_pid(pid, account)
    if error:
        print("解密出错...")
        messagebox.showerror("错误", error)
        after()
        return error

    print("连接数据库...")
    user_directory = Config.PROJ_USER_PATH
    db_file = user_directory + rf"/{account}/edit_{account}_MicroMsg.db"

    data_path = func_setting.get_wechat_data_dir()
    excluded_folders = {'All Users', 'Applet', 'Plugins', 'WMPF'}
    folders = set(
        folder for folder in os.listdir(data_path)
        if os.path.isdir(os.path.join(data_path, folder))
    ) - excluded_folders

    conn = sqlite3.connect(db_file)
    try:
        cursor = conn.cursor()
        for folder in folders:
            sql_contact = f"SELECT UserName, Alias, NickName FROM 'Contact' WHERE UserName = '{folder}';"
            sql_contact_head_img_url = \
                f"SELECT UsrName, bigHeadImgUrl FROM 'ContactHeadImgUrl' WHERE UsrName = '{folder}';"
            try:
                cursor.execute(sql_contact)
                contact_results = cursor.fetchall()
                if len(contact_results) > 0:
                    user_name, alias, nickname = contact_results[0]
                    # 处理alias为空的情况
                    subfunc_file.update_acc_details_to_acc_json(user_name, alias=alias or user_name, nickname=nickname)
                else:
                    logger.error("该账号未能获取到昵称、微信号")
                    return

                cursor.execute(sql_contact_head_img_url)
                avatar_results = cursor.fetchall()
                if len(avatar_results) > 0:
                    usr_name, url = avatar_results[0]
                    subfunc_file.update_acc_details_to_acc_json(usr_name, avatar_url=url)
                    save_path = os.path.join(Config.PROJ_USER_PATH, f"{usr_name}", f"{usr_name}.jpg").replace('\\', '/')
                    if not os.path.exists(os.path.dirname(save_path)):
                        os.makedirs(os.path.dirname(save_path))
                    # 下载头像逻辑
                    if usr_name != account:
                        if not os.path.exists(save_path):
                            success = image_utils.download_image(url, save_path)
                        else:
                            success = "无需下载"
                            logger.info("该账号无需下载")
                    else:
                        success = image_utils.download_image(url, save_path)
                    if not success:
                        logger.error("无法下载图像")
                else:
                    logger.error("该账号未能获取头像url")
                    return
            except Exception as e:
                print("sql executed have some error", e)
                messagebox.showerror("错误", f"数据库执行出错:{e}")
                return "数据库执行出错"
    finally:
        conn.close()
        after()
