import os
import shutil
import sqlite3
import subprocess
import sys
import threading
from tkinter import messagebox

import psutil
import requests

import decrypt
from functions import subfunc_file
from functions.sw_func import SwInfoFunc
from public_class.enums import LocalCfg
from resources.config import Config
from utils import image_utils
from utils.logger_utils import mylogger as logger
from utils.logger_utils import myprinter as printer


class DetailWndFunc:
    @staticmethod
    def _get_decrypt_utils(platform):
        module_name = "decrypt"
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
            raise ValueError(f"暂不支持! 模块 {module_name} 中未找到类: {class_name}")

    @staticmethod
    def _decrypt_db_and_return(sw, pid, account):
        # 加载对应平台的解密工具
        try:
            decrypt_impl = DetailWndFunc._get_decrypt_utils(sw)
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
            return success, result
        except Exception as e:
            logger.error(e)
            return False, e

    @staticmethod
    def _fetch_acc_detail_by_pid(sw, pid, account, after):
        """
        根据账号及对应的pid去获取账号详细信息
        :param sw: 选择的软件标签
        :param pid: 对应的微信进程id
        :param account: 账号
        :param after: 结束后的操作：恢复按钮
        :return: 无
        """
        try:
            decrypt_impl = DetailWndFunc._get_decrypt_utils(sw)
        except Exception as e:
            logger.error(e)
            messagebox.showerror("错误", f"{e}")
            after()
            return

        print(f"pid：{pid}，开始找key...")
        success, result = DetailWndFunc._decrypt_db_and_return(sw, pid, account)
        if success is not True:
            print("解密出错...")
            messagebox.showerror("错误", result)
            after()
            return

        decrypted_mm_db_path = result
        print(f"解密成功，数据库临时存在：{decrypted_mm_db_path}")

        data_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.DATA_DIR)
        excluded_folders, = subfunc_file.get_remote_cfg(
            sw, excluded_dir_list=None)
        excluded_folders = set(excluded_folders)
        acc_folders = set(
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
            for acc in acc_folders:
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

    @staticmethod
    def thread_to_fetch_acc_detail_by_pid(sw, pid, account, after):
        try:
            psutil.Process(pid)
        except psutil.NoSuchProcess:
            # 用户在此过程偷偷把账号退了...
            logger.warning(f"该进程已不存在: {pid}")
            subfunc_file.update_sw_acc_data(sw, account, pid=None)
            messagebox.showinfo("提示", "未检测到该账号登录")
            after()
            return
        # 线程启动获取详情
        threading.Thread(target=DetailWndFunc._fetch_acc_detail_by_pid,
                         args=(sw, pid, account, after)).start()


class UpdateLogWndFunc:
    @staticmethod
    def download_files(ver_dicts, download_dir, progress_callback, on_complete_callback, status):
        try:
            print("进入下载文件方法...")
            for ver_dict in ver_dicts:
                if status.get("stop"):  # 检查停止状态
                    print("下载被用户中断")
                    return False
                url = ver_dict.get("url", "")
                if not url:
                    print("URL为空，跳过此文件字典...")
                    continue
                try:
                    urls = [url]
                    for idx, url in enumerate(urls):
                        print(f"Downloading to {download_dir}")
                        with requests.get(url, stream=True, allow_redirects=True) as r:
                            r.raise_for_status()
                            total_length = int(r.headers.get('content-length', 0))
                            with open(download_dir, 'wb') as f:
                                downloaded = 0
                                for chunk in r.iter_content(chunk_size=8192):
                                    if status.get("stop"):  # 每次读取chunk都检查停止状态
                                        print("下载被用户中断")
                                        return False
                                    if chunk:
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                        progress_callback(idx, len(urls), downloaded, total_length)

                    print("所有文件下载成功。")
                    on_complete_callback()
                    return True
                except Exception as e:
                    print(f"从 {url} 下载失败, 错误: {e}")
            print("所有提供的URL下载失败。")
            return False
        except Exception as e:
            print(f"发生异常: {e}")
            raise e

    @staticmethod
    def close_and_update(tmp_path):
        if getattr(sys, 'frozen', False):
            answer = messagebox.askokcancel("提醒", "将关闭主程序进行更新操作，请确认")
            if answer:
                exe_path = sys.executable
                current_version = subfunc_file.get_app_current_version()
                install_dir = os.path.dirname(exe_path)

                update_exe_path = os.path.join(Config.PROJ_EXTERNAL_RES_PATH, 'Updater.exe')
                new_update_exe_path = os.path.join(os.path.dirname(tmp_path), 'Updater.exe')
                try:
                    shutil.copy(update_exe_path, new_update_exe_path)
                    print(f"成功将 {update_exe_path} 拷贝到 {new_update_exe_path}")
                except Exception as e:
                    print(f"拷贝文件时出错: {e}")
                subprocess.Popen([new_update_exe_path, current_version, install_dir, tmp_path],
                                 creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
        else:
            messagebox.showinfo("提醒", "请在打包环境中执行")
