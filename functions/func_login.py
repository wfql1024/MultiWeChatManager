# func_login.py
import ctypes
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox

import win32api
import win32con
import win32gui
from pywinauto.controls.hwndwrapper import HwndWrapper

import utils
from functions import func_setting
from functions.func_config import ConfigCreator
from resources.config import Config
from utils import window_utils
from utils.window_utils import wait_for_window_open, wait_for_window_close


def logging_in_listener():
    handles = set()
    flag = False

    while True:
        handle = win32gui.FindWindow("WeChatLoginWndForPC", "微信")
        if handle:
            handles.add(handle)
            flag = True
        print(f"当前有微信窗口：{handles}")
        for handle in list(handles):
            if win32gui.IsWindow(handle):
                wechat_wnd_details = utils.window_utils.get_window_details_from_hwnd(handle)
                wechat_width = wechat_wnd_details["width"]
                wechat_height = wechat_wnd_details["height"]
                # do_click(handle, int(wechat_width * 0.5), int(wechat_height * 0.75))
            else:
                handles.remove(handle)

        time.sleep(5)
        # 检测到出现开始，直接列表再次为空结束
        if flag and len(handles) == 0:
            return


def get_all_child_handles(parent_handle):
    """
    获取指定父窗口句柄下的所有子窗口句柄。

    :param parent_handle: 父窗口句柄
    :return: 子窗口句柄列表
    """
    child_handles = []

    def enum_child_windows_proc(hwnd, lParam):
        child_handles.append(hwnd)
        return True

    # 定义回调函数类型
    EnumChildWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    enum_proc = EnumChildWindowsProc(enum_child_windows_proc)

    # 调用 EnumChildWindows 来获取所有子窗口
    ctypes.windll.user32.EnumChildWindows(parent_handle, enum_proc, 0)

    return child_handles


def do_click(handle, cx, cy):  # 第四种，可后台
    """
    在窗口中的相对位置点击鼠标，可以后台
    :param handle: 句柄
    :param cx: 相对横坐标
    :param cy: 相对纵坐标
    :return: 无
    """
    long_position = win32api.MAKELONG(cx, cy)  # 模拟鼠标指针 传送到指定坐标
    win32api.SendMessage(handle, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, long_position)  # 模拟鼠标按下
    win32api.SendMessage(handle, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON, long_position)  # 模拟鼠标弹起


def open_wechat(status):
    """
    根据状态以不同方式打开微信
    :param status: 状态
    :return: 微信窗口句柄
    """
    multi_wechat_process = None
    wechat_path = func_setting.get_wechat_install_path()
    data_path = func_setting.get_wechat_data_path()
    if not wechat_path or not data_path:
        return None

    if status == "已开启":
        wechat_process = subprocess.Popen(wechat_path, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        sub_exe = func_setting.get_setting_from_ini(
            Config.SETTING_INI_PATH,
            Config.INI_SECTION,
            Config.INI_KEY_SUB_EXE,
        )
        if sub_exe == "WeChatMultiple_Anhkgg.exe":
            multi_wechat_process = subprocess.Popen(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}",
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        elif sub_exe == "WeChatMultiple_lyie15.exe":
            multi_wechat_process = subprocess.Popen(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}",
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            sub_exe_hwnd = wait_for_window_open("WTWindow", 3)
            if sub_exe_hwnd:
                child_handles = get_all_child_handles(sub_exe_hwnd)
                button = HwndWrapper(child_handles[1])
                if button:
                    do_click(child_handles[1], int(button.rectangle().width() / 2),
                             int(button.rectangle().height() / 2))
        elif sub_exe == "WeChatMultiple_pipihan.exe":
            multi_wechat_process = subprocess.Popen(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}",
                # creationflags=subprocess.CREATE_NO_WINDOW
            )
            sub_exe_hwnd = wait_for_window_open("WTWindow", 3)
            if sub_exe_hwnd:
                child_handles = get_all_child_handles(sub_exe_hwnd)
                time.sleep(2.5)
                button = HwndWrapper(child_handles[2])
                if button:
                    do_click(child_handles[2], int(button.rectangle().width() / 2),
                             int(button.rectangle().height() / 2))
    time.sleep(2)
    if multi_wechat_process:
        multi_wechat_process.terminate()
    wechat_hwnd = wait_for_window_open("WeChatLoginWndForPC", 3)
    if wechat_hwnd:
        return wechat_hwnd
    else:
        return None


def manual_login(status):
    """
    根据状态进行手动登录过程
    :param status: 状态
    :return: 成功与否
    """
    utils.window_utils.close_windows_by_class(["WTWindow", "WeChatLoginWndForPC"])
    wechat_hwnd = open_wechat(status)
    if wechat_hwnd:
        print(f"打开了登录窗口{wechat_hwnd}")
        login_size = func_setting.get_setting_from_ini(
            Config.SETTING_INI_PATH,
            Config.INI_SECTION,
            Config.INI_KEY_LOGIN_SIZE,
        )
        if not login_size or login_size == "":
            login_wnd_details = window_utils.get_window_details_from_hwnd(wechat_hwnd)
            login_wnd = login_wnd_details["window"]
            login_width = login_wnd_details["width"]
            login_height = login_wnd_details["height"]
            if 0.734 < login_width / login_height < 0.740:
                func_setting.save_setting_to_ini(
                    Config.SETTING_INI_PATH,
                    Config.INI_SECTION,
                    Config.INI_KEY_LOGIN_SIZE,
                    f"{login_width}*{login_height}"
                )
        if wait_for_window_close(wechat_hwnd, timeout=60):
            print("登录窗口已关闭")
            return True
    else:
        print("打开失败，请重试！")
        return False
    return True


