import base64
import datetime
import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from collections.abc import Iterable
from tkinter import messagebox
from typing import Dict, List

import psutil
import win32con
import win32gui
import winshell
from PIL import Image

from functions import subfunc_file
from functions.sw_func import SwOperator, SwInfoFunc
from public_class.enums import AccKeys, SW, LocalCfg
from public_class.global_members import GlobalMembers
from resources import Constants
from resources.config import Config
from resources.strings import Strings
from utils import process_utils, image_utils, hwnd_utils, handle_utils
from utils.encoding_utils import StringUtils
from utils.logger_utils import mylogger as logger


class AccOperator:
    @staticmethod
    def _auto_login_accounts(login_dict: Dict[str, List]):
        """
        对选择的账号，进行全自动登录
        :param login_dict: 登录列表字典
        :return: 是否成功
        """
        root_class = GlobalMembers.root_class
        root = root_class.root
        acc_tab_ui = root_class.acc_tab_ui

        # print(login_dict)

        # 统计一下数目
        acc_cnt = 0
        for sw, acc_list in login_dict.items():
            if isinstance(acc_list, list):
                acc_cnt += len(acc_list)
        # print(acc_cnt)

        # 检查要登录的账号数量
        if acc_cnt is None or acc_cnt == 0:
            return False
        # 优先自动获取尺寸，若获取不到从配置中获取
        screen_width = int(tk.Tk().winfo_screenwidth())
        screen_height = int(tk.Tk().winfo_screenheight())
        if not screen_height or not screen_width:
            size = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.SCREEN_SIZE).split('*')
            screen_width, screen_height = int(size[0]), int(size[1])
        if not screen_width or screen_width == "":
            messagebox.showinfo("提醒", "缺少登录窗口尺寸配置，请到应用设置中添加！")
            return False
        # 检查是否有登录窗口大小配置
        max_login_size = AccOperator._get_max_dimensions_from_sw_list(list(login_dict.keys()))
        if not max_login_size or max_login_size is None:
            messagebox.showinfo("提醒", "缺少登录窗口尺寸配置，请到应用设置中添加！")
            return False

        # 计算登录窗口的位置
        acc_positions = hwnd_utils.layout_wnd_positions(acc_cnt, max_login_size, (screen_width, screen_height))

        # 开始登录过程
        acc_turn = 0
        for sw, accounts in login_dict.items():
            print(f"进行{sw}平台的登录")
            if not isinstance(accounts, list) or len(accounts) == 0:
                continue

            # 初始化操作：清空闲置的登录窗口、多开器，清空并拉取各账户的登录和互斥体情况
            redundant_wnd_list, login_wnd_class, executable_name, cfg_handles = (
                subfunc_file.get_remote_cfg(
                    sw, redundant_wnd_class=None, login_wnd_class=None, executable=None, cfg_handle_regex_list=None))
            SwOperator.close_classes_but_sw_main_wnd(redundant_wnd_list, sw)
            SwOperator.kill_sw_multiple_processes(sw)
            time.sleep(0.5)
            subfunc_file.clear_some_acc_data(sw, AccKeys.PID_MUTEX)
            subfunc_file.update_all_acc_in_acc_json(sw)

            multirun_mode = root_class.sw_classes[sw].multirun_mode

            # 开始遍历登录账号过程
            start_time = time.time()
            # 使用一个set存储不重复的handle
            wechat_handles = set()
            for j in range(len(login_dict[sw])):
                # 关闭配置文件锁
                handle_utils.close_sw_mutex_by_handle(
                    Config.HANDLE_EXE_PATH, executable_name, cfg_handles)

                # 读取配置
                success, _ = AccOperator.operate_acc_config('use', sw, accounts[j])
                if success:
                    print(f"{accounts[j]}:复制配置文件成功")
                else:
                    print(f"{accounts[j]}:复制配置文件失败")
                    break

                # 打开微信
                sub_exe_process = SwOperator.open_sw(sw, multirun_mode)

                # 等待打开窗口
                end_time = time.time() + 20
                while True:
                    wechat_hwnd = hwnd_utils.wait_open_to_get_hwnd(login_wnd_class, 1)
                    if wechat_hwnd is not None and wechat_hwnd not in wechat_handles:
                        # 确保打开了新的微信登录窗口
                        wechat_handles.add(wechat_hwnd)
                        if sub_exe_process:
                            # print(f"进程{sub_exe_process}")
                            # print(isinstance(sub_exe_process, process_utils.Process))
                            # print(sub_exe_process.h_process, sub_exe_process.h_thread)
                            sub_exe_process.terminate()
                        print(f"打开窗口成功：{wechat_hwnd}")
                        subfunc_file.set_all_acc_values_to_false(sw)
                        subfunc_file.update_has_mutex_from_all_acc(sw)
                        break
                    if time.time() > end_time:
                        print(f"超时！此号打开窗口失败！")
                        wechat_hwnd = None
                        break

                if wechat_hwnd is None:
                    # 跳过这个账号
                    continue

                # 安排窗口位置
                # 横坐标算出完美的平均位置
                new_left, new_top = acc_positions[acc_turn]

                # 只调整窗口的位置，不改变大小
                try:
                    win32gui.SetWindowPos(
                        wechat_hwnd,
                        win32con.HWND_TOP,
                        new_left,
                        new_top,
                        0,  # 宽度设置为 0 表示不改变
                        0,  # 高度设置为 0 表示不改变
                        win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
                    )
                except Exception as e:
                    logger.error(e)

                # 逐次统计时间
                subfunc_file.update_statistic_data(sw, 'auto', str(j + 1), multirun_mode, time.time() - start_time)

                acc_turn += 1

            # 统计平均时间
            subfunc_file.update_statistic_data(sw, 'auto', 'avg', multirun_mode,
                                               (time.time() - start_time) / acc_cnt)

            # 循环登录完成
            # 如果有，关掉多余的多开器
            SwOperator.kill_sw_multiple_processes(sw)

            # 定义点击按钮并等待成功的线程，启动线程
            def click_all_login_button():
                # 判断是否需要自动点击按钮
                auto_press = root_class.global_settings_value.auto_press
                if auto_press:
                    # 两轮点击所有窗口的登录，防止遗漏
                    hwnd_list = hwnd_utils.get_hwnd_list_by_class_and_title(login_wnd_class)
                    time.sleep(0.5)
                    inner_start_time = time.time()
                    for i in range(1):
                        for h in hwnd_list:
                            hwnd_details = hwnd_utils.get_hwnd_details_of_(h)
                            cx = int(hwnd_details["width"] * 0.5)
                            cy = int(hwnd_details["height"] * 0.75)
                            hwnd_utils.do_click_in_wnd(h, cx, cy)
                            time.sleep(0.2)
                        print(f"通过位置查找，用时：{time.time() - inner_start_time:.4f}s")

                    inner_start_time = time.time()
                    for h in hwnd_list:
                        titles = ["进入微信", "进入WeChat", "Enter Weixin", "进入微信"]  # 添加所有需要查找的标题
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
                    hs = hwnd_utils.get_hwnd_list_by_class_and_title(login_wnd_class)
                    # print("等待登录完成")
                    if len(hs) == 0:
                        break
                    if time.time() > ddl_time:
                        break
                root.after(0, acc_tab_ui.refresh_frame, sw)

            threading.Thread(target=click_all_login_button).start()

    @staticmethod
    def _get_max_dimensions_from_sw_list(sw_list):
        """
        遍历 sw 列表，返回宽度最大的尺寸（宽度和高度），如果所有 sw 都没有有效的尺寸配置，返回 False。

        :param sw_list: 列表，每个元素代表一个 sw 对象
        :return: (最大宽度, 对应高度) 或 False（如果所有 sw 都没有有效尺寸配置）
        """
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
    def thread_to_auto_login_accounts(login_dict: Dict[str, List]):
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
        data_path = SwInfoFunc.get_sw_data_dir(sw)
        if not data_path:
            return False, "无法获取WeChat数据路径"
        config_path_suffix, cfg_items = subfunc_file.get_remote_cfg(
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
        acc_tab_ui = root_class.acc_tab_ui

        if messagebox.askyesno(
                "确认",
                "建议在只登录了一个账号时，或刚刚登录了此账号时进行配置，\n成功率更高。将唤起登录窗口，请勿重复登录。是否继续？"
        ):
            redundant_wnd_classes, executable_name, cfg_handles = subfunc_file.get_remote_cfg(
                sw, redundant_wnd_class=None, executable=None, cfg_handle_regex_list=None)
            SwOperator.close_classes_but_sw_main_wnd(redundant_wnd_classes, sw)
            handle_utils.close_sw_mutex_by_handle(
                Config.HANDLE_EXE_PATH, executable_name, cfg_handles)
            SwOperator.kill_sw_multiple_processes(sw)
            time.sleep(0.5)
            sub_exe_process = SwOperator.open_sw(sw, multirun_mode)
            login_wnd_class, = subfunc_file.get_remote_cfg(sw, login_wnd_class=None)
            wechat_hwnd = hwnd_utils.wait_open_to_get_hwnd(login_wnd_class, timeout=8)
            print(wechat_hwnd)
            if wechat_hwnd:
                if sub_exe_process:
                    sub_exe_process.terminate()
                time.sleep(1)
                hwnd_utils.bring_hwnd_next_to_left_of_hwnd2(wechat_hwnd, root.winfo_id())
                if messagebox.askyesno("确认", "是否为对应的微信号？"):
                    success, result = AccOperator.operate_acc_config('add', sw, account)
                    if success is True:
                        created_list_text = "\n".join(result)
                        messagebox.showinfo("成功", f"已生成：\n{created_list_text}")
                hwnd_utils.close_by_wnd_class(login_wnd_class)
            else:
                messagebox.showerror("错误", "打开登录窗口失败")
        root.after(0, acc_tab_ui.refresh_frame, sw)

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
            try:
                pid, = subfunc_file.get_sw_acc_data(sw, account, pid=None)
                display_name = AccInfoFunc.get_acc_origin_display_name(sw, account)
                cleaned_display_name = StringUtils.clean_texts(display_name)
                executable_name, = subfunc_file.get_remote_cfg(sw, executable=None)
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

    @staticmethod
    def create_lnk_for_account(sw, account, multiple_status):
        """
        为账号创建快捷开启
        :param sw: 选择的软件标签
        :param account: 账号
        :param multiple_status: 是否多开状态
        :return: 是否成功
        """
        # 确保可以创建快捷启动
        data_path = SwInfoFunc.get_sw_data_dir(sw)
        wechat_path = SwInfoFunc.get_sw_install_path(sw)
        if not data_path or not wechat_path:
            messagebox.showerror("错误", "无法获取数据路径")
            return False
        avatar_path = os.path.join(Config.PROJ_USER_PATH, sw, f"{account}", f"{account}.jpg")
        if not os.path.exists(avatar_path):
            avatar_path = os.path.join(Config.PROJ_USER_PATH, "default.jpg")

        # 构建源文件和目标文件路径
        source_file = os.path.join(data_path, "All Users", "config", f"{account}.data").replace('/', '\\')
        target_file = os.path.join(data_path, "All Users", "config", "config.data").replace('/', '\\')
        close_mutex_executable = os.path.join(Config.PROJ_EXTERNAL_RES_PATH, "WeChatMultiple_Anhkgg.exe")
        if multiple_status == "已开启":
            close_mutex_code = ""
            prefix = "[要开全局] - "
            exe_path = wechat_path
        else:
            close_mutex_code = \
                f"""
                                \n{close_mutex_executable}
                            """
            prefix = ""
            # 判断环境
            if getattr(sys, 'frozen', False):  # 打包环境
                exe_path = sys.executable  # 当前程序的 exe
            else:  # PyCharm 或其他开发环境
                exe_path = close_mutex_executable  # 使用 handle_path

        bat_content = f"""
                        @echo off
                        chcp 65001
                        REM 复制配置文件
                        copy "{source_file}" "{target_file}"
                        if errorlevel 1 (
                            echo 复制配置文件失败
                            exit /b 1
                        )
                        echo 复制配置文件成功

                        REM 根据状态启动微信
                        @echo off{close_mutex_code}
                        cmd /u /c "start "" "{wechat_path}""
                        if errorlevel 1 (
                        echo 启动微信失败，请检查路径是否正确。
                        pause
                        exit /b 1
                        )
                        """

        # 确保路径存在
        account_file_path = os.path.join(Config.PROJ_USER_PATH, sw, f'{account}')
        if not os.path.exists(account_file_path):
            os.makedirs(account_file_path)
        # 保存为批处理文件
        bat_file_path = os.path.join(Config.PROJ_USER_PATH, sw, f'{account}', f'{prefix}{account}.bat')
        # 以带有BOM的UTF-8格式写入bat文件
        with open(bat_file_path, 'w', encoding='utf-8-sig') as bat_file:
            bat_file.write(bat_content)
        print(f"批处理文件已生成: {bat_file_path}")

        # 获取桌面路径
        desktop = winshell.desktop()
        # 获取批处理文件名并去除后缀
        bat_file_name = os.path.splitext(os.path.basename(bat_file_path))[0]
        # 构建快捷方式路径
        shortcut_path = os.path.join(desktop, f"{bat_file_name}.lnk")

        # 图标文件路径
        acc_dir = os.path.join(Config.PROJ_USER_PATH, str(sw), f"{account}")
        exe_name = os.path.splitext(os.path.basename(exe_path))[0]

        # 步骤1：提取图标为图片
        extracted_exe_png_path = os.path.join(acc_dir, f"{exe_name}_extracted.png")
        image_utils.extract_icon_to_png(exe_path, extracted_exe_png_path)

        # 步骤2：合成图片
        ico_jpg_path = os.path.join(acc_dir, f"{account}_{exe_name}.png")
        image_utils.add_diminished_se_corner_mark_to_image(avatar_path, extracted_exe_png_path, ico_jpg_path)

        # 步骤3：对图片转格式
        ico_path = os.path.join(acc_dir, f"{account}_{exe_name}.ico")
        image_utils.png_to_ico(ico_jpg_path, ico_path)

        # 清理临时文件
        os.remove(extracted_exe_png_path)

        # 创建快捷方式
        with winshell.shortcut(shortcut_path) as shortcut:
            shortcut.path = bat_file_path
            shortcut.working_directory = os.path.dirname(bat_file_path)
            # 修正icon_location的传递方式，传入一个包含路径和索引的元组
            shortcut.icon_location = (ico_path, 0)

        print(f"桌面快捷方式已生成: {os.path.basename(shortcut_path)}")
        return True


class AccInfoFunc:
    """
    账号信息
    常用变量：
        sw: 选择的软件标签
        acc: 账号标识
    """
    pass

    @staticmethod
    def get_acc_avatar_from_files(sw, acc):
        """
        从本地缓存或json文件中的url地址获取头像，失败则默认头像
        """
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
        # print(sw, data_path, account)
        if not data_path:
            return "无配置路径"
        config_path_suffix, config_files = subfunc_file.get_remote_cfg(
            sw, config_path_suffix=None, config_file_list=None)
        if not isinstance(config_files, list) or len(config_files) == 0:
            return "无法获取配置路径"
        file = config_files[0]
        file_suffix = file.split(".")[-1]
        dest_filename = f"{account}.{file_suffix}"
        acc_cfg_path = (os.path.join(str(data_path), str(config_path_suffix), dest_filename)
                        .replace("\\", "/"))
        if os.path.exists(acc_cfg_path):
            mod_time = os.path.getmtime(acc_cfg_path)
            date = datetime.datetime.fromtimestamp(mod_time)
            return f"{date.year % 100:02}/{date.month:02}/{date.day:02} {date.hour:02}:{date.minute:02}"
        else:
            return "无配置"

    @staticmethod
    def get_acc_wrapped_display_name(sw, account) -> str:
        """获取账号的折叠展示名"""
        return StringUtils.balanced_wrap_text(
            AccInfoFunc.get_acc_origin_display_name(sw, account),
            10
        )

    @staticmethod
    def _silent_get_avatar_url(sw, acc_list, data_dir):
        """悄悄获取账号的头像url"""
        changed1 = subfunc_file.get_avatar_url_from_file(sw, acc_list, data_dir)
        changed2 = subfunc_file.get_avatar_url_from_other_sw(sw, acc_list)
        return changed1 or changed2

    @staticmethod
    def _silent_get_nickname(sw, acc_list, data_dir):
        """悄悄获取账号的头像url"""
        changed1 = subfunc_file.get_nickname_from_file(sw, acc_list, data_dir)
        changed2 = subfunc_file.get_nickname_from_other_sw(sw, acc_list)
        return changed1 or changed2

    @staticmethod
    def silent_get_and_config(sw):
        """后台静默获取账号配置"""
        root_class = GlobalMembers.root_class
        acc_tab_ui = root_class.acc_tab_ui
        root = root_class.root
        data_dir = root_class.sw_classes[sw].data_dir

        # 悄悄执行检测昵称和头像
        need_to_notice = False

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
            changed = AccInfoFunc._silent_get_avatar_url(sw, accounts_need_to_get_avatar, data_dir)
            if changed is True:
                need_to_notice = True

        # 3. 对待获取昵称的账号尝试遍历获取
        if len(accounts_need_to_get_nickname) > 0:
            changed = AccInfoFunc._silent_get_nickname(sw, accounts_need_to_get_nickname, data_dir)
            if changed is True:
                need_to_notice = True

        # 4. 偷偷创建配置文件
        curr_config_acc = subfunc_file.get_curr_wx_id_from_config_file(sw, data_dir)
        if curr_config_acc is not None:
            if AccInfoFunc.get_sw_acc_login_cfg(sw, curr_config_acc, data_dir) == "无配置":
                changed, _ = AccOperator.operate_acc_config('add', sw, curr_config_acc)
                if changed is True:
                    need_to_notice = True

        # 5. 通知
        if need_to_notice is True:
            messagebox.showinfo("提醒", "已自动化获取或配置！即将刷新！")
            root.after(0, acc_tab_ui.refresh_frame, sw)

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
        if data_dir is None or os.path.isdir(data_dir) is False:
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

        exe, excluded_dir_list = subfunc_file.get_remote_cfg(
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
        multiple_status = sw_class.freely_multirun
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

    @staticmethod
    def get_main_hwnd_of_accounts(sw, acc_list):
        target_class, = subfunc_file.get_remote_cfg(sw, main_wnd_class=None)
        if target_class is None:
            messagebox.showerror("错误", f"{sw}平台未适配")
            return False
        for acc in acc_list:
            correct_hwnd = None

            pid, = subfunc_file.get_sw_acc_data(sw, acc, pid=None)
            hwnd_list = hwnd_utils.get_hwnd_list_by_pid_and_class(pid, target_class)
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
                hwnd_utils.set_window_title(correct_hwnd, f"微信 - {display_name}")

    @staticmethod
    def is_hwnd_a_main_wnd_of_acc_on_sw(hwnd, sw, acc):
        """检测窗口是否是某个账号的主窗口"""
        # hwnd_utils.restore_window(hwnd)
        pid, = subfunc_file.get_sw_acc_data(sw, acc, pid=None)
        if pid is None:
            return False
        # 判断hwnd是否属于指定的pid
        if hwnd_utils.get_hwnd_details_of_(hwnd)["pid"] != pid:
            return False
        expected_class, = subfunc_file.get_remote_cfg(sw, main_wnd_class=None)
        class_name = win32gui.GetClassName(hwnd)
        # print(expected_class, class_name)
        if sw == SW.WECHAT:
            # 旧版微信可直接通过窗口类名确定主窗口
            return class_name == expected_class
        elif sw == SW.WEIXIN:
            if class_name != expected_class:
                return False
            # 新版微信需要通过窗口控件判定
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            # 检查是否有最大化按钮
            has_maximize = bool(style & win32con.WS_MAXIMIZEBOX)
            # print("有最大化按钮", hwnd, has_maximize)
            return has_maximize

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
        if messagebox.askyesno("提示", "请将微信窗口置于前台，是否继续？"):
            # 将桌面中可见的窗口从顶部到底部遍历
            hwnds = hwnd_utils.get_visible_windows_sorted_by_top()
            for hwnd in hwnds:
                print(hwnd_utils.get_hwnd_details_of_(hwnd)["class"])
                if AccInfoFunc.is_hwnd_a_main_wnd_of_acc_on_sw(hwnd, sw, account):
                    subfunc_file.update_sw_acc_data(sw, account, main_hwnd=hwnd)
                    display_name = AccInfoFunc.get_acc_origin_display_name(sw, account)
                    hwnd_utils.set_window_title(hwnd, f"微信 - {display_name}")
                    break
