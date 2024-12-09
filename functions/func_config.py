import os
import shutil
import time
from datetime import datetime
from tkinter import messagebox

from functions import func_setting, subfunc_wechat, subfunc_file
from resources import Config
from utils import hwnd_utils, handle_utils
from utils.logger_utils import mylogger as logger


def get_config_status_by_account(account, data_path, sw="WeChat") -> str:
    """
    通过账号的配置状态
    :param sw: 选择的软件标签
    :param data_path: 微信数据存储路径
    :param account: 账号
    :return: 配置状态
    """
    # print(sw, data_path, account)
    if not data_path:
        return "无法获取配置路径"
    config_path_suffix, config_files = subfunc_file.get_details_from_remote_setting_json(
        sw, config_path_suffix=None, config_file_list=None)
    if len(config_files) == 0 or config_files is None:
        return "无法获取配置路径"
    file = config_files[0]
    file_suffix = file.split(".")[-1]
    dest_filename = f"{account}.{file_suffix}"
    acc_cfg_path = (os.path.join(str(data_path), str(config_path_suffix), dest_filename)
                    .replace("\\", "/"))
    if os.path.exists(acc_cfg_path):
        mod_time = os.path.getmtime(acc_cfg_path)
        date = datetime.fromtimestamp(mod_time)
        return f"{date.year % 100:02}-{date.month}-{date.day} {date.hour:02}:{date.minute:02}"
    else:
        return "无配置"


def use_config(account, sw="WeChat"):
    """
    使用账号对应的登录配置
    :param sw: 选择的软件标签
    :param account: 账号
    :return: 是否成功应用配置
    """
    data_path = func_setting.get_sw_data_dir(sw=sw)
    if not data_path:
        messagebox.showerror("错误", "无法获取WeChat数据路径")
        return False
    config_path_suffix, config_files = subfunc_file.get_details_from_remote_setting_json(
        sw, config_path_suffix=None, config_file_list=None)

    # 移除所有文件
    for item in config_files:
        # print(account, item)
        # 拼接出源配置路径
        config_path = os.path.join(str(data_path), str(config_path_suffix), str(item)).replace("\\", "/")
        if os.path.isfile(config_path):
            try:
                os.remove(config_path)
            except Exception as e:
                logger.error(e)
                messagebox.showerror("错误", f"复制配置文件时发生错误：{str(e)}")
                return False
        elif os.path.isdir(config_path):
            try:
                shutil.rmtree(config_path)
            except Exception as e:
                logger.error(e)
                messagebox.showerror("错误", f"复制配置文件时发生错误：{str(e)}")
                return False
        else:
            logger.error(f"配置文件不存在：{config_path}")
            # messagebox.showerror("错误", f"配置文件不存在：{config_path}")
            # return False

    # 拷贝新的配置文件
    for item in config_files:
        # 拼接出源配置路径
        config_path = os.path.join(str(data_path), str(config_path_suffix), str(item)).replace("\\", "/")
        # 提取源配置文件的后缀
        file_suffix = item.split(".")[-1]

        dest_filename = f"{account}.{file_suffix}"
        acc_config_path = (os.path.join(str(data_path), str(config_path_suffix), dest_filename)
                           .replace("\\", "/"))

        # print(item, file_suffix, dest_filename, acc_config_path)

        if os.path.isfile(acc_config_path):
            try:
                shutil.copy2(acc_config_path, config_path, follow_symlinks=False)
            except Exception as e:
                logger.error(e)
                messagebox.showerror("错误", f"复制配置文件时发生错误：{str(e)}")
                return False
        elif os.path.isdir(acc_config_path):
            try:
                shutil.copytree(acc_config_path, config_path, symlinks=True)
            except Exception as e:
                logger.error(e)
                messagebox.showerror("错误", f"复制配置文件时发生错误：{str(e)}")
                return False
        else:
            logger.error(f"配置文件不存在：{acc_config_path}")
            messagebox.showerror("错误", f"配置文件不存在：{acc_config_path}")
            return False
    return True