def auto_login(account, status):
    utils.window_utils.close_windows_by_class(["WTWindow", "WeChatLoginWndForPC"])
    creator = ConfigCreator(account)
    result = creator.use_config()
    if result:
        print("复制配置文件成功")
    else:
        return False
    wechat_hwnd = open_wechat(status)
    if wechat_hwnd:
        print(f"打开了登录窗口{wechat_hwnd}")
        wechat_wnd_details = utils.window_utils.get_window_details_from_hwnd(wechat_hwnd)
        wechat_wnd = wechat_wnd_details["window"]
        wechat_width = wechat_wnd_details["width"]
        wechat_height = wechat_wnd_details["height"]
        end_time = time.time() + 60
        while True:
            do_click(wechat_hwnd, int(wechat_width * 0.5), int(wechat_height * 0.75))
            time.sleep(0.2)
            if win32gui.IsWindow(wechat_hwnd) == 0:
                print("登录窗口已关闭")
                return True
            elif time.time() > end_time:
                print("登录超时")
                return False
    return False


def auto_login_accounts(accounts, status, max_gap_width=30):
    def get_wnd_position(n):
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

    # 关闭闲置的子程序和登录窗口
    utils.window_utils.close_windows_by_class(["WTWindow", "WeChatLoginWndForPC"])

    # 检测尺寸设置是否完整
    login_size = func_setting.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY_LOGIN_SIZE
    )
    if not login_size or login_size == "":
        messagebox.showinfo("提醒", "缺少登录窗口尺寸配置，请到应用设置中添加！")
        return False
    else:
        login_width, login_height = login_size.split('*')

    # 确保整数
    login_width = int(login_width)
    login_height = int(login_height)

    # 登录账号个数
    if len(accounts) == 0:
        return False
    count = len(accounts)

    # 优先自动获取尺寸，若获取不到从配置中获取
    screen_width = tk.Tk().winfo_screenwidth()
    screen_height = tk.Tk().winfo_screenheight()
    if not screen_height or not screen_width:
        screen_width, screen_height = func_setting.get_setting_from_ini(
            Config.SETTING_INI_PATH,
            Config.INI_SECTION,
            Config.INI_KEY_SCREEN_SIZE
        ).split('*')
    screen_width = int(screen_width)
    screen_height = int(screen_height)

    # 计算一行最多可以显示多少个
    max_column = int((screen_width - max_gap_width) / (login_width + max_gap_width))

    # 存放登录窗口的起始位置的列表
    positions = []

    # 若账号个数超过最多显示个数，则只创建最多显示个数的位置列表
    if count > max_column:
        print("不能一行显示")
        get_wnd_position(max_column)
    else:
        print("可以一行显示")
        get_wnd_position(count)

    # 遍历登录账号
    for j in range(count):
        # 读取配置
        creator = ConfigCreator(accounts[j])
        result = creator.use_config()
        if result:
            print(f"{accounts[j]}:复制配置文件成功")
        else:
            print(f"{accounts[j]}:复制配置文件失败")
            break

        # 等待打开窗口
        wechat_hwnd = open_wechat(status)
        if wechat_hwnd:
            print(f"{accounts[j]}:打开了登录窗口{wechat_hwnd}")
            wechat_wnd = HwndWrapper(wechat_hwnd)
        else:
            print(f"{accounts[j]}:登录窗口打开失败")
            break

        # 横坐标算出完美的平均位置
        new_left = positions[j % max_column][0]
        # 纵坐标由居中位置稍向上偏移，然后每轮完一行，位置向下移动一个登录窗口宽度的距离
        new_top = positions[j % max_column][1] - int(login_width / 2) + int(j / max_column) * login_width
        # do_click(wechat_hwnd, int(login_width * 0.5), int(login_height * 0.75))
        time.sleep(0.5)
        win32gui.SetWindowPos(
            wechat_hwnd,
            win32con.HWND_TOP,
            new_left,
            new_top,
            int(login_width),
            int(login_height),
            win32con.SWP_SHOWWINDOW
        )

    handles = window_utils.find_all_windows("WeChatLoginWndForPC", "微信")
    for h in handles:
        do_click(h, int(login_width * 0.5), int(login_height * 0.75))
    # 两遍防止遗漏
    for h in handles:
        do_click(h, int(login_width * 0.5), int(login_height * 0.75))

    end_time = time.time() + 20
    while True:
        hs = window_utils.find_all_windows("WeChatLoginWndForPC", "微信")
        if len(hs) == 0:
            return True
        if time.time() > end_time:
            return True


if __name__ == '__main__':
    auto_login_accounts([1, 2, 3, 4, 5, 6, 7, 8], "未开启")
