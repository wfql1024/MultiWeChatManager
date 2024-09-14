# func_login.py
import time
import tkinter as tk
from tkinter import messagebox

import win32con
import win32gui

from functions import func_setting, func_config
from utils import handle_utils, wechat_utils


def manual_login(status):
    """
    根据状态进行手动登录过程
    :param status: 状态
    :return: 成功与否
    """
    wechat_utils.clear_idle_wnd_and_process()
    time.sleep(0.5)
    wechat_hwnd = wechat_utils.open_wechat(status)
    if wechat_hwnd:
        print(f"打开了登录窗口{wechat_hwnd}")
        if handle_utils.wait_for_window_close(wechat_hwnd, timeout=60):
            print(f"登录窗口已关闭")
            return True
    else:
        print(f"打开失败，请重试！")
        return False
    return True


def auto_login(account, status):
    return auto_login_accounts([account], status)


def auto_login_accounts(accounts, status):
    """
    对选择的账号，进行
    :param accounts:
    :param status:
    :return:
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

    # 关闭闲置的子程序和登录窗口
    wechat_utils.clear_idle_wnd_and_process()

    # 检测尺寸设置是否完整
    login_size = func_setting.get_login_size_from_ini()
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
    screen_width = int(tk.Tk().winfo_screenwidth())
    screen_height = int(tk.Tk().winfo_screenheight())
    if not screen_height or not screen_width:
        screen_width, screen_height = func_setting.get_screen_size_from_ini()
    # 计算一行最多可以显示多少个
    max_column = int(screen_width / login_width)

    # 存放登录窗口的起始位置的列表
    positions = []

    # 若账号个数超过最多显示个数，则只创建最多显示个数的位置列表
    if count > max_column:
        print(f"不能一行显示")
        get_wnd_positions(max_column)
    else:
        print(f"可以一行显示")
        get_wnd_positions(count)

    start_time = time.time()
    # 使用一个set存储不重复的handle
    wechat_handles = set()
    # 遍历登录账号
    for j in range(count):
        # 读取配置
        result = func_config.use_config(accounts[j])
        if result:
            print(f"{accounts[j]}:复制配置文件成功")
        else:
            print(f"{accounts[j]}:复制配置文件失败")
            break

        # 等待打开窗口
        wechat_hwnd = wechat_utils.open_wechat(status)
        if wechat_hwnd is None:
            messagebox.showerror("错误", "打不开登录窗口")
            return False
        if wechat_hwnd not in wechat_handles:
            print(f"{accounts[j]}:打开了登录窗口{wechat_hwnd}")
            wechat_handles.add(wechat_hwnd)
        else:
            print(f"{accounts[j]}:非对应窗口，继续等待")
            end_time = time.time() + 8
            while True:
                wechat_hwnd = handle_utils.wait_for_window_open("WeChatLoginWndForPC", 8)
                if wechat_hwnd not in wechat_handles:
                    wechat_handles.add(wechat_hwnd)
                    break
                if time.time() > end_time:
                    print(f"超时！换下一个账号")
                    break

        # 横坐标算出完美的平均位置
        new_left = positions[j % max_column][0]
        # 纵坐标由居中位置稍向上偏移，然后每轮完一行，位置向下移动一个登录窗口宽度的距离
        new_top = positions[j % max_column][1] - int(login_width / 2) + int(j / max_column) * login_width
        # do_click(wechat_hwnd, int(login_width * 0.5), int(login_height * 0.75))
        win32gui.SetWindowPos(
            wechat_hwnd,
            win32con.HWND_TOP,
            new_left,
            new_top,
            int(login_width),
            int(login_height),
            win32con.SWP_SHOWWINDOW
        )
        print(f"登录到第{j + 1}个账号用时：{time.time() - start_time:.4f}秒")

    # 如果有，关掉多余的多开器
    wechat_utils.kill_wechat_multiple_processes()

    # 两轮点击所有窗口的登录，防止遗漏
    handles = handle_utils.find_all_windows("WeChatLoginWndForPC", "微信")
    for h in handles:
        handle_utils.do_click(h, int(login_width * 0.5), int(login_height * 0.75))
    for h in handles:
        handle_utils.do_click(h, int(login_width * 0.5), int(login_height * 0.75))

    # 结束条件为所有窗口消失或等待超过20秒（网络不好则会这样）
    end_time = time.time() + 20
    while True:
        hs = handle_utils.find_all_windows("WeChatLoginWndForPC", "微信")
        if len(hs) == 0:
            return True
        if time.time() > end_time:
            return True


if __name__ == '__main__':
    auto_login_accounts([1, 2, 3, 4, 5, 6, 7, 8], "未开启")
