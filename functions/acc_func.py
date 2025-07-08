import base64
import datetime
import os
import random
import re
import shutil
import sys
import threading
import time
import tkinter as tk
from collections.abc import Iterable
from fnmatch import fnmatch
from pathlib import Path
from tkinter import messagebox, filedialog
from typing import Dict, List, Tuple

import psutil
import win32con
import win32gui
import win32process
import winshell
from PIL import Image, ImageDraw, ImageFont

from functions import subfunc_file
from functions.acc_func_impl import AccInfoFuncImpl
from functions.func_tool import FuncTool
from functions.sw_func import SwOperator, SwInfoFunc
from public_class.enums import AccKeys, SW, LocalCfg, MultirunMode, CfgStatus
from public_class.global_members import GlobalMembers
from resources import Constants
from resources.config import Config
from resources.strings import Strings
from utils import process_utils, image_utils, hwnd_utils, handle_utils, file_utils
from utils.encoding_utils import StringUtils
from utils.logger_utils import mylogger as logger, Printer


class AccOperator:
    @staticmethod
    def _get_screen_size() -> Tuple[int, int]:
        """获取屏幕尺寸"""
        screen_width = int(tk.Tk().winfo_screenwidth())
        screen_height = int(tk.Tk().winfo_screenheight())
        if not screen_height or not screen_width:
            size = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.SCREEN_SIZE).split('*')
            screen_width, screen_height = int(size[0]), int(size[1])
        if not screen_height or not screen_width:
            screen_width, screen_height = 1920, 1080
        return screen_width, screen_height

    @staticmethod
    def _get_max_dimensions_from_sw_list(sw_list):
        """获取多个平台中最大的登录窗口尺寸"""
        max_width = 0
        max_height = 0
        for software in sw_list:
            # 获取尺寸配置
            siz = subfunc_file.fetch_sw_setting_or_set_default_or_none(software, "login_size")
            if siz and siz.strip():
                try:
                    # 拆分宽度和高度，并确保为整数
                    width, height = map(int, siz.split('*'))
                    if width > max_width:
                        max_width = width
                        max_height = height
                except ValueError:
                    # 忽略尺寸配置格式错误的情况
                    continue
        return (max_width, max_height) if max_width > 0 else None

    @staticmethod
    def _get_now_login_hwnd_from_cache(sw, acc, excluded_hwnd_list):
        """用缓存类名来获取当前登录窗口hwnd"""
        Printer().debug(f"传入参数: {sw}, {acc}, {excluded_hwnd_list}")
        cached_class, = subfunc_file.get_sw_acc_data(sw, acc, login_wnd_class=None)
        if cached_class is None:
            return None
        sw_hwnd = hwnd_utils.wait_hwnd_exclusively_by_class(excluded_hwnd_list, cached_class)
        if sw_hwnd is None:
            return None
        return sw_hwnd

    @staticmethod
    def _set_wnd_pos(hwnd, pos):
        if hwnd is not None:
            new_left, new_top = pos
            try:
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOP,
                    new_left,
                    new_top,
                    0,  # 宽度设置为 0 表示不改变
                    0,  # 高度设置为 0 表示不改变
                    win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
                )
            except Exception as e:
                logger.error(e)

    @staticmethod
    def _thread_to_click_all_login_buttons_and_wait_refresh(sw, hwnds):
        """点击列表所有登录窗口的登录按钮,等待所有窗口关闭则刷新"""
        # 判断是否需要自动点击按钮
        root_class = GlobalMembers.root_class
        root = root_class.root
        login_ui = root_class.login_ui
        auto_press = root_class.global_settings_value.auto_press
        if auto_press:
            # 两轮点击所有窗口的登录，防止遗漏
            time.sleep(0.5)
            inner_start_time = time.time()
            for i in range(1):
                for h in hwnds:
                    hwnd_details = hwnd_utils.get_hwnd_details_of_(h)
                    cx = int(hwnd_details["width"] * 0.5)
                    cy = int(hwnd_details["height"] * 0.75)
                    hwnd_utils.do_click_in_wnd(h, cx, cy)
                    time.sleep(0.2)
                print(f"通过位置查找，用时：{time.time() - inner_start_time:.4f}s")

            inner_start_time = time.time()
            for h in hwnds:
                titles = ["进入微信", "进入WeChat", "Enter Weixin"]  # 添加所有需要查找的标题
                try:
                    # cx, cy = hwnd_utils.get_widget_center_pos_by_hwnd_and_possible_titles(h, titles)  # avg:2.4s
                    cx, cy = hwnd_utils.find_widget_with_uiautomation(h, titles)  # avg:1.9s
                    # print(hwnd_utils.get_child_hwnd_list_of_(h))
                    # cx, cy = hwnd_utils.find_widget_with_win32(h, titles)  # 微信窗口非标准窗口，查找不了
                    # cx, cy = hwnd_utils.find_widget_with_pygetwindow(h, titles)  # 只能用来查找窗口标题，无法用来查找窗口内的控件
                    # cx, cy = hwnd_utils.find_widget_with_uia(h, titles)  # 有问题，修复较复杂，不管
                    print(f"通过控件查找，用时：{time.time() - inner_start_time:.4f}s")
                    if cx is not None and cy is not None:
                        hwnd_utils.do_click_in_wnd(h, int(cx), int(cy))
                        break  # 找到有效坐标后退出循环
                except TypeError as te:
                    logger.warning(te)
                    print("没有按钮，应该是点过啦~")
                except Exception as fe:
                    logger.error(fe)
        else:
            print("请手动点击登录按钮")

        # 结束条件为所有窗口消失或等待超过20秒（网络不好则会这样）
        ddl_time = time.time() + 30
        while True:
            # 判断所有 hwnd 是否都不存在了
            all_closed = all(not win32gui.IsWindow(hwnd) for hwnd in hwnds)
            if all_closed:
                break
            if time.time() > ddl_time:
                break
        root.after(0, login_ui.refresh_frame, sw)

    @staticmethod
    def _auto_login_accounts(login_dict: Dict[str, List]):
        """传入{平台: 账号列表}字典，进行全自动登录"""
        root_class = GlobalMembers.root_class
        # 统计一下数目,若为0则直接返回 ===================================================================
        acc_cnt = 0
        for sw, acc_list in login_dict.items():
            if isinstance(acc_list, list):
                acc_cnt += len(acc_list)
        if acc_cnt is None or acc_cnt == 0:
            return
        # 计算窗口排列位置 ===================================================================
        screen_size = AccOperator._get_screen_size()
        max_login_size = AccOperator._get_max_dimensions_from_sw_list(list(login_dict.keys()))
        if max_login_size is None:
            max_login_size = (int(screen_size[0] / 6), int(screen_size[1] / 3))
        all_acc_positions = hwnd_utils.layout_wnd_positions(acc_cnt, max_login_size, screen_size)
        # 开始登录过程 ===================================================================
        all_acc_turn = 0  # 所有账号队列的当前轮次
        all_opened_hwnds = []  # 记录新打开的登录窗口
        all_excluded_hwnds = []  # 记录要排除的已存在的登录窗口
        for sw, accounts in login_dict.items():
            Printer().vital(f"{sw}登录")
            if not isinstance(accounts, list) or len(accounts) == 0:
                continue
            # 初始化获取数据 -------------------------------------------------------------------
            multirun_mode = root_class.sw_classes[sw].multirun_mode
            origin_exe_path = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.INST_PATH)
            login_wnd_class, exec_name, cfg_handles_regexes, login_wildcards = (
                subfunc_file.get_remote_cfg(
                    sw,
                    login_wnd_class=None,
                    executable=None,
                    cfg_handle_regex_list=None,
                    login_wnd_class_wildcards=None
                )
            )
            # mutant_wildcards, config_wildcards = subfunc_file.get_remote_cfg(
            #     sw,
            #     mutant_handle_wildcards=None,
            #     config_handle_wildcards=None
            # )
            # 清空闲置的登录窗口、多开器，清空并拉取各账户的登录和互斥体情况 -------------------------------------------------------------------
            SwOperator.kill_sw_multiple_processes(sw)
            kill_idle: bool = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.KILL_IDLE_LOGIN_WND)
            kill_idle = True if kill_idle is True else False  # 是否需要关闭闲置的登录窗口
            remained_idle_wnd_list = SwOperator.get_idle_login_wnd_and_close_if_necessary(sw, kill_idle)
            all_excluded_hwnds.extend(remained_idle_wnd_list)
            # 检查所有pid及互斥体情况 -------------------------------------------------------------------
            SwInfoFunc.record_sw_pid_mutex_dict_when_start_login(sw)
            # 开始平台的账号列表登录 -------------------------------------------------------------------
            sw_opened_hwnds = []  # 当前平台的登录窗口列表

            start_time = time.time()
            for j in range(len(login_dict[sw])):
                # 调取配置,打开登录窗口 *******************************************************************
                sub_proc = None
                if AccInfoFunc.is_acc_coexist(sw, accounts[j]):
                    # 共存账号
                    print(f"[OK]{accounts[j]}是共存号,无需登录配置")
                    coexist_exe_path = os.path.join(os.path.dirname(origin_exe_path), accounts[j])
                    sw_proc = process_utils.create_process_without_admin(coexist_exe_path)
                else:
                    # 主程序账号
                    handle_utils.close_sw_mutex_by_handle(
                        Config.HANDLE_EXE_PATH, exec_name, cfg_handles_regexes)
                    success, _ = AccOperator.operate_acc_config('use', sw, accounts[j])
                    if success:
                        Printer().print_vn(f"[OK]应用{accounts[j]}的登录配置")
                    else:
                        Printer().print_vn(f"[ERR]应用{accounts[j]}配置失败")
                        continue
                    sw_proc, sub_proc = SwOperator.open_sw(sw, multirun_mode)
                sw_proc_pid = sw_proc.pid if sw_proc else None
                # 等待打开窗口并获取hwnd *******************************************************************
                sw_hwnd = AccOperator._get_now_login_hwnd_from_cache(
                    sw, accounts[j], all_excluded_hwnds)
                # Printer().debug(f"通过缓存类名获取到的登录窗口：{sw_hwnd}")
                if sw_hwnd is None:
                    # 从精确类名未能获取,只能用类名通配模式来获取,并缓存起来
                    sw_hwnd, class_name = hwnd_utils.wait_hwnd_exclusively_by_pid_and_class_wildcards(
                        all_excluded_hwnds, sw_proc_pid, login_wildcards)
                    if class_name is not None:
                        subfunc_file.update_sw_acc_data(sw, accounts[j], login_wnd_class=class_name)
                if sub_proc:
                    sub_proc.terminate()
                Printer().debug(sw_hwnd)
                # 对hwnd进行处理 *******************************************************************
                # 确保打开了新的微信登录窗口
                if sw_hwnd is not None:
                    if sw_hwnd not in all_opened_hwnds:
                        all_opened_hwnds.append(sw_hwnd)
                    if sw_hwnd not in all_excluded_hwnds:
                        all_excluded_hwnds.append(sw_hwnd)
                    if sw_hwnd not in sw_opened_hwnds:
                        sw_opened_hwnds.append(sw_hwnd)
                    print(f"打开窗口成功：{sw_hwnd}")
                    subfunc_file.set_pid_mutex_all_values_to_false(sw)
                    if sw_proc_pid is None:
                        _, sw_proc_pid = win32process.GetWindowThreadProcessId(sw_hwnd)
                    subfunc_file.update_sw_acc_data(sw, AccKeys.PID_MUTEX, **{f"{sw_proc_pid}": True})
                else:
                    all_opened_hwnds.append(None)
                    sw_opened_hwnds.append(None)
                # 从第二个窗口开始,每打开一个窗口就安排上一个窗口的位置,上一个窗口若为空则不处理
                if all_acc_turn >= 1:
                    pre_hwnd = all_opened_hwnds[all_acc_turn - 1]
                    pre_wnd_pos = all_acc_positions[all_acc_turn - 1]
                    AccOperator._set_wnd_pos(pre_hwnd, pre_wnd_pos)
                # 逐次统计时间 *******************************************************************
                subfunc_file.update_statistic_data(
                    sw, 'auto', str(j + 1), multirun_mode, time.time() - start_time)
                all_acc_turn += 1

            # 统计平台平均时间 -------------------------------------------------------------------
            subfunc_file.update_statistic_data(sw, 'auto', 'avg', multirun_mode,
                                               (time.time() - start_time) / acc_cnt)
            # 间隔一段时间后对平台的最后一个窗口移动 -------------------------------------------------------------------
            SwOperator.kill_sw_multiple_processes(sw)
            time.sleep(3)
            Printer().debug(sw_opened_hwnds, all_opened_hwnds, all_excluded_hwnds, all_acc_turn)
            sw_last_hwnd = all_opened_hwnds[all_acc_turn - 1]
            sw_last_pos = all_acc_positions[all_acc_turn - 1]
            AccOperator._set_wnd_pos(sw_last_hwnd, sw_last_pos)
            # 启动善后线程 -------------------------------------------------------------------
            threading.Thread(
                target=AccOperator._thread_to_click_all_login_buttons_and_wait_refresh,
                args=(sw, sw_opened_hwnds,)
            ).start()
        return

    @staticmethod
    def start_auto_login_accounts_thread(login_dict: Dict[str, List]):
        """
        开启一个线程来执行登录操作
        :param login_dict: 登录列表字典
        :return: None
        """
        try:
            threading.Thread(
                target=AccOperator._auto_login_accounts,
                args=(login_dict,)
            ).start()
        except Exception as e:
            logger.error(e)

    @staticmethod
    def operate_acc_config(method, sw, acc):
        """
        使用use或add操作账号对应的登录配置
        :param method: 操作方法
        :param sw: 选择的软件标签
        :param acc: 账号
        :return: 是否成功，携带的信息
        """
        if method not in ["use", "add"]:
            logger.error("未知字段：" + method)
            return False, "未知字段"
        data_path = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.DATA_DIR)
        if not data_path:
            return False, "无法获取WeChat数据路径"
        config_path_suffix, cfg_basename_list = subfunc_file.get_remote_cfg(
            sw, config_path_suffix=None, config_file_list=None)

        origin_acc_dict = dict()
        # 构建相关文件列表
        for cfg_basename in cfg_basename_list:
            # 拼接出源配置路径
            origin_cfg_path = os.path.join(
                str(data_path), str(config_path_suffix), str(cfg_basename)).replace("\\", "/")
            acc_cfg_item = f"{acc}_{cfg_basename}"
            acc_cfg_path = (os.path.join(str(data_path), str(config_path_suffix), acc_cfg_item)
                            .replace("\\", "/"))
            origin_acc_dict.update({origin_cfg_path: acc_cfg_path})

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

    @staticmethod
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
        login_ui = root_class.login_ui
        if AccInfoFunc.is_acc_coexist(sw, account):
            messagebox.showwarning("提示", "共存账号无需配置!")
            return
        if messagebox.askyesno(
                "确认",
                "建议在只登录了一个账号时，或刚刚登录了此账号时进行配置，\n成功率更高。将唤起登录窗口，请勿重复登录。是否继续？"
        ):
            # 手动登录原始程序
            all_excluded_hwnds = []
            SwOperator.kill_sw_multiple_processes(sw)
            remained_idle_wnd_list = SwOperator.get_idle_login_wnd_and_close_if_necessary(sw, False)
            all_excluded_hwnds.extend(remained_idle_wnd_list)
            SwInfoFunc.record_sw_pid_mutex_dict_when_start_login(sw)
            sw_proc, sub_proc = SwOperator.open_sw(sw, multirun_mode)
            sw_proc_pid = sw_proc.pid if sw_proc else None
            login_wnd_class, = subfunc_file.get_remote_cfg(sw, login_wnd_class=None)
            sw_hwnd = AccOperator._get_now_login_hwnd_from_cache(
                sw, account, all_excluded_hwnds)
            if sw_hwnd is None:
                # 从精确类名未能获取,只能用类名通配模式来获取,并缓存起来
                sw_hwnd, class_name = hwnd_utils.wait_hwnd_exclusively_by_pid_and_class_wildcards(
                    all_excluded_hwnds, sw_proc_pid, [login_wnd_class])
                if class_name is not None:
                    subfunc_file.update_sw_acc_data(sw, account, login_wnd_class=class_name)
            if sub_proc:
                sub_proc.terminate()
            if sw_hwnd:
                time.sleep(1)
                hwnd_utils.bring_hwnd_next_to_left_of_hwnd2(sw_hwnd, root.winfo_id())
                if messagebox.askyesno("确认", "是否为对应的账号？"):
                    success, result = AccOperator.operate_acc_config('add', sw, account)
                    if success is True:
                        created_list_text = "\n".join(result)
                        messagebox.showinfo("成功", f"已生成：\n{created_list_text}")
                hwnd_utils.close_a_wnd_by_win32_classname(login_wnd_class)
            else:
                messagebox.showerror("错误", "打开登录窗口失败")
        root.after(0, login_ui.refresh_frame, sw)

    @staticmethod
    def switch_to_sw_account_wnd(item_id):
        """切换到指定的账号窗口"""
        sw, acc = item_id.split("/")
        main_hwnd, = subfunc_file.get_sw_acc_data(sw, acc, main_hwnd=None)
        # 恢复平台指定主窗口
        if sw == SW.WECHAT:
            hwnd_utils.restore_window(main_hwnd)
        elif sw == SW.WEIXIN:
            # 如果微信没有被隐藏到后台
            if hwnd_utils.is_window_visible(main_hwnd):
                hwnd_utils.restore_window(main_hwnd)
            else:
                # 先恢复窗口，再模拟双击以激活窗口
                hwnd_utils.restore_window(main_hwnd)
                time.sleep(0.2)
                hwnd_utils.do_click_in_wnd(main_hwnd, 8, 8)
                hwnd_utils.do_click_in_wnd(main_hwnd, 8, 8)
        else:
            hwnd_utils.restore_window(main_hwnd)

    @staticmethod
    def quit_selected_accounts(sw, accounts_selected):
        accounts_to_quit = []
        for acc in accounts_selected:
            pid, = subfunc_file.get_sw_acc_data(sw, acc, pid=None)
            display_name = AccInfoFunc.get_acc_origin_display_name(sw, acc)
            cleaned_display_name = StringUtils.clean_texts(display_name)
            accounts_to_quit.append(f"[{pid}: {cleaned_display_name}]")
        accounts_to_quit_str = "\n".join(accounts_to_quit)
        if messagebox.askokcancel("提示",
                                  f"确认退登：\n{accounts_to_quit_str}？"):
            try:
                quited_accounts = AccOperator._quit_accounts(sw, accounts_selected)
                quited_accounts_str = "\n".join(quited_accounts)
                messagebox.showinfo("提示", f"已退登：\n{quited_accounts_str}")
            except Exception as e:
                logger.error(e)
            return True
        return False

    @staticmethod
    def _quit_accounts(sw, accounts):
        quited_accounts = []
        for account in accounts:
            pid, = subfunc_file.get_sw_acc_data(sw, account, pid=None)
            display_name = AccInfoFunc.get_acc_origin_display_name(sw, account)
            cleaned_display_name = StringUtils.clean_texts(display_name)
            executable_wildcards, = subfunc_file.get_remote_cfg(
                sw, executable_wildcards=None)
            if isinstance(executable_wildcards, list):
                success = process_utils.psutil_kill_process_tree_if_matched_in_wildcards(pid, executable_wildcards)
                if success is True:
                    quited_accounts.append(f"[{cleaned_display_name}: {pid}]")
                    subfunc_file.update_sw_acc_data(sw, account, pid=None)
        return quited_accounts

    @staticmethod
    def _generate_close_mutex_bat(handle_exe_path, target_exe_name, mutex_names):
        """
        生成 .bat 文件，用于通过 handle.exe 查找并关闭指定程序中的互斥体句柄。
        :param handle_exe_path: handle.exe 的绝对路径
        :param target_exe_name:      要查找的目标进程名称（如 SomeProgram.exe）
        :param mutex_names:      要查找的互斥体全名（如 \\BaseNamedObjects\\MyMutex）
        """
        header = f"""REM 删除互斥体
@echo off
REM 设置路径和参数
set "HANDLE_EXE={handle_exe_path}"
set "TARGET_EXE={target_exe_name}"
"""

        body = 'setlocal enabledelayedexpansion\n'
        for i, mutex in enumerate(mutex_names):
            var_name = f"MUTEX{i}"
            body += f'set "{var_name}={mutex}"\n'

        body += "\nREM 遍历所有互斥体并查找+关闭句柄\n"
        for i in range(len(mutex_names)):
            var = f"%MUTEX{i}%"
            body += f"""
echo ========= 查找互斥体：{var} =========
"%HANDLE_EXE%" -a -p "%TARGET_EXE%" "{var}" > temp_handle.txt

for /f "tokens=3,6 delims= " %%a in ('findstr /i "{var}" temp_handle.txt') do (
    set "PID=%%a"
    set "HANDLE=%%b"
    call set "PID=%%PID: =%%"
    call set "HANDLE=%%HANDLE: =%%"
    echo 找到句柄 PID: !PID!, 句柄: !HANDLE!
    echo 尝试关闭句柄...
    echo y | "%HANDLE_EXE%" -c !HANDLE! -p !PID!
    echo 已关闭
)
"""

        footer = """
del temp_handle.txt
echo 所有互斥体处理完成
"""
        content = header + body + footer
        return content

    @staticmethod
    def _generate_replace_cfg_cmds(sw, acc, data_path):
        """生成用于替换配置文件的bat指令"""
        config_path_suffix, cfg_items = subfunc_file.get_remote_cfg(
            sw, config_path_suffix=None, config_file_list=None)
        # 构建相关文件列表
        replace_cmd_list = []
        for item in cfg_items:
            # 拼接出源配置路径
            origin_cfg_path = os.path.join(
                str(data_path), str(config_path_suffix), str(item)).replace("/", "\\")
            # 提取源配置文件的后缀
            item_suffix = item.split(".")[-1]
            acc_cfg_item = f"{acc}.{item_suffix}"
            acc_cfg_path = (os.path.join(str(data_path), str(config_path_suffix), acc_cfg_item)
                            .replace("/", "\\"))
            remove_cmd = f'echo y | del "{origin_cfg_path}"'
            copy_cmd = f'echo y | copy "{acc_cfg_path}" "{origin_cfg_path}"'
            replace_cmd = f"{remove_cmd}\n{copy_cmd}"
            replace_cmd_list.append(replace_cmd)

            # # 构建配置字典
        replace_cmds_str = "\n".join(replace_cmd_list)
        replace_cfg_cmd = f"""
@echo off
chcp 65001
REM 替换配置文件
{replace_cmds_str}
if errorlevel 1 (
    echo 复制配置文件失败
    exit /b 1
)
echo 替换配置文件成功
"""
        return replace_cfg_cmd

    @staticmethod
    def _generate_start_cmds_if_freely_multirun(sw_path):
        close_handle_cmds_str = ""
        #         start_cmds_str = f"""
        # REM 启动
        # cmd /u /c "start "" "{sw_path}""
        # if errorlevel 1 (
        #     echo 启动微信失败，请检查路径是否正确。
        #     pause
        #     exit /b 1
        # )
        # """
        start_vbs_str = f"""
WScript.Sleep 2000

shell.ShellExecute "{sw_path}", "", "", "", 1
"""
        handle_path = os.path.join(Config.PROJ_EXTERNAL_RES_PATH, "handle.exe")
        # 判断环境
        if getattr(sys, 'frozen', False):  # 打包环境
            icon_exe = sys.executable  # 当前程序的 exe
        else:  # PyCharm 或其他开发环境
            icon_exe = handle_path  # 使用 handle_path
        prefix = "[需开全局多开]"
        return [(icon_exe, prefix, close_handle_cmds_str, start_vbs_str)]

    @staticmethod
    def _generate_start_cmds_for_handle(handle_path, sw_path, mutex_names):
        sw_exe_name = os.path.basename(sw_path)
        close_handle_cmds_str = AccOperator._generate_close_mutex_bat(handle_path, sw_exe_name, mutex_names)
        #         start_cmds_str = f"""REM 启动
        # cmd /u /c "start "" "{sw_path}""
        # if errorlevel 1 (
        #     echo 启动微信失败，请检查路径是否正确。
        #     pause
        #     exit /b 1
        # )
        # """
        start_vbs_str = f"""
WScript.Sleep 5000

shell.ShellExecute "{sw_path}", "", "", "", 1
"""
        prefix = "[handle]"
        return [(sw_path, prefix, close_handle_cmds_str, start_vbs_str)]

    @staticmethod
    def _generate_start_cmds_for_other(sw):
        res_tuple = []
        exe_files = [str(p) for p in Path(Config.PROJ_EXTERNAL_RES_PATH).rglob(f"{sw}Multiple_*.exe")]
        for exe_file in exe_files:
            exe_name = os.path.basename(exe_file)
            right_part = exe_name.split('_', 1)[1].rsplit('.exe', 1)[0]
            prefix = f"[{right_part}]"
            close_handle_cmds_str = ""
            #             start_cmds_str = f"""
            # REM 启动
            # cmd /u /c "start "" "{exe_file}""
            # if errorlevel 1 (
            #     echo 启动微信失败，请检查路径是否正确。
            #     pause
            #     exit /b 1
            # )
            # """
            start_vbs_str = f"""
WScript.Sleep 2000

shell.ShellExecute "{exe_file}", "", "", "", 1
"""
            res_tuple.append((exe_file, prefix, close_handle_cmds_str, start_vbs_str))
        return res_tuple

    @staticmethod
    def _create_bat_icon_lnk(sw, acc, icon_exe, acc_avatar, prefix, admin_bat_str, normal_vbs_str):
        # 确保路径存在
        account_file_path = os.path.join(Config.PROJ_USER_PATH, sw, f'{acc}')
        if not os.path.exists(account_file_path):
            os.makedirs(account_file_path)
        # 保存为批处理文件
        sw_display_name = StringUtils.clean_texts(SwInfoFunc.get_sw_origin_display_name(sw))
        acc_display_name = StringUtils.clean_texts(AccInfoFunc.get_acc_origin_display_name(sw, acc))
        admin_bat_file_path = os.path.join(
            Config.PROJ_USER_PATH, sw, f'{acc}',
            f'{prefix}{sw_display_name}{acc_display_name}[admin].bat').replace("/", "\\")
        # bat_file_path = os.path.join(
        #     Config.PROJ_USER_PATH, sw, f'{acc}', f'{prefix}{sw_display_name}{acc_display_name}.bat').replace("/", "\\")
        vbs_file_path = os.path.join(
            Config.PROJ_USER_PATH, sw, f'{acc}',
            f'{prefix}{sw_display_name}{acc_display_name}.vbs').replace("/", "\\")
        # -以带有BOM的UTF-8格式写入管理员bat文件
        with open(admin_bat_file_path, 'w', encoding='utf-8-sig') as bat_file:
            bat_file.write(admin_bat_str)
        print(f"批处理文件已生成: {admin_bat_file_path}")

        #         # -拼接一个先运行管理员bat文件再执行普通bat命令的bat文件
        #         bat_file_content = f"""@echo off
        # chcp 65001 >nul
        # REM 执行 VBS 提权执行 bat
        # cscript //nologo "{vbs_file_path}"
        #
        # {normal_vbs_str}
        #         """
        #         with open(bat_file_path, 'w', encoding='utf-8-sig') as bat_file:
        #             bat_file.write(bat_file_content)
        #         print(f"批处理文件已生成: {bat_file_path}")

        # -生成vbs文件
        vbs_content = f"""
Set shell = CreateObject("Shell.Application")
shell.ShellExecute "{admin_bat_file_path}", "", "", "runas", 1
{normal_vbs_str}
"""
        with open(vbs_file_path, "w", encoding="utf-16") as f:
            f.write(vbs_content)
        # 获取桌面路径
        desktop = winshell.desktop()
        # 获取批处理文件名并去除后缀
        bat_file_name = os.path.splitext(os.path.basename(vbs_file_path))[0]
        # 构建快捷方式路径
        shortcut_path = os.path.join(desktop, f"{bat_file_name}.lnk")

        # 图标文件路径
        acc_dir = os.path.join(Config.PROJ_USER_PATH, str(sw), f"{acc}")
        exe_name = os.path.splitext(os.path.basename(icon_exe))[0]

        # 步骤1：提取图标为图片
        extracted_exe_png_path = os.path.join(acc_dir, f"{exe_name}_extracted.png")
        image_utils.extract_icon_to_png(icon_exe, extracted_exe_png_path)

        # 步骤2：合成图片
        ico_jpg_path = os.path.join(acc_dir, f"{acc}_{exe_name}.png")
        image_utils.add_diminished_se_corner_mark_to_image(acc_avatar, extracted_exe_png_path, ico_jpg_path)

        # 步骤3：对图片转格式
        ico_path = os.path.join(acc_dir, f"{acc}_{exe_name}.ico")
        image_utils.png_to_ico(ico_jpg_path, ico_path)

        # 清理临时文件
        os.remove(extracted_exe_png_path)

        # 创建快捷方式
        with winshell.shortcut(shortcut_path) as shortcut:
            shortcut.path = vbs_file_path
            shortcut.working_directory = os.path.dirname(vbs_file_path)
            # 修正icon_location的传递方式，传入一个包含路径和索引的元组
            shortcut.icon_location = (ico_path, 0)

        print(f"桌面快捷方式已生成: {os.path.basename(shortcut_path)}")

    @staticmethod
    def _create_starter_lnk_for_acc(sw, acc):
        """
        为账号创建快捷开启
        :param sw: 选择的软件标签
        :param acc: 账号
        :return: 是否成功
        """
        # 确保可以创建快捷启动
        data_path = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.DATA_DIR)
        sw_path = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.INST_PATH)
        if not data_path or not sw_path:
            messagebox.showerror("错误", "无法获取数据路径")
            return False
        data_path = data_path.replace("/", "\\")
        sw_path = sw_path.replace("/", "\\")
        handle_exe_path = Config.HANDLE_EXE_PATH.replace("/", "\\")
        # 头像
        avatar_path = os.path.join(Config.PROJ_USER_PATH, sw, f"{acc}", f"{acc}.jpg")
        if not os.path.exists(avatar_path):
            avatar_path = os.path.join(Config.PROJ_USER_PATH, "default.jpg")

        # 互斥体名称列表
        mutex_names = []
        mutant_handle_infos, = subfunc_file.get_remote_cfg(sw, mutant_handle_infos=[])
        for handle_regex_dict in mutant_handle_infos:
            print(handle_regex_dict)
            mutex_name = handle_regex_dict.get("handle_name")
            mutex_names.append(mutex_name)
        print(f"互斥体名称列表：{mutex_names}")

        replace_cfg_cmd = AccOperator._generate_replace_cfg_cmds(sw, acc, data_path)
        operate_list = []
        operate_list.extend(AccOperator._generate_start_cmds_if_freely_multirun(sw_path))
        operate_list.extend(AccOperator._generate_start_cmds_for_handle(
            handle_exe_path, sw_path, mutex_names))
        operate_list.extend(AccOperator._generate_start_cmds_for_other(sw))

        for exe_path, prefix, close_handle_cmds_str, start_vbs_str in operate_list:
            # 管理员运行部分:替换+关闭句柄
            admin_bat_str = f"{replace_cfg_cmd}\n{close_handle_cmds_str}"
            # 普通运行部分：启动
            normal_vbs_str = f"{start_vbs_str}"
            AccOperator._create_bat_icon_lnk(sw, acc, exe_path, avatar_path, prefix, admin_bat_str, normal_vbs_str)
        return None

    @staticmethod
    def create_starter_lnk_for_accounts(sw_accounts_dict):
        err_dict = {}
        for sw, accounts in sw_accounts_dict.items():
            for acc in accounts:
                try:
                    AccOperator._create_starter_lnk_for_acc(sw, acc)
                except Exception as e:
                    err_dict[f"{sw / acc}"] = e
        success = len(err_dict) == 0
        return success, err_dict

    @staticmethod
    def kill_mutex_of_pid(sw, acc):
        """关闭指定进程的所有互斥体"""
        pid, = subfunc_file.get_sw_acc_data(sw, acc, pid=None)
        if pid is None:
            return False
        handle_regex_list, = subfunc_file.get_remote_cfg(sw, mutant_handle_infos=None)
        if handle_regex_list is None:
            return True
        handle_names = [handle["handle_name"] for handle in handle_regex_list]
        if handle_names is None or len(handle_names) == 0:
            return True
        success = handle_utils.pywinhandle_close_handles(
            handle_utils.pywinhandle_find_handles_by_pids_and_handle_names(
                [pid],
                handle_names
            )
        )
        print(f"kill mutex: {success}")
        if success:
            subfunc_file.update_sw_acc_data(sw, acc, has_mutex=False)
        return success


