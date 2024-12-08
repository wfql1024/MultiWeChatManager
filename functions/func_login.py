# func_login.py
import threading
import time
import tkinter as tk
from tkinter import messagebox

import win32con
import win32gui

from functions import func_config, subfunc_wechat, subfunc_file
from resources import Config
from utils import hwnd_utils, handle_utils
from utils.logger_utils import mylogger as logger


def manual_login(m_class, tab, status, window_callback):
    """
    根据状态进行手动登录过程
    :param tab: 选择的软件标签
    :param m_class:
    :param window_callback:
    :param status: 状态
    :return: 成功与否
    """
    # 初始化操作：清空闲置的登录窗口、多开器，清空并拉取各账户的登录和互斥体情况
    start_time = time.time()
    redundant_wnd_list, login_wnd_class, executable_name, cfg_handles = subfunc_file.get_details_from_remote_setting_json(
        tab, redundant_wnd_class=None, login_wnd_class=None, executable=None, cfg_handle_regex_list=None)
    # 关闭配置文件锁
    handle_utils.close_sw_mutex_by_handle(
        Config.HANDLE_EXE_PATH, executable_name, cfg_handles)
    hwnd_utils.close_all_wnd_by_classes(redundant_wnd_list)
    subfunc_wechat.kill_wechat_multiple_processes(tab)
    time.sleep(0.5)
    subfunc_file.clear_all_wechat_in_acc_json(tab)
    subfunc_file.update_all_wechat_in_acc_json(tab)
    has_mutex_dict = subfunc_wechat.get_mutex_dict(tab)
    logger.info(f"当前模式是：{status}")
    sub_exe_process, sub_exe = subfunc_wechat.open_wechat(status, has_mutex_dict, tab)
    wechat_hwnd = hwnd_utils.wait_for_wnd_open(login_wnd_class, 20)
    if wechat_hwnd:
        subfunc_file.set_all_wechat_values_to_false(tab)
        subfunc_file.update_manual_time_statistic(sub_exe, time.time() - start_time, tab)
        print(f"打开了登录窗口{wechat_hwnd}")
        if sub_exe_process:
            sub_exe_process.terminate()
        if hwnd_utils.wait_for_wnd_close(wechat_hwnd, timeout=60):
            print(f"手动登录成功，正在刷新...")
        else:
            messagebox.showinfo("提示", "登录窗口长时间未操作，即将刷新列表")
    else:
        logger.warning(f"打开失败，请重试！")
        messagebox.showerror("错误", "手动登录失败，请重试")

    m_class.root.after(0, m_class.refresh_main_frame)
    window_callback()


