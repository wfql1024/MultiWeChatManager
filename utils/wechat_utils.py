import subprocess
import time
import win32gui
from pywinauto.controls.hwndwrapper import HwndWrapper
from functions import func_setting
from resources.config import Config
from utils import handle_utils


def clear_idle_wnd_and_process():
    handle_utils.close_windows_by_class(
        [
            "WTWindow",
            "WeChatLoginWndForPC",
            "WindowsForms10.BUTTON.app.0.141b42a_r13_ad1"
        ]
    )


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
            sub_exe_hwnd = handle_utils.wait_for_window_open("WTWindow", 3)
            if sub_exe_hwnd:
                button_handle = handle_utils.get_all_child_handles(
                    sub_exe_hwnd
                )[1]
                button = HwndWrapper(button_handle)
                if button:
                    handle_utils.do_click(button_handle, int(button.rectangle().width() / 2),
                                          int(button.rectangle().height() / 2))
            else:
                return None

        elif sub_exe == "WeChatMultiple_pipihan.exe":
            multi_wechat_process = subprocess.Popen(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}"
            )
            print(multi_wechat_process)
            sub_exe_hwnd = handle_utils.wait_for_window_open("WTWindow", 3)
            print(sub_exe_hwnd)
            if sub_exe_hwnd:
                button_handle = handle_utils.get_all_child_handles(
                    sub_exe_hwnd
                )[2]
                time.sleep(3)
                button = HwndWrapper(button_handle)
                if button:
                    handle_utils.do_click(button_handle, int(button.rectangle().width() / 2),
                                          int(button.rectangle().height() / 2))
            else:
                return None

        elif sub_exe == "WeChatMultiple_GsuhyFihx.exe":
            multi_wechat_process = subprocess.Popen(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}",
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            sub_exe_hwnd = handle_utils.wait_for_window_open("WTWindow", 3)
            if sub_exe_hwnd:
                button_handle = handle_utils.get_all_child_handles(
                    handle_utils.get_all_child_handles(
                        sub_exe_hwnd
                    )[4]
                )[0]
                button = HwndWrapper(button_handle)
                if button:
                    handle_utils.do_click(button_handle, int(button.rectangle().width() / 2),
                                          int(button.rectangle().height() / 2))
            else:
                return None

        elif sub_exe == "WeChatMultiple_moyan123.exe":
            multi_wechat_process = subprocess.Popen(
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
            else:
                return None

        elif sub_exe == "WeChatMultiple_wudixiaozi135.exe":
            multi_wechat_process = subprocess.Popen(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}",
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            sub_exe_hwnd = handle_utils.wait_for_window_open("WTWindow", 3)
            if sub_exe_hwnd:
                button_handle = handle_utils.get_all_child_handles(sub_exe_hwnd)[8]
                button = HwndWrapper(button_handle)
                if button:
                    handle_utils.do_click(button_handle, int(button.rectangle().width() / 2),
                                          int(button.rectangle().height() / 2))
            else:
                return None

    # 等待登录窗口
    time.sleep(2)
    if multi_wechat_process:
        multi_wechat_process.terminate()
    wechat_hwnd = handle_utils.wait_for_window_open("WeChatLoginWndForPC", 3)
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