class AccInfoFunc:
    """
    账号信息
    常用变量：
        sw: 选择的软件标签
        acc: 账号标识
    """

    @staticmethod
    def _use_default_avatar_or_white_bg():
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
            return None
        except IOError as e:
            print("图像文件读取失败:", e)
            return None
        except Exception as e:
            print("所有方法都失败，创建空白头像:", e)
            return Image.new('RGB', Constants.AVT_SIZE, color='white')

    @staticmethod
    def _generate_text_avatar(display_name):
        # 计算最多4单位长度的末尾子串（中文占2，英文占1）
        units = []
        total = 0
        for char in reversed(display_name):
            char_width = 2 if re.match(r'[\u4e00-\u9fff]', char) else 1
            if total + char_width > 4:
                break
            units.append(char)
            total += char_width
        text = ''.join(reversed(units))

        # 创建头像图像（背景颜色可以自定义）
        def _random_dark_color():
            return tuple(random.randint(75, 125) for _ in range(3))

        dark_color = _random_dark_color()
        img = Image.new("RGB", Constants.AVT_SIZE, color=dark_color)  # type: ignore
        draw = ImageDraw.Draw(img)

        # 加载字体（使用系统字体，必要时可指定路径）
        try:
            font = ImageFont.truetype("msyh.ttc", 16)
        except IOError:
            font = ImageFont.load_default()

        # 计算文本位置使其居中
        text_size = draw.textbbox((0, 0), text, font=font)
        text_width = text_size[2] - text_size[0]
        text_height = text_size[3] - text_size[1]
        position = ((Constants.AVT_SIZE[0] - text_width) // 2, (Constants.AVT_SIZE[1] - text_height) // 2.2)

        # 绘制文本
        draw.text(position, text, fill="white", font=font)
        return img

    @staticmethod
    def manual_choose_avatar_for_acc(sw, acc):
        file_path = filedialog.askopenfilename(
            title="选择头像图片",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif")]
        )
        if not file_path:
            return

        with Image.open(file_path) as img:
            width, height = img.size
            side = min(width, height)
            left = (width - side) // 2
            top = (height - side) // 2
            cropped = img.crop((left, top, left + side, top + side))
            dir_path = os.path.join(Config.PROJ_USER_PATH, sw, f"{acc}")
            file_path = os.path.join(dir_path, f"{acc}.jpg")
            # 确保目录存在
            os.makedirs(dir_path, exist_ok=True)
            cropped.save(file_path, format=img.format)

    @staticmethod
    def delete_avatar_for_acc(sw, acc):
        path = os.path.join(Config.PROJ_USER_PATH, sw, f"{acc}", f"{acc}.jpg")
        if os.path.exists(path):
            os.remove(path)
        subfunc_file.update_sw_acc_data(sw, acc, avatar_url=None)

    @staticmethod
    def get_acc_avatar_from_files(sw, acc):
        """
        从本地缓存或json文件中的url地址获取头像，失败则默认头像
        """
        disable_avatar, = subfunc_file.get_sw_acc_data(sw, acc, disable_avatar=None)
        if disable_avatar is True:
            return AccInfoFunc._get_acc_avatar_without_files(sw, acc)

        # 构建头像文件路径
        avatar_path = os.path.join(Config.PROJ_USER_PATH, sw, f"{acc}", f"{acc}.jpg")

        # 检查是否存在对应account的头像
        if os.path.exists(avatar_path):
            return Image.open(avatar_path)
        # 如果没有，从网络下载
        url, = subfunc_file.get_sw_acc_data(sw, acc, avatar_url=None)
        if url is not None and url.endswith("/0"):
            image_utils.download_image(url, avatar_path)

        # 第二次检查是否存在对应account的头像
        if os.path.exists(avatar_path):
            return Image.open(avatar_path)

        return AccInfoFunc._get_acc_avatar_without_files(sw, acc)

    @staticmethod
    def _get_acc_avatar_without_files(sw, acc):
        # 处理没有本地头像的情况
        use_text_avatar = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.USE_TXT_AVT)
        if use_text_avatar:
            return AccInfoFunc._generate_text_avatar(AccInfoFunc.get_acc_origin_display_name(sw, acc))
        else:
            return AccInfoFunc._use_default_avatar_or_white_bg()

    @staticmethod
    def get_acc_origin_display_name(sw, acc) -> str:
        """获取账号的展示名"""
        # 依次查找 note, nickname, alias，找到第一个不为 None 的值
        display_name = str(acc)  # 默认值为 account
        for key in ("note", "nickname", "alias"):
            value, = subfunc_file.get_sw_acc_data(sw, acc, **{key: None})
            if value is not None:
                display_name = str(value)
                break
        return display_name

    @staticmethod
    def get_sw_acc_login_cfg(sw, account, data_path) -> str:
        """
        通过账号的配置状态
        :param sw: 选择的软件标签
        :param data_path: 数据存储路径
        :param account: 账号
        :return: 配置状态
        """
        if not data_path:
            return "无配置路径"
        config_path_suffix, cfg_basename_list = subfunc_file.get_remote_cfg(
            sw, config_path_suffix=None, config_file_list=None)
        if not isinstance(cfg_basename_list, list) or len(cfg_basename_list) == 0:
            return "无法获取配置路径"
        # 版本更新,数据文件重命名
        for cfg_basename in cfg_basename_list:
            # 旧版
            file_suffix = cfg_basename.split(".")[-1]
            old_cfg_basename = f"{account}.{file_suffix}"
            old_acc_cfg_path = (os.path.join(str(data_path), str(config_path_suffix), old_cfg_basename)
                                .replace("\\", "/"))
            # 新版
            cfg_basename = f"{account}_{cfg_basename}"
            acc_cfg_path = (os.path.join(str(data_path), str(config_path_suffix), cfg_basename)
                            .replace("\\", "/"))
            # 如果无新版配置但存在旧版配置，复制为新版
            if os.path.exists(old_acc_cfg_path) and not os.path.exists(acc_cfg_path):
                shutil.copy2(old_acc_cfg_path, acc_cfg_path)
                print(f"复制旧版配置文件：{old_acc_cfg_path} -> {acc_cfg_path}")

        cfg_basename = cfg_basename_list[0]
        cfg_basename = f"{account}_{cfg_basename}"
        acc_cfg_path = (os.path.join(str(data_path), str(config_path_suffix), cfg_basename)
                        .replace("\\", "/"))
        if os.path.exists(acc_cfg_path):
            mod_time = os.path.getmtime(acc_cfg_path)
            date = datetime.datetime.fromtimestamp(mod_time)
            return f"{date.year % 100:02}/{date.month:02}/{date.day:02} {date.hour:02}:{date.minute:02}"
        else:
            return CfgStatus.NO_CFG.value

    @staticmethod
    def get_acc_wrapped_display_name(sw, account) -> str:
        """获取账号的折叠展示名"""
        return StringUtils.balanced_wrap_text(
            AccInfoFunc.get_acc_origin_display_name(sw, account),
            18
        )

    @staticmethod
    def _get_avatar_from_other_sw(now_sw, now_acc_list):
        # 获取从其他平台到当前平台的裁剪映射
        changed = False
        sw_id_trims, = subfunc_file.get_remote_cfg(now_sw, sw_id_trims=None)
        for other_sw, trim_values in (sw_id_trims or {}).items():
            if not isinstance(trim_values, list) or len(trim_values) != 4:
                logger.warning(f"无效的 sw_id_trims 配置: {other_sw} -> {trim_values}")
                continue
            other_l, other_r, now_l, now_r = trim_values
            other_r = None if other_r == 0 else -other_r
            now_r = None if now_r == 0 else -now_r

            # 加载其他平台的账号列表
            other_acc_list = subfunc_file.get_sw_acc_data(other_sw)
            # 预处理：构建一个 dict，key 是裁切后的 other_acc，value 是原账号
            other_cut_map = {
                other_acc[other_l:other_r]: other_acc
                for other_acc in other_acc_list
            }

            for now_acc in now_acc_list:
                now_cut_acc = now_acc[now_l:now_r]
                other_acc = other_cut_map.get(now_cut_acc)
                if other_acc:
                    # 检查头像url是否存在,若不在,则偷取
                    now_avatar_url, = subfunc_file.get_sw_acc_data(now_sw, now_acc, avatar_url=None)
                    other_avatar_url, = subfunc_file.get_sw_acc_data(other_sw, other_acc, avatar_url=None)
                    if other_avatar_url and not now_avatar_url:
                        logger.info(f"{now_acc}: {other_avatar_url}")
                        subfunc_file.update_sw_acc_data(now_sw, now_acc, avatar_url=other_avatar_url)
                        changed = True
                    # 检查头像文件是否存在,若不在,先从url下载,若下载失败,则从其他平台偷取本地图片
                    now_avatar_path = os.path.join(Config.PROJ_USER_PATH, now_sw, f"{now_acc}", f"{now_acc}.jpg")
                    now_avatar_url, = subfunc_file.get_sw_acc_data(now_sw, now_acc, avatar_url=None)
                    if not os.path.isfile(now_avatar_path):
                        if now_avatar_url is not None:
                            success = image_utils.download_image(now_avatar_url, now_avatar_path)
                            if success is True:
                                return True
                        other_avatar_path = os.path.join(Config.PROJ_USER_PATH, other_sw, f"{other_acc}",
                                                         f"{other_acc}.jpg")
                        if os.path.isfile(other_avatar_path) and not os.path.isfile(now_avatar_path):
                            os.makedirs(os.path.dirname(now_avatar_path), exist_ok=True)
                            shutil.copyfile(other_avatar_path, now_avatar_path)
                            return True
        return changed

    @staticmethod
    def _get_nickname_from_other_sw(now_sw, now_acc_list):
        # 获取从其他平台到当前平台的裁剪映射
        changed = False
        sw_id_trims, = subfunc_file.get_remote_cfg(now_sw, sw_id_trims=None)
        for other_sw, trim_values in (sw_id_trims or {}).items():
            if not isinstance(trim_values, list) or len(trim_values) != 4:
                logger.warning(f"无效的 sw_id_trims 配置: {other_sw} -> {trim_values}")
                continue
            other_l, other_r, now_l, now_r = trim_values
            other_r = None if other_r == 0 else -other_r
            now_r = None if now_r == 0 else -now_r

            # 加载其他平台的账号列表
            other_acc_list = subfunc_file.get_sw_acc_data(other_sw)
            # 预处理：构建一个 dict，key 是裁切后的 other_acc，value 是原账号
            other_cut_map = {
                other_acc[other_l:other_r]: other_acc
                for other_acc in other_acc_list
            }

            for now_acc in now_acc_list:
                now_cut_acc = now_acc[now_l:now_r]
                other_acc = other_cut_map.get(now_cut_acc)
                if other_acc:
                    # 检查头像url是否存在,若不在,则偷取
                    now_nickname, = subfunc_file.get_sw_acc_data(now_sw, now_acc, nickname=None)
                    other_nickname, = subfunc_file.get_sw_acc_data(other_sw, other_acc, nickname=None)
                    if other_nickname and not now_nickname:
                        logger.info(f"{now_acc}: {other_nickname}")
                        subfunc_file.update_sw_acc_data(now_sw, now_acc, nickname=other_nickname)
                        changed = True
        return changed

    @staticmethod
    def silent_get_and_config(sw):
        """后台静默获取账号配置"""
        root_class = GlobalMembers.root_class
        login_ui = root_class.login_ui
        root = root_class.root
        data_dir = root_class.sw_classes[sw].data_dir

        # 线程执行检测昵称和头像
        need_to_notice = []

        # 1. 获取所有账号节点的url和昵称，将空的账号返回
        accounts_need_to_get_avatar = []
        accounts_need_to_get_nickname = []
        sw_data = subfunc_file.get_sw_acc_data(sw)
        # print(login, logout)
        for acc in sw_data:
            if acc == AccKeys.PID_MUTEX:
                continue
            avatar_url, nickname = subfunc_file.get_sw_acc_data(sw, acc, avatar_url=None, nickname=None)
            if avatar_url is None:
                accounts_need_to_get_avatar.append(acc)
            if nickname is None:
                accounts_need_to_get_nickname.append(acc)
        # print(accounts_need_to_get_avatar, accounts_need_to_get_nickname)
        # 2. 对待获取url的账号遍历尝试获取
        if len(accounts_need_to_get_avatar) > 0:
            need_to_notice.append(
                FuncTool.get_sw_acc_func_impl(AccInfoFuncImpl, sw).get_avatar_url_from_file(
                    sw, accounts_need_to_get_avatar, data_dir))
            need_to_notice.append(AccInfoFunc._get_avatar_from_other_sw(sw, accounts_need_to_get_avatar))
        # 3. 对待获取昵称的账号尝试遍历获取
        if len(accounts_need_to_get_nickname) > 0:
            need_to_notice.append(
                FuncTool.get_sw_acc_func_impl(AccInfoFuncImpl, sw).get_nickname_from_file(
                    sw, accounts_need_to_get_nickname, data_dir))
            need_to_notice.append(AccInfoFunc._get_nickname_from_other_sw(sw, accounts_need_to_get_nickname))
        # 4. 偷偷创建配置文件
        curr_config_acc = AccInfoFunc.get_curr_wx_id_from_config_file(sw, data_dir)
        if curr_config_acc is not None:
            if AccInfoFunc.get_sw_acc_login_cfg(sw, curr_config_acc, data_dir) == CfgStatus.NO_CFG.value:
                changed, _ = AccOperator.operate_acc_config('add', sw, curr_config_acc)
                need_to_notice.append(changed)
        # 5. 通知
        if any(need_to_notice):
            messagebox.showinfo("提醒", "已自动化获取或配置！即将刷新！")
            root.after(0, login_ui.refresh_frame, sw)

    @staticmethod
    def get_curr_wx_id_from_config_file(sw, data_dir):
        # Printer().debug(FuncTool.get_sw_acc_func_impl(AccInfoFuncImpl, sw))
        return FuncTool.get_sw_acc_func_impl(AccInfoFuncImpl, sw).get_curr_wx_id_from_config_file(sw, data_dir)

    @staticmethod
    def is_acc_coexist(sw, acc):
        acc_dict = subfunc_file.get_sw_acc_data(sw, acc)
        if not isinstance(acc_dict, dict) or "linked_acc" not in acc_dict:
            return False
        return True

    @staticmethod
    def get_real_acc(sw, acc):
        acc_dict = subfunc_file.get_sw_acc_data(sw, acc)
        if not isinstance(acc_dict, dict):
            return acc
        if "linked_acc" in acc_dict:
            return acc_dict["linked_acc"] if acc_dict["linked_acc"] is not None else acc
        return acc

    @staticmethod
    def _update_acc_list_by_pid(pid: int, data_dir, pid_acc_dict, exclude_folders):
        """为存在的进程匹配出对应的账号，并更新[已登录账号]和[(已登录进程,账号)]"""

        def identify_by_file(file):
            # print(process_id, f)
            # 将路径中的反斜杠替换为正斜杠
            normalized_path = file.path.replace('\\', '/')
            # print(normalized_path)
            # 检查路径是否以 data_path 开头
            if normalized_path.startswith(data_dir):
                # print(
                #     f"┌———匹配到进程{process_id}使用的符合的文件，待比对，已用时：{time.time() - start_time:.4f}秒")
                # print(f"提取中：{f.path}")
                path_parts = file.path.split(os.path.sep)
                try:
                    acc_dir_index = path_parts.index(os.path.basename(data_dir)) + 1
                    acc_dir = path_parts[acc_dir_index]
                    if acc_dir not in exclude_folders:
                        pid_acc_dict[pid] = acc_dir
                        # print(f"进程{process_id}对应账号{acc_dir}，已用时：{time.time() - start_time:.4f}秒")
                        return True
                    return None
                except Exception as e:
                    logger.error(e)
                    return None
            return None

        try:
            for f in psutil.Process(pid).memory_maps():
                success = identify_by_file(f)
                if success:
                    return
            for f in psutil.Process(pid).open_files():
                success = identify_by_file(f)
                if success:
                    return

        except psutil.AccessDenied:
            logger.error(f"无法访问进程ID为 {pid} 的内存映射文件，权限不足。")
        except psutil.NoSuchProcess:
            logger.error(f"进程ID为 {pid} 的进程不存在或已退出。")
        except Exception as e:
            logger.error(f"发生意外错误: {e}")

    @staticmethod
    def _link_acc_to_coexist_exe(sw, pid_acc_dict, executable_wildcards):
        # 共存程序,将账号id赋给共存字典,将共存id赋给账号id
        origin_exe, = subfunc_file.get_remote_cfg(sw, executable=None)
        if origin_exe is None:
            raise Exception("无法区分共存程序")
        for pid, acc in pid_acc_dict.items():
            pid_exe = process_utils.get_exe_name_by_pid(pid)
            for wildcard in executable_wildcards:
                if fnmatch(pid_exe, wildcard) and pid_exe != origin_exe:
                    # 只筛选出共存但不是原生程序的
                    subfunc_file.update_sw_acc_data(sw, pid_exe, linked_acc=acc)
                    pid_acc_dict[pid] = pid_exe
                    break

    @staticmethod
    def _get_all_coexist_acc_and_let_dist_exists(sw, inst_dir, executable_wildcards):
        """获取所有的共存程序,并在字典中确保存在对应的账号节点和 linked_acc 属性"""
        # 处理共存版账号,创建字典和节点
        all_exes = file_utils.get_file_names_matching_wildcards(executable_wildcards, inst_dir)
        origin_exe, = subfunc_file.get_remote_cfg(sw, executable=None)
        all_coexist_exes = []
        for coexist_exe in all_exes:
            if coexist_exe == origin_exe:
                continue
            all_coexist_exes.append(coexist_exe)
            coexist_exe_dict = subfunc_file.get_sw_acc_data(sw, coexist_exe)
            if not isinstance(coexist_exe_dict, dict):
                subfunc_file.update_sw_acc_data(sw, **{coexist_exe: {}})
            coexist_exe_dict = subfunc_file.get_sw_acc_data(sw, coexist_exe)
            if "linked_acc" not in coexist_exe_dict:
                subfunc_file.update_sw_acc_data(sw, coexist_exe, linked_acc=None)
        return all_coexist_exes

    @staticmethod
    def get_sw_acc_list(_root, root_class, sw):
        """
        获取账号及其登录情况
        :param _root: 主窗口
        :param root_class: 主窗口类
        :param sw: 平台
        :return: Union[Tuple[True, Tuple[账号字典，进程字典，有无互斥体]], Tuple[False, 错误信息]]
        """
        sw_class = root_class.sw_classes[sw]
        data_dir = sw_class.data_dir
        inst_path = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.INST_PATH)
        inst_dir = os.path.dirname(inst_path)
        if data_dir is None or os.path.isdir(data_dir) is False:
            return False, "数据路径不存在"
        origin_exe, excluded_dirs, executable_wildcards, origin_login_wnd_class = subfunc_file.get_remote_cfg(
            sw,
            executable=None,
            excluded_dir_list=None,
            executable_wildcards=None,
            login_wnd_class=None,
        )
        if not isinstance(executable_wildcards, list):
            messagebox.showerror("错误", f"{sw}平台未适配")
            return False, "该平台未适配"

        start_time = time.time()
        pid_acc_dict = {}

        # 获取在线进程及对应的账号字典 pid_acc_dict --------------------------------------------
        pids = SwInfoFunc.get_sw_all_exe_pids(sw)
        print(f"读取到{sw}所有进程，用时：{time.time() - start_time:.4f} 秒")
        Printer().debug(pids)
        if isinstance(pids, Iterable):
            for pid in pids:
                AccInfoFunc._update_acc_list_by_pid(pid, data_dir, pid_acc_dict, excluded_dirs)
        Printer().debug(pid_acc_dict)
        # 对 pid_acc_dict 字典中的账号匹配共存程序 --------------------------------------------
        AccInfoFunc._link_acc_to_coexist_exe(sw, pid_acc_dict, executable_wildcards)
        Printer().debug(pid_acc_dict)
        # 得到所有账号列表,并存入结果集 --------------------------------------------
        acc_dirs_set = set(
            item for item in os.listdir(data_dir)
            if os.path.isdir(os.path.join(data_dir, item))
        ) - set(excluded_dirs)
        if executable_wildcards is not None:
            # 处理共存版账号,确保创建字典和节点
            all_coexist_exes = AccInfoFunc._get_all_coexist_acc_and_let_dist_exists(sw, inst_dir, executable_wildcards)
            Printer().debug(all_coexist_exes)
            acc_dirs_set.update(all_coexist_exes)
        all_acc_list = list(acc_dirs_set)
        logins_set = set(pid_acc_dict.values())
        logins = list(logins_set & acc_dirs_set)
        logouts = list(acc_dirs_set - logins_set)
        acc_list_dict = {"login": logins, "logout": logouts}
        Printer().debug(acc_list_dict)
        # 反转字典,更新账号数据 --------------------------------------------
        acc_pid_dict = dict()
        for k, v in pid_acc_dict.items():
            acc_pid_dict[v] = k
        Printer().debug(acc_pid_dict)
        # 先从pid_mutex加载回互斥体情况,再更新
        _, has_mutex = subfunc_file.update_has_mutex_from_pid_mutex(sw)
        multirun_mode = sw_class.multirun_mode
        for acc in all_acc_list:
            pid = acc_pid_dict.get(acc, None)
            if pid is None:
                subfunc_file.update_sw_acc_data(sw, acc, pid=None, has_mutex=False)
            else:
                subfunc_file.update_sw_acc_data(sw, acc, pid=pid)
                if multirun_mode == MultirunMode.FREELY_MULTIRUN:
                    subfunc_file.update_sw_acc_data(sw, acc, has_mutex=False)
        # 对账号添加窗口类名属性
        for acc in all_acc_list:
            login_wnd_class, = subfunc_file.get_sw_acc_data(sw, acc, login_wnd_class=None)
            if login_wnd_class is None:
                subfunc_file.update_sw_acc_data(sw, acc, login_wnd_class=origin_login_wnd_class)
        return True, (acc_list_dict, has_mutex)

    @staticmethod
    def get_main_hwnd_of_accounts(sw, acc_list):
        # Printer().debug(sw, acc_list)
        main_wildcards, = subfunc_file.get_remote_cfg(
            sw, main_wnd_class_wildcards=None)
        if main_wildcards is None:
            messagebox.showerror("错误", f"{sw}平台未适配")
            return False
        for acc in acc_list:
            correct_hwnd = None
            pid, = subfunc_file.get_sw_acc_data(sw, acc, pid=None)
            hwnd_list = hwnd_utils.uiautomation_get_hwnds_by_pid_and_class_wildcards(pid, main_wildcards)
            Printer().debug(pid, hwnd_list)
            if len(hwnd_list) == 0:
                continue
            if len(hwnd_list) == 1:
                correct_hwnd = hwnd_list[0]
            for hwnd in hwnd_list:
                if AccInfoFunc.is_hwnd_a_main_wnd_of_acc_on_sw(hwnd, sw, acc):
                    correct_hwnd = hwnd
                    break
            if correct_hwnd is not None:
                subfunc_file.update_sw_acc_data(sw, acc, main_hwnd=correct_hwnd)
                display_name = AccInfoFunc.get_acc_origin_display_name(sw, acc)
                sw_display_name = SwInfoFunc.get_sw_origin_display_name(sw)
                hwnd_utils.set_window_title(correct_hwnd, f"{sw_display_name} - {display_name}")
                Printer().debug(acc, correct_hwnd)
                return None
            return None
        return None

    @staticmethod
    def is_hwnd_a_main_wnd_of_acc_on_sw(hwnd, sw, acc):
        """检测窗口是否是某个账号的主窗口"""
        # hwnd_utils.restore_window(hwnd)
        Printer().debug(hwnd, sw, acc)
        acc_dict: dict = subfunc_file.get_sw_acc_data(sw, acc)
        if "linked_acc" in acc_dict:
            acc = acc_dict["linked_acc"]
        pid, = subfunc_file.get_sw_acc_data(sw, acc, pid=None)
        if pid is None:
            return False
        # 判断hwnd是否属于指定的pid
        if hwnd_utils.get_hwnd_details_of_(hwnd)["pid"] != pid:
            return False
        expected_classes, = subfunc_file.get_remote_cfg(sw, main_wnd_class_wildcards=None)
        class_name = win32gui.GetClassName(hwnd)
        for expected_class in expected_classes:
            if fnmatch(class_name, expected_class):
                return True
            continue
        return False

    @staticmethod
    def unlink_hwnd_of_account(sw, account):
        """
        解除账号与hwnd的绑定
        :param sw: 软件标签
        :param account: 账号列表
        :return:
        """
        subfunc_file.update_sw_acc_data(sw, account, main_hwnd=None)
        messagebox.showinfo("成功", "已解绑，账号列表刷新将尝试重新绑定！")

    @staticmethod
    def relink_hwnd_of_account(sw, account):
        AccInfoFunc.get_main_hwnd_of_accounts(sw, [account])
        messagebox.showinfo("成功", "已重新绑定！")

    @staticmethod
    def manual_link_hwnd_of_account(sw, account):
        # 一个确定和取消的提示框
        if messagebox.askyesno("提示", "请先手动将平台对应窗口置于前台，是否完成？"):
            # 将桌面中可见的窗口从顶部到底部遍历
            hwnds = hwnd_utils.get_visible_windows_sorted_by_top()
            for hwnd in hwnds:
                print(hwnd_utils.get_hwnd_details_of_(hwnd)["class"])
                if AccInfoFunc.is_hwnd_a_main_wnd_of_acc_on_sw(hwnd, sw, account):
                    subfunc_file.update_sw_acc_data(sw, account, main_hwnd=hwnd)
                    sw_display_name = SwInfoFunc.get_sw_origin_display_name(sw)
                    display_name = AccInfoFunc.get_acc_origin_display_name(sw, account)
                    hwnd_utils.set_window_title(hwnd, f"{sw_display_name} - {display_name}")
                    break
