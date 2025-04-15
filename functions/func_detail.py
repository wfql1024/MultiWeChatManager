import os
import sqlite3
from tkinter import messagebox

import decrypt
from functions import func_setting, subfunc_file
from resources.config import Config
from utils import image_utils
from utils.logger_utils import mylogger as logger
from utils.logger_utils import myprinter as printer


def fetch_acc_detail_by_pid(sw, pid, account, after):
    """
    根据账号及对应的pid去获取账号详细信息
    :param sw: 选择的软件标签
    :param pid: 对应的微信进程id
    :param account: 账号
    :param after: 结束后的操作：恢复按钮
    :return: 无
    """
    try:
        decrypt_impl = _get_decrypt_utils(sw)
    except Exception as e:
        logger.error(e)
        messagebox.showerror("错误", f"{e}")
        after()
        return

    print(f"pid：{pid}，开始找key...")
    success, result = decrypt_db_and_return(sw, pid, account)
    if success is not True:
        print("解密出错...")
        messagebox.showerror("错误", result)
        after()
        return

    decrypted_mm_db_path = result
    print(f"解密成功，数据库临时存在：{decrypted_mm_db_path}")

    data_path = func_setting.get_sw_data_dir(sw)
    excluded_folders = {'All Users', 'Applet', 'Plugins', 'WMPF'}
    folders = set(
        folder for folder in os.listdir(data_path)
        if os.path.isdir(os.path.join(data_path, folder))
    ) - excluded_folders

    printer.vital("数据库查询...")
    if os.path.isfile(decrypted_mm_db_path):
        conn = sqlite3.connect(decrypted_mm_db_path)
    else:
        logger.error("数据库文件不存在")
        messagebox.showerror("错误", f"数据库文件不存在")
        return

    try:
        cursor = conn.cursor()
        for acc in folders:
            success, result = decrypt_impl.get_acc_id_and_alias_from_db(cursor, acc)
            if success is not True:
                logger.error(f"账号{acc}查询失败")
                continue
            if isinstance(result, list) and len(result) > 0:
                user_name, alias = result[0]
                subfunc_file.update_sw_acc_data(sw, acc, alias=alias or user_name)
            else:
                logger.warning(f"账号{acc}未能获取到微信号")

            success, result = decrypt_impl.get_acc_nickname_from_db(cursor, acc)
            if success is not True:
                logger.error(f"账号{acc}查询失败")
                continue
            if isinstance(result, list) and len(result) > 0:
                user_name, nickname = result[0]
                subfunc_file.update_sw_acc_data(sw, acc, nickname=nickname)
            else:
                logger.warning(f"账号{acc}未能获取到昵称")

            success, result = decrypt_impl.get_acc_avatar_from_db(cursor, acc)
            if success is not True:
                logger.error(f"账号{acc}查询失败")
                continue
            if isinstance(result, list) and len(result) > 0:
                usr_name, url = result[0]
                origin_url, = subfunc_file.get_sw_acc_data(sw, acc, avatar_url=None)
                save_path = os.path.join(Config.PROJ_USER_PATH, sw, f"{acc}", f"{acc}.jpg").replace('\\', '/')
                if not os.path.exists(os.path.dirname(save_path)):
                    os.makedirs(os.path.dirname(save_path))

                # 下载头像逻辑：对于非选定的账号，若图像文件不存在或者url更新了，将会下载。对选定账号则一定下载。
                if usr_name != account:
                    if not os.path.exists(save_path) or origin_url != url:
                        success = image_utils.download_image(url, save_path)
                    else:
                        success = "无需下载"
                        logger.info(f"{acc}无需下载")
                else:
                    success = image_utils.download_image(url, save_path)
                if success is True:
                    subfunc_file.update_sw_acc_data(sw, acc, avatar_url=url)
            else:
                logger.warning(f"账号{acc}未能获取头像url")
                continue
    finally:
        conn.close()
        # if os.path.isfile(decrypted_mm_db_path):
        #     os.remove(decrypted_mm_db_path)
        after()


def _get_decrypt_utils(platform):
    module_name = None
    class_name = None
    try:
        # # 动态加载模块，模块名称格式为 {platform}_decrypt_utils
        # # module_name = f"decrypt.impl.{platform}_decrypt_impl"
        # module_name = f"decrypt"
        # module = importlib.import_module(module_name)
        # 从模块中获取工具类，例如 WeChatDecryptUtils
        class_name = f"{platform}DecryptImpl"
        decrypt_class = getattr(decrypt, class_name)
        return decrypt_class()
    except ModuleNotFoundError:
        raise ValueError(f"未找到模块: {module_name}")
    except AttributeError:
        raise ValueError(f"模块 {module_name} 中未找到类: {class_name}")


def decrypt_db_and_return(sw, pid, account):
    # 加载对应平台的解密工具
    try:
        decrypt_impl = _get_decrypt_utils(sw)
    except ValueError as e:
        logger.error(e)
        return False, f"{sw}平台不支持, {e}"

    # 第一阶段：获取密钥
    success, result = decrypt_impl.get_acc_str_key_by_pid(pid)
    if success is not True:
        return False, result
    str_key = result
    print(f"成功获取key:{str_key}")

    # 第二阶段：将数据库拷贝到项目
    success, result = decrypt_impl.copy_origin_db_to_proj(pid, account)
    if success is not True:
        return False, result
    db_path = result
    print(f"成功将数据库拷贝到项目：{db_path}")

    # 第三阶段：解密
    try:
        success, result = decrypt_impl.decrypt_db_file_by_str_key(pid, db_path, str_key)
    except Exception as e:
        logger.error(e)
        return False, e

    if success is True:
        return True, result


def unlink_hwnd_of_account(sw, account):
    """
    解除账号与hwnd的绑定
    :param sw: 软件标签
    :param account: 账号列表
    :return:
    """
    subfunc_file.update_sw_acc_data(sw, account, main_hwnd=None)
