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
    success, result = wechat_decrypt_utils.decrypt_db_and_return(pid, account)
    if success is not True:
        print("解密出错...")
        messagebox.showerror("错误", result)
        after()
        return

    decrypted_mm_db_path = result

    data_path = func_setting.get_wechat_data_dir()
    excluded_folders = {'All Users', 'Applet', 'Plugins', 'WMPF'}
    folders = set(
        folder for folder in os.listdir(data_path)
        if os.path.isdir(os.path.join(data_path, folder))
    ) - excluded_folders

    print("连接数据库...")
    if os.path.isfile(decrypted_mm_db_path):
        conn = sqlite3.connect(decrypted_mm_db_path)
    else:
        logger.error("数据库文件不存在")
        messagebox.showerror("错误", f"数据库文件不存在")
        return
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
                    subfunc_file.update_acc_details_to_acc_json(user_name, alias=alias or user_name, nickname=nickname)
                else:
                    logger.warning(f"账号{folder}未能获取到昵称、微信号")

                cursor.execute(sql_contact_head_img_url)
                avatar_results = cursor.fetchall()
                if len(avatar_results) > 0:
                    usr_name, url = avatar_results[0]
                    origin_url, = subfunc_file.get_acc_details_from_acc_json(usr_name, avatar_url=None)
                    save_path = os.path.join(Config.PROJ_USER_PATH, f"{usr_name}", f"{usr_name}.jpg").replace('\\', '/')
                    if not os.path.exists(os.path.dirname(save_path)):
                        os.makedirs(os.path.dirname(save_path))

                    # 下载头像逻辑：对于非选定的账号，若图像文件不存在或者url更新了，将会下载。对选定账号则一定下载。
                    if usr_name != account:
                        if not os.path.exists(save_path) or origin_url != url:
                            success = image_utils.download_image(url, save_path)
                        else:
                            success = "无需下载"
                            logger.info(f"{folder}无需下载")
                    else:
                        success = image_utils.download_image(url, save_path)
                    if success is True:
                        subfunc_file.update_acc_details_to_acc_json(usr_name, avatar_url=url)
                else:
                    logger.warning(f"账号{folder}未能获取头像url")
                    continue
            except Exception as e:
                logger.error(e)
                messagebox.showerror("错误", f"数据库执行出错:{e}")
                return
    finally:
        conn.close()
        if os.path.isfile(decrypted_mm_db_path):
            os.remove(decrypted_mm_db_path)
        after()