def create_config(account, sw="WeChat"):
    """
    创建账号的登录配置文件
    :param sw: 选择软件
    :param account: 账号
    :return: 是否创建成功
    """
    # print(sw)
    data_path = func_setting.get_sw_data_dir(sw=sw)
    # print(data_path)
    if data_path is None:
        messagebox.showerror("错误", "无法获取WeChat数据路径")
        return False
    login_wnd_class, config_path_suffix, config_files = subfunc_file.get_details_from_remote_setting_json(
        sw, login_wnd_class=None, config_path_suffix=None, config_file_list=None)

    created_list = []
    for file in config_files:
        # print(account, file)
        # 拼接出源配置路径
        config_path = os.path.join(str(data_path), str(config_path_suffix), str(file)).replace("\\", "/")
        # 提取源配置文件的后缀
        file_suffix = os.path.splitext(config_path)
        if len(file_suffix) != 1:
            file_suffix = file_suffix[1]
        else:
            file_suffix = ""

        dest_filename = f"{account}{file_suffix}"
        acc_config_path = os.path.join(str(data_path), str(config_path_suffix), dest_filename).replace("\\", "/")

        if os.path.isfile(config_path):
            try:
                if os.path.exists(acc_config_path):
                    os.remove(acc_config_path)
                shutil.copy2(config_path, acc_config_path, follow_symlinks=False)
                hwnd_utils.close_wnd_by_name(login_wnd_class)
                created_list.append(dest_filename)
            except Exception as e:
                logger.error(e)
                messagebox.showerror("错误", f"生成配置文件时发生错误：{str(e)}")
                return False
        elif os.path.isdir(config_path):
            try:
                if os.path.exists(acc_config_path):
                    os.remove(acc_config_path)
                shutil.copytree(config_path, acc_config_path, dirs_exist_ok=True)
                hwnd_utils.close_wnd_by_name(login_wnd_class)
                created_list.append(dest_filename)
            except Exception as e:
                logger.error(e)
                return False
        else:
            messagebox.showerror("错误", f"配置文件不存在：{config_path}")
            return False

    created_list_text = "\n".join(created_list)
    messagebox.showinfo("成功", f"配置文件已生成：\n{created_list_text}")
    return True


def test(m_class, account, multiple_status, tab="WeChat"):
    """
    尝试打开微信，让用户判断是否是对应的账号，根据用户结果去创建配置或结束
    :param account: 账号
    :param m_class: 主窗口类
    :param multiple_status: 是否全局多开状态
    :return: 是否对应
    """
    if messagebox.askyesno(
            "确认",
            "建议在只登录了一个账号时，或刚刚登录了此账号时进行配置，\n成功率更高。将唤起登录窗口，请勿重复登录。是否继续？"
    ):
        redundant_wnd_classes, executable_name, cfg_handles = subfunc_file.get_details_from_remote_setting_json(
            tab, redundant_wnd_class=None, executable=None, cfg_handle_regex_list=None)
        hwnd_utils.close_all_wnd_by_classes(redundant_wnd_classes)
        handle_utils.close_sw_mutex_by_handle(
            Config.HANDLE_EXE_PATH, executable_name, cfg_handles)
        subfunc_wechat.kill_wechat_multiple_processes(tab)
        time.sleep(0.5)
        has_mutex_dict = subfunc_wechat.get_mutex_dict(tab)
        sub_exe_process, _ = subfunc_wechat.open_wechat(multiple_status, has_mutex_dict, tab)
        login_wnd_class, = subfunc_file.get_details_from_remote_setting_json(tab, login_wnd_class=None)
        wechat_hwnd = hwnd_utils.wait_for_wnd_open(login_wnd_class, timeout=8)
        if wechat_hwnd:
            if sub_exe_process:
                sub_exe_process.terminate()
            time.sleep(2)
            if messagebox.askyesno("确认", "是否为对应的微信号？"):
                create_config(account, tab)
            else:
                hwnd_utils.close_wnd_by_name(login_wnd_class)
        else:
            messagebox.showerror("错误", "打开登录窗口失败")
    m_class.root.after(0, m_class.refresh_main_frame)
