import base64
import os
import subprocess
import sys
import time
from collections.abc import Iterable
from tkinter import messagebox

import psutil
from PIL import Image

from functions import subfunc_file, func_config
from public_class.enums import Keywords
from public_class.global_members import GlobalMembers
from resources import Constants
from resources.config import Config
from resources.strings import Strings
from utils import process_utils, image_utils, string_utils, hwnd_utils
from utils.logger_utils import mylogger as logger


def quit_selected_accounts(sw, accounts_selected):
    accounts_to_quit = []
    for acc in accounts_selected:
        pid, = subfunc_file.get_sw_acc_data(sw, acc, pid=None)
        display_name = get_acc_origin_display_name(sw, acc)
        cleaned_display_name = string_utils.clean_texts(display_name)
        accounts_to_quit.append(f"[{pid}: {cleaned_display_name}]")
    accounts_to_quit_str = "\n".join(accounts_to_quit)
    if messagebox.askokcancel("提示",
                              f"确认退登：\n{accounts_to_quit_str}？"):
        try:
            quited_accounts = quit_accounts(sw, accounts_selected)
            quited_accounts_str = "\n".join(quited_accounts)
            messagebox.showinfo("提示", f"已退登：\n{quited_accounts_str}")
        except Exception as e:
            logger.error(e)
        return True
    return False


