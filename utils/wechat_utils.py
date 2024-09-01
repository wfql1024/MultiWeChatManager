import ctypes
import subprocess
import time

import psutil
import win32gui
from pywinauto.controls.hwndwrapper import HwndWrapper
from functions import func_setting
from resources.config import Config
from utils import handle_utils


def kill_wechat_multiple_processes():
    # 遍历所有的进程
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # 检查进程名是否以"WeChatMultiple_"开头
            if proc.name() and proc.name().startswith('WeChatMultiple_'):
                proc.kill()
                print(f"Killed process tree for {proc.name()} (PID: {proc.pid})")

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass


def clear_idle_wnd_and_process():
    handle_utils.close_windows_by_class(
        [
            "WTWindow",
            "WeChatLoginWndForPC",
            "WindowsForms10.Window.8.app.0.141b42a_r13_ad1"
        ]
    )
    kill_wechat_multiple_processes()


def open_wechat(status):
    """
    根据状态以不同方式打开微信
    :param status: 状态
    :return: 微信窗口句柄
    """
    sub_exe_process = None
    wechat_path = func_setting.get_wechat_install_path()
    data_path = func_setting.get_wechat_data_path()
    if not wechat_path or not data_path:
        return None

    if status == "已开启":
        subprocess.Popen(wechat_path, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        # 获取当前选择的多开子程序
        sub_exe = func_setting.get_setting_from_ini(
            Config.SETTING_INI_PATH,
            Config.INI_SECTION,
            Config.INI_KEY_SUB_EXE,
        )
        # ————————————————————————————————WeChatMultiple_Anhkgg.exe————————————————————————————————
        if sub_exe == "WeChatMultiple_Anhkgg.exe":
            sub_exe_process = subprocess.Popen(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}",
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        # ————————————————————————————————WeChatMultiple_lyie15.exe————————————————————————————————
        elif sub_exe == "WeChatMultiple_lyie15.exe":
            sub_exe_process = subprocess.Popen(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}",
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            sub_exe_hwnd = handle_utils.wait_for_window_open("WTWindow", 8)
            if sub_exe_hwnd:
                button_handle = handle_utils.get_all_child_handles(
                    sub_exe_hwnd
                )[1]
                button = HwndWrapper(button_handle)
                if button:
                    handle_utils.do_click(button_handle, int(button.rectangle().width() / 2),
                                          int(button.rectangle().height() / 2))
        # ————————————————————————————————WeChatMultiple_pipihan.exe————————————————————————————————
        elif sub_exe == "WeChatMultiple_pipihan.exe":
            sub_exe_hwnd_list = handle_utils.find_all_windows("WTWindow", "微信多开----by 雄雄")
            if len(sub_exe_hwnd_list) == 0:
                print("找不到")
                sub_exe_process = subprocess.Popen(
                    f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}",
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                sub_exe_hwnd = handle_utils.wait_for_window_open("WTWindow", 3)
                if not sub_exe_hwnd:
                    return None
            else:
                sub_exe_hwnd = sub_exe_hwnd_list[0]
            print(f"找到了{sub_exe_hwnd}")
            button_handle = handle_utils.get_all_child_handles(
                sub_exe_hwnd
            )[2]
            time.sleep(0.5)
            button = HwndWrapper(button_handle)
            if button:
                handle_utils.do_click(button_handle, int(button.rectangle().width() / 2),
                                      int(button.rectangle().height() / 2))

                time.sleep(2.5)
        # ————————————————————————————————WeChatMultiple_moyan123.exe————————————————————————————————
        elif sub_exe == "WeChatMultiple_moyan123.exe":
            sub_exe_process = subprocess.Popen(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}",
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            sub_exe_hwnd = handle_utils.wait_for_window_open("WTWindow", 3)
            if sub_exe_hwnd:
                button_handle = handle_utils.get_all_child_handles(
                    sub_exe_hwnd
                )[2]
                button = HwndWrapper(button_handle)
                if button:
                    handle_utils.do_click(button_handle, int(button.rectangle().width() / 2),
                                          int(button.rectangle().height() / 2))
                time.sleep(1)
                sub_exe_process.terminate()
            else:
                return None

    wechat_hwnd = handle_utils.wait_for_window_open("WeChatLoginWndForPC", 8)
    if wechat_hwnd:
        return wechat_hwnd
    else:
        return None


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
                wechat_wnd_details = handle_utils.get_window_details_from_hwnd(handle)
                wechat_width = wechat_wnd_details["width"]
                wechat_height = wechat_wnd_details["height"]
                # handle_utils.do_click(handle, int(wechat_width * 0.5), int(wechat_height * 0.75))
            else:
                handles.remove(handle)

        time.sleep(5)
        # 检测到出现开始，直接列表再次为空结束
        if flag and len(handles) == 0:
            return
