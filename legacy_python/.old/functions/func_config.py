import os
import shutil
import time
from tkinter import messagebox

import func_setting
from legacy_python.functions import subfunc_file
from legacy_python.functions.sw_func import SwOperator
from public_class.global_members import GlobalMembers
from resources import Config
from legacy_python.utils import hwnd_utils, handle_utils
from legacy_python.utils.logger_utils import mylogger as logger


def operate_acc_config(method, sw, account):
    """
    使用use或add操作账号对应的登录配置
    :param method: 操作方法
    :param sw: 选择的软件标签
    :param account: 账号
    :return: 是否成功，携带的信息
    """
    if method not in ["use", "add"]:
        logger.error("未知字段：" + method)
        return False, "未知字段"
    data_path = func_setting.get_sw_data_dir(sw)
    if not data_path:
        return False, "无法获取WeChat数据路径"
    config_path_suffix, cfg_items = subfunc_file.get_details_from_remote_setting_json(
        sw, config_path_suffix=None, config_file_list=None)

    origin_acc_dict = dict()
    # 构建相关文件列表
    for item in cfg_items:
        # 拼接出源配置路径
        origin_cfg_path = os.path.join(str(data_path), str(config_path_suffix), str(item)).replace("\\", "/")
        # 提取源配置文件的后缀
        item_suffix = item.split(".")[-1]
        acc_cfg_item = f"{account}.{item_suffix}"
        acc_cfg_path = (os.path.join(str(data_path), str(config_path_suffix), acc_cfg_item)
                        .replace("\\", "/"))
        # 构建配置字典
        origin_acc_dict.update({origin_cfg_path: acc_cfg_path})
        # print("\n".join([item, origin_cfg_path, item_suffix, acc_cfg_item, acc_cfg_path]))
        print(item, origin_acc_dict)

    paths_to_del = list(origin_acc_dict.keys()) if method == "use" else list(origin_acc_dict.values())

    # 移除配置项
    for p in paths_to_del:
        try:
            if os.path.isfile(p):
                os.remove(p)
            elif os.path.isdir(p):
                shutil.rmtree(p)
        except Exception as e:
            logger.error(e)
            return False, f"移除配置项目时发生错误：{str(e)}"

    success_list = []
    # 拷贝配置项
    for origin, acc in origin_acc_dict.items():
        print(origin, acc)
        source_path = acc if method == "use" else origin
        dest_path = origin if method == "use" else acc

        try:
            if os.path.isfile(source_path):
                shutil.copy2(source_path, dest_path, follow_symlinks=False)
                success_list.append(dest_path)
            elif os.path.isdir(source_path):
                shutil.copytree(source_path, dest_path, symlinks=True)
                success_list.append(dest_path)
            else:
                logger.error(f"配置项目异常：{origin}-{acc}")
                return False, f"配置项目异常：{origin}-{acc}"
        except Exception as e:
            logger.error(e)
            return False, f"复制配置文件时发生错误：{str(e)}"
    return True, success_list


def open_sw_and_ask(sw, account, multirun_mode):
    """
    尝试打开微信，让用户判断是否是对应的账号，根据用户结果去创建配置或结束
    :param sw:
    :param account: 账号
    :param multirun_mode: 是否全局多开状态
    :return: 是否对应
    """
    root_class = GlobalMembers.root_class
    root = root_class.root
    acc_tab_ui = root_class.acc_tab_ui

    if messagebox.askyesno(
            "确认",
            "建议在只登录了一个账号时，或刚刚登录了此账号时进行配置，\n成功率更高。将唤起登录窗口，请勿重复登录。是否继续？"
    ):
        redundant_wnd_classes, executable_name, cfg_handles = subfunc_file.get_details_from_remote_setting_json(
            sw, redundant_wnd_class=None, executable=None, cfg_handle_regex_list=None)
        hwnd_utils.close_all_by_wnd_classes(redundant_wnd_classes)
        handle_utils.close_sw_mutex_by_handle(
            Config.HANDLE_EXE_PATH, executable_name, cfg_handles)
        SwOperator.kill_sw_multiple_processes(sw)
        time.sleep(0.5)
        sub_exe_process = SwOperator.open_sw(sw, multirun_mode)
        login_wnd_class, = subfunc_file.get_details_from_remote_setting_json(sw, login_wnd_class=None)
        wechat_hwnd = hwnd_utils.wait_open_to_get_hwnd(login_wnd_class, timeout=8)
        print(wechat_hwnd)
        if wechat_hwnd:
            if sub_exe_process:
                sub_exe_process.terminate()
            time.sleep(1)
            hwnd_utils.bring_hwnd_next_to_left_of_hwnd2(wechat_hwnd, root.winfo_id())
            if messagebox.askyesno("确认", "是否为对应的微信号？"):
                success, result = operate_acc_config('add', sw, account)
                if success is True:
                    created_list_text = "\n".join(result)
                    messagebox.showinfo("成功", f"已生成：\n{created_list_text}")
            hwnd_utils.close_by_wnd_class(login_wnd_class)
        else:
            messagebox.showerror("错误", "打开登录窗口失败")
    root.after(0, acc_tab_ui.refresh_frame, sw)