def quit_accounts(sw, accounts):
    quited_accounts = []
    for account in accounts:
        try:
            pid, = subfunc_file.get_sw_acc_data(sw, account, pid=None)
            display_name = get_acc_origin_display_name(sw, account)
            cleaned_display_name = string_utils.clean_texts(display_name)
            executable_name, = subfunc_file.get_details_from_remote_setting_json(sw, executable=None)
            process = psutil.Process(pid)
            if process_utils.process_exists(pid) and process.name() == executable_name:
                startupinfo = None
                if sys.platform == 'win32':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                result = subprocess.run(
                    ['taskkill', '/T', '/F', '/PID', f'{pid}'],
                    startupinfo=startupinfo,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print(f"结束了 {pid} 的进程树")
                    quited_accounts.append(f"[{cleaned_display_name}: {pid}]")
                else:
                    print(f"无法结束 PID {pid} 的进程树，错误：{result.stderr.strip()}")
            else:
                print(f"进程 {pid} 已经不存在。")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return quited_accounts


def get_acc_avatar_from_files(account, sw):
    """
    从本地缓存或json文件中的url地址获取头像，失败则默认头像
    :param sw: 选择的软件标签
    :param account: 原始微信号
    :return: 头像文件 -> ImageFile
    """
    # 构建头像文件路径
    avatar_path = os.path.join(Config.PROJ_USER_PATH, sw, f"{account}", f"{account}.jpg")

    # 检查是否存在对应account的头像
    if os.path.exists(avatar_path):
        return Image.open(avatar_path)
    # 如果没有，从网络下载
    url, = subfunc_file.get_sw_acc_data(sw, account, avatar_url=None)
    if url is not None and url.endswith("/0"):
        image_utils.download_image(url, avatar_path)

    # 第二次检查是否存在对应account的头像
    if os.path.exists(avatar_path):
        return Image.open(avatar_path)
    # 如果没有，检查default.jpg
    default_path = os.path.join(Config.PROJ_USER_PATH, "default.jpg")
    if os.path.exists(default_path):
        return Image.open(default_path)

    # 如果default.jpg也不存在，则将从字符串转换出来
    try:
        base64_string = Strings.DEFAULT_AVATAR_BASE64
        image_data = base64.b64decode(base64_string)
        with open(default_path, "wb") as f:
            f.write(image_data)
        return Image.open(default_path)
    except FileNotFoundError as e:
        print("文件路径无效或无法创建文件:", e)
    except IOError as e:
        print("图像文件读取失败:", e)
    except Exception as e:
        print("所有方法都失败，创建空白头像:", e)
        return Image.new('RGB', Constants.AVT_SIZE, color='white')


def get_acc_origin_display_name(sw, account) -> str:
    """
    获取账号的展示名
    :param sw: 选择的软件标签
    :param account: 微信账号
    :return: 展示在界面的名字
    """
    # 依次查找 note, nickname, alias，找到第一个不为 None 的值
    display_name = str(account)  # 默认值为 account
    for key in ("note", "nickname", "alias"):
        value, = subfunc_file.get_sw_acc_data(sw, account, **{key: None})
        if value is not None:
            display_name = str(value)
            break

    return display_name


def get_acc_wrapped_display_name(sw, account) -> str:
    """
    获取账号的展示名
    :param sw: 选择的软件标签
    :param account: 微信账号
    :return: 展示在界面的折叠好的名字
    """
    return string_utils.balanced_wrap_text(
        get_acc_origin_display_name(sw, account),
        10
    )


def silent_get_avatar_url(sw, acc_list, data_dir):
    """
    悄悄获取账号的头像url
    :param sw: 选择的软件标签
    :param acc_list: 微信账号
    :param data_dir: 数据目录
    :return: 无
    """
    changed1 = subfunc_file.get_avatar_url_from_file(sw, acc_list, data_dir)
    changed2 = subfunc_file.get_avatar_url_from_other_sw(sw, acc_list)
    return changed1 or changed2


def silent_get_nickname(sw, acc_list, data_dir):
    """
    悄悄获取账号的头像url
    :param sw: 选择的软件标签
    :param acc_list: 微信账号
    :param data_dir: 数据目录
    :return: 无
    """
    changed1 = subfunc_file.get_nickname_from_file(sw, acc_list, data_dir)
    changed2 = subfunc_file.get_nickname_from_other_sw(sw, acc_list)
    return changed1 or changed2


def silent_get_and_config(sw):
    root_class = GlobalMembers.root_class
    acc_tab_ui = root_class.acc_tab_ui
    root = root_class.root
    data_dir = root_class.sw_classes[sw].data_dir
    # while True:
    #     print("静默处理...")
    #     time.sleep(1)

    # 悄悄执行检测昵称和头像
    need_to_notice = False

    # 1. 获取所有账号节点的url和昵称，将空的账号返回
    accounts_need_to_get_avatar = []
    accounts_need_to_get_nickname = []

    sw_data = subfunc_file.get_sw_acc_data(sw)
    # print(login, logout)
    for acc in sw_data:
        if acc == Keywords.PID_MUTEX:
            continue
        avatar_url, nickname = subfunc_file.get_sw_acc_data(sw, acc, avatar_url=None, nickname=None)
        if avatar_url is None:
            accounts_need_to_get_avatar.append(acc)
        if nickname is None:
            accounts_need_to_get_nickname.append(acc)
    # print(accounts_need_to_get_avatar, accounts_need_to_get_nickname)

    # 2. 对待获取url的账号遍历尝试获取
    if len(accounts_need_to_get_avatar) > 0:
        changed = silent_get_avatar_url(sw, accounts_need_to_get_avatar, data_dir)
        if changed is True:
            need_to_notice = True

    # 3. 对待获取昵称的账号尝试遍历获取
    if len(accounts_need_to_get_nickname) > 0:
        changed = silent_get_nickname(sw, accounts_need_to_get_nickname, data_dir)
        if changed is True:
            need_to_notice = True

    # 4. 偷偷创建配置文件
    curr_config_acc = subfunc_file.get_curr_wx_id_from_config_file(sw, data_dir)
    if curr_config_acc is not None:
        if func_config.get_sw_acc_login_cfg(sw, curr_config_acc, data_dir) == "无配置":
            changed, _ = func_config.operate_config('add', sw, curr_config_acc)
            if changed is True:
                need_to_notice = True

    # 5. 通知
    if need_to_notice is True:
        messagebox.showinfo("提醒", "已自动化获取或配置！即将刷新！")
        root.after(0, acc_tab_ui.refresh_frame, sw)


def get_sw_acc_list(_root, root_class, sw):
    """
    获取账号及其登录情况
    :param _root: 主窗口
    :param root_class: 主窗口类
    :param sw: 平台
    :return: Union[Tuple[True, Tuple[账号字典，进程字典，有无互斥体]], Tuple[False, 错误信息]]
    """
    sw_class = root_class.sw_classes[sw]
    # print(sw_class)
    # print(sw_class.__dict__)

    data_dir = sw_class.data_dir
    # print(data_dir)
    if os.path.isdir(data_dir) is False:
        return False, "数据路径不存在"

    def update_acc_list_by_pid(process_id: int):
        """
        为存在的微信进程匹配出对应的账号，并更新[已登录账号]和[(已登录进程,账号)]
        :param process_id: 微信进程id
        :return: 无
        """
        # print(data_path)
        try:
            # print(pid, "的孩子：", psutil.Process(process_id).children())
            # 获取指定进程的内存映射文件路径
            for f in psutil.Process(process_id).memory_maps():
                # print(process_id, f)
                # 将路径中的反斜杠替换为正斜杠
                normalized_path = f.path.replace('\\', '/')
                # print(normalized_path)
                # 检查路径是否以 data_path 开头
                if normalized_path.startswith(data_dir):
                    # print(
                    #     f"┌———匹配到进程{process_id}使用的符合的文件，待比对，已用时：{time.time() - start_time:.4f}秒")
                    # print(f"提取中：{f.path}")
                    path_parts = f.path.split(os.path.sep)
                    try:
                        wx_id_index = path_parts.index(os.path.basename(data_dir)) + 1
                        wx_id = path_parts[wx_id_index]
                        if wx_id not in excluded_dir_list:
                            proc_dict.append((wx_id, process_id))
                            logged_in_ids.add(wx_id)
                            # print(f"进程{process_id}对应账号{wx_id}，已用时：{time.time() - start_time:.4f}秒")
                            return
                    except Exception as e:
                        logger.error(e)
            for f in psutil.Process(process_id).open_files():
                # print(process_id, f)
                # 将路径中的反斜杠替换为正斜杠
                normalized_path = f.path.replace('\\', '/')
                # print(normalized_path)
                # 检查路径是否以 data_path 开头
                if normalized_path.startswith(data_dir):
                    # print(
                    #     f"┌———匹配到进程{process_id}使用的符合的文件，待比对，已用时：{time.time() - start_time:.4f}秒")
                    # print(f"提取中：{f.path}")
                    path_parts = f.path.split(os.path.sep)
                    try:
                        wx_id_index = path_parts.index(os.path.basename(data_dir)) + 1
                        wx_id = path_parts[wx_id_index]
                        if wx_id not in ["all_users"]:
                            proc_dict.append((wx_id, process_id))
                            logged_in_ids.add(wx_id)
                            # print(f"进程{process_id}对应账号{wx_id}，已用时：{time.time() - start_time:.4f}秒")
                            return
                    except Exception as e:
                        logger.error(e)
        except psutil.AccessDenied:
            logger.error(f"无法访问进程ID为 {process_id} 的内存映射文件，权限不足。")
        except psutil.NoSuchProcess:
            logger.error(f"进程ID为 {process_id} 的进程不存在或已退出。")
        except Exception as e:
            logger.error(f"发生意外错误: {e}")

    start_time = time.time()

    proc_dict = []
    logged_in_ids = set()

    exe, excluded_dir_list = subfunc_file.get_details_from_remote_setting_json(
        sw, executable=None, excluded_dir_list=None)
    if exe is None or excluded_dir_list is None:
        messagebox.showerror("错误", f"{sw}平台未适配")
        return False, "该平台未适配"
    pids = process_utils.get_process_ids_by_name(exe)
    pids = process_utils.remove_child_pids(pids)
    # print(f"读取到{sw}所有进程，用时：{time.time() - start_time:.4f} 秒")
    if isinstance(pids, Iterable):
        for pid in pids:
            update_acc_list_by_pid(pid)
    # print(f"完成判断进程对应账号，用时：{time.time() - start_time:.4f} 秒")

    # print(proc_dict)
    # print(logged_in_ids)

    # 获取文件夹并分类
    folders = set(
        item for item in os.listdir(data_dir)
        if os.path.isdir(os.path.join(data_dir, item))
    ) - set(excluded_dir_list)
    login = list(logged_in_ids & folders)
    logout = list(folders - logged_in_ids)

    # print(f"{sw}已登录：{login}")
    # print(f"{sw}未登录：{logout}")
    # print(f"完成账号分类，用时：{time.time() - start_time:.4f} 秒")

    # 更新数据
    has_mutex = True
    pid_dict = dict(proc_dict)
    multiple_status = sw_class.multiple_state
    if multiple_status == "已开启":
        # print(f"由于是全局多开模式，直接所有has_mutex都为false")
        for acc in login + logout:
            subfunc_file.update_sw_acc_data(sw, acc, pid=pid_dict.get(acc, None), has_mutex=False)
    else:
        for acc in login + logout:
            pid = pid_dict.get(acc, None)
            if pid is None:
                subfunc_file.update_sw_acc_data(sw, acc, has_mutex=None)
            subfunc_file.update_sw_acc_data(sw, acc, pid=pid_dict.get(acc, None))
        # 更新json表中各微信进程的互斥体情况
        success, has_mutex = subfunc_file.update_has_mutex_from_all_acc(sw)

    # print(f"完成记录账号对应pid，用时：{time.time() - start_time:.4f} 秒")
    acc_list_dict = {
        "login": login,
        "logout": logout
    }
    return True, (acc_list_dict, proc_dict, has_mutex)


def get_main_hwnd_of_accounts(acc_list, sw):
    target_class, = subfunc_file.get_details_from_remote_setting_json(sw, main_wnd_class=None)
    if target_class is None:
        messagebox.showerror("错误", f"{sw}平台未适配")
        return False
    for acc in acc_list:
        pid, = subfunc_file.get_sw_acc_data(sw, acc, pid=None)
        hwnd_list = hwnd_utils.get_hwnd_list_by_pid_and_class(pid, target_class)
        # print(pid, hwnd_list)
        if len(hwnd_list) > 0:
            hwnd = hwnd_list[0]
            subfunc_file.update_sw_acc_data(sw, acc, main_hwnd=hwnd)
            display_name = get_acc_origin_display_name(sw, acc)
            hwnd_utils.set_window_title(hwnd, f"微信 - {display_name}")
