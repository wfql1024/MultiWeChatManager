import time

import psutil
import win32gui

from functions import func_setting, func_file, subfunc_file
from resources import Config
from utils import handle_utils, process_utils, ini_utils, pywinhandle


def kill_wechat_multiple_processes():
    """清理多开器的进程"""
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
    """清理闲置的登录窗口和多开器子窗口"""
    handle_utils.close_windows_by_class(
        [
            "WTWindow",
            "WeChatLoginWndForPC",
            "WindowsForms10.Window.8.app.0.141b42a_r13_ad1"
        ]
    )
    kill_wechat_multiple_processes()


def get_mutex_dict():
    """拿到当前时间下系统中所有微信进程的互斥体情况"""
    pids = process_utils.get_process_ids_by_name("WeChat.exe")
    has_mutex_dict = dict()
    for pid in pids:
        # 没有在all_wechat节点中，则这个是尚未判断的，默认有互斥体
        has_mutex, = subfunc_file.get_acc_details_from_acc_json("all_wechat", **{f"{pid}": True})
        if has_mutex:
            subfunc_file.update_acc_details_to_acc_json("all_wechat", **{f"{pid}": True})
            has_mutex_dict.update({pid: has_mutex})
    return has_mutex_dict


def open_wechat(status, has_mutex_dictionary=None):
    """
    根据状态以不同方式打开微信
    :param status: 状态
    :param has_mutex_dictionary:
    :return: 微信窗口句柄
    """

    if has_mutex_dictionary is None:
        has_mutex_dictionary = dict()
    print(f"进入了打开微信的方法...")
    start_time = time.time()
    sub_exe_process = None
    sub_exe = "全局多开"
    wechat_path = func_setting.get_wechat_install_path()
    if not wechat_path:
        return None

    if status == "已开启":
        print(f"当前是全局多开模式")
        process_utils.create_process_with_medium_il(wechat_path)
        time.sleep(0.1)
    else:
        # 获取当前选择的多开子程序
        sub_exe = ini_utils.get_setting_from_ini(
            Config.SETTING_INI_PATH,
            Config.INI_SECTION,
            Config.INI_KEY_SUB_EXE,
        )
        # ————————————————————————————————WeChatMultiple_Anhkgg.exe————————————————————————————————
        if sub_exe == "WeChatMultiple_Anhkgg.exe":
            sub_exe_process = process_utils.create_process_with_medium_il(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}",
                creation_flags=process_utils.CREATE_NO_WINDOW
            )
            # time.sleep(1.1)
        # ————————————————————————————————WeChatMultiple_wfql.exe————————————————————————————————
        elif sub_exe == "WeChatMultiple_wfql.exe":
            sub_exe_process = process_utils.create_process_with_medium_il(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}",
                creation_flags=process_utils.CREATE_NO_WINDOW
            )
            # time.sleep(1.1)
        # ————————————————————————————————WeChatMultiple_lyie15.exe————————————————————————————————
        elif sub_exe == "WeChatMultiple_lyie15.exe":
            sub_exe_process = process_utils.create_process_with_medium_il(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}"
            )
            sub_exe_hwnd = handle_utils.wait_for_window_open("WTWindow", 8)
            if sub_exe_hwnd:
                button_handle = handle_utils.get_all_child_handles(
                    sub_exe_hwnd
                )[1]
                if button_handle:
                    button_details = handle_utils.get_window_details_from_hwnd(button_handle)
                    button_cx = int(button_details["width"] / 2)
                    button_cy = int(button_details["height"] / 2)
                    handle_utils.do_click_in_window(button_handle, button_cx, button_cy)
                    # time.sleep(1.2)
        # ————————————————————————————————handle————————————————————————————————
        elif sub_exe == "handle":
            success_lists = handle_utils.close_mutex_of_pids()
            if success_lists:
                # 更新 has_mutex 为 False 并保存
                print(f"成功关闭{success_lists}：{time.time() - start_time:.4f}秒")

            # 所有操作完成后，执行创建进程的操作
            process_utils.create_process_with_medium_il(wechat_path, None)
        # ————————————————————————————————python————————————————————————————————
        elif sub_exe == "python":
            for pid, has_mutex in has_mutex_dictionary.items():
                success = pywinhandle.close_handles(
                    pywinhandle.find_handles(
                        [pid],
                        ['_WeChat_App_Instance_Identity_Mutex_Name']
                    )
                )
                if success:
                    # 更新 has_mutex 为 False 并保存
                    print(f"成功关闭：{time.time() - start_time:.4f}秒")
                else:
                    print(f"关闭互斥体失败，PID: {pid}")

            # 所有操作完成后，执行创建进程的操作
            process_utils.create_process_with_medium_il(wechat_path, None)

    return sub_exe_process, sub_exe


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
                handle_utils.do_click_in_window(handle, int(wechat_width * 0.5), int(wechat_height * 0.75))
            else:
                handles.remove(handle)

        time.sleep(5)
        # 检测到出现开始，直接列表再次为空结束
        if flag and len(handles) == 0:
            return