def auto_login_accounts(accounts, status, callback, tab="WeChat"):
    """
    对选择的账号，进行全自动登录
    :param tab: 选择的软件标签
    :param callback:
    :param accounts: 选择的账号列表
    :param status: 是否全局多开
    :return: 是否成功
    """

    def get_wnd_positions(n):
        # 实际的间隔设置
        actual_gap_width = int((screen_width - n * login_width) / (n + 1))
        # 去除两边间隔总共的宽度
        all_login_width = int(n * login_width + (n - 1) * actual_gap_width)
        # 计算起始位置x，y
        x = int((screen_width - all_login_width) / 2)
        y = int((screen_height - login_height) / 2) - 25
        # 计算每个窗口的位置
        for i in range(n):
            positions.append((x + i * (login_width + actual_gap_width), y))
        print(positions)

    if len(accounts) == 0:
        return False
    # 初始化操作：清空闲置的登录窗口、多开器，清空并拉取各账户的登录和互斥体情况
    redundant_wnd_list, login_wnd_class, executable_name, cfg_handles = (
        subfunc_file.get_details_from_remote_setting_json(
            tab, redundant_wnd_class=None, login_wnd_class=None, executable=None, cfg_handle_regex_list=None))
    hwnd_utils.close_all_wnd_by_classes(redundant_wnd_list)
    subfunc_wechat.kill_wechat_multiple_processes(tab)
    time.sleep(0.5)
    subfunc_file.clear_all_wechat_in_acc_json(tab)
    subfunc_file.update_all_wechat_in_acc_json(tab)

    # 检测尺寸设置是否完整
    login_size = subfunc_file.get_sw_login_size_from_setting_ini(tab)
    if not login_size or login_size == "":
        messagebox.showinfo("提醒", "缺少登录窗口尺寸配置，请到应用设置中添加！")
        return False
    else:
        login_width, login_height = login_size.split('*')

    # 确保整数
    login_width = int(login_width)
    login_height = int(login_height)

    # 优先自动获取尺寸，若获取不到从配置中获取
    screen_width = int(tk.Tk().winfo_screenwidth())
    screen_height = int(tk.Tk().winfo_screenheight())
    if not screen_height or not screen_width:
        screen_width, screen_height = subfunc_file.get_screen_size_from_setting_ini()
    # 计算一行最多可以显示多少个
    max_column = int(screen_width / login_width)

    # 存放登录窗口的起始位置的列表
    positions = []
    # 若账号个数超过最多显示个数，则只创建最多显示个数的位置列表
    count = len(accounts)
    if count > max_column:
        print(f"不能一行显示")
        get_wnd_positions(max_column)
    else:
        print(f"可以一行显示")
        get_wnd_positions(count)

    # 开始遍历登录账号过程
    start_time = time.time()
    # 使用一个set存储不重复的handle
    wechat_handles = set()
    for j in range(count):
        # 关闭配置文件锁
        handle_utils.close_sw_mutex_by_handle(
            Config.HANDLE_EXE_PATH, executable_name, cfg_handles)

        # 读取配置
        result = func_config.use_config(accounts[j], tab)
        if result:
            print(f"{accounts[j]}:复制配置文件成功")
        else:
            print(f"{accounts[j]}:复制配置文件失败")
            break

        # 打开微信
        has_mutex_dict = subfunc_wechat.get_mutex_dict(tab)
        sub_exe_process, sub_exe = subfunc_wechat.open_wechat(status, has_mutex_dict, tab)

        # 等待打开窗口
        end_time = time.time() + 20
        while True:
            wechat_hwnd = hwnd_utils.wait_for_wnd_open(login_wnd_class, 1)
            if wechat_hwnd is not None and wechat_hwnd not in wechat_handles:
                # 确保打开了新的微信登录窗口
                wechat_handles.add(wechat_hwnd)
                if sub_exe_process:
                    sub_exe_process.terminate()
                print(f"打开窗口成功：{wechat_hwnd}")
                subfunc_file.set_all_wechat_values_to_false(tab)
                subfunc_file.update_has_mutex_from_all_wechat(tab)
                break
            if time.time() > end_time:
                print(f"超时！换下一个账号")
                break

        # 安排窗口位置
        # 横坐标算出完美的平均位置
        new_left = positions[j % max_column][0]
        # 纵坐标由居中位置稍向上偏移，然后每轮完一行，位置向下移动一个登录窗口宽度的距离
        new_top = positions[j % max_column][1] - int(login_width / 2) + int(j / max_column) * login_width
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
            print(e)

        # 统计时间
        subfunc_file.update_auto_time_statistic(sub_exe, time.time() - start_time, j + 1, tab)

    # 循环登录完成
    # 如果有，关掉多余的多开器
    subfunc_wechat.kill_wechat_multiple_processes(tab)

    def func():
        # 两轮点击所有窗口的登录，防止遗漏
        handles = hwnd_utils.find_all_wnd_by_class_and_title(login_wnd_class)
        time.sleep(2.5)
        for h in handles:
            hwnd_utils.do_click_in_wnd(h, int(login_width * 0.5), int(login_height * 0.75))
            time.sleep(0.5)
        time.sleep(2.5)
        for h in handles:
            hwnd_utils.do_click_in_wnd(h, int(login_width * 0.5), int(login_height * 0.75))
            time.sleep(0.2)
        for h in handles:
            titles = ["进入微信", "进入WeChat", "Enter Weixin"]  # 添加所有需要查找的标题
            try:
                # 依次查找每个标题
                for title in titles:
                    cx, cy = hwnd_utils.get_center_pos_by_hwnd_and_title(h, title)
                    if cx is not None and cy is not None:
                        hwnd_utils.do_click_in_wnd(h, int(cx), int(cy))
                        break  # 找到有效坐标后退出循环
            except TypeError as te:
                print(te)
                print("没有按钮，应该是点过啦~")

    threading.Thread(target=func).start()

    # 结束条件为所有窗口消失或等待超过20秒（网络不好则会这样）
    end_time = time.time() + 30
    while True:
        hs = hwnd_utils.find_all_wnd_by_class_and_title(login_wnd_class)
        # print("等待登录完成")
        if len(hs) == 0:
            callback()
            return True
        if time.time() > end_time:
            callback()
            return True
