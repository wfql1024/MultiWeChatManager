import getpass
import os
import sys
import threading
import time
import winreg

import psutil
import win32gui
from functions import func_setting, func_account
from resources.config import Config
from utils import handle_utils, process_utils, ini_utils, json_utils


def is_valid_wechat_install_path(path) -> bool:
    if path and path != "":
        return os.path.exists(path)
    else:
        return False


def is_valid_wechat_data_path(path) -> bool:
    if path and path != "":
        config_data_path = os.path.join(path, "All Users", "config", "config.data").replace('\\', '/')
        return os.path.isfile(config_data_path)
    else:
        return False


def is_valid_wechat_dll_dir_path(path) -> bool:
    if path and path != "":
        return os.path.exists(os.path.join(path, "WeChatWin.dll"))
    else:
        return False


def get_wechat_install_path_from_process():
    for process in psutil.process_iter(['name', 'exe']):
        if process.name() == 'WeChat.exe':
            path = process.exe().replace('\\', '/')
            print(f"通过查找进程方式获取了微信安装地址：{path}")
            return path
    return None


def get_wechat_install_path_from_machine_register():
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\WeChat")
        found_path = winreg.QueryValueEx(key, "InstallLocation")[0].replace('\\', '/')
        winreg.CloseKey(key)
        print(f"通过注册表方式1获取了微信安装地址：{found_path}")
        if found_path:
            return os.path.join(found_path, "WeChat.exe").replace('\\', '/')
    except WindowsError as e:
        print(e)
    return None


def get_wechat_install_path_from_user_register():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Tencent\WeChat")
        found_path = winreg.QueryValueEx(key, "InstallPath")[0].replace('\\', '/')
        winreg.CloseKey(key)
        print(f"通过注册表方式2获取了微信安装地址：{found_path}")
        if found_path:
            return os.path.join(found_path, "WeChat.exe").replace('\\', '/')
    except WindowsError as e:
        print(e)
    return None


def get_wechat_data_path_from_user_register():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Tencent\WeChat", 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "FileSavePath")
        winreg.CloseKey(key)
        value = os.path.join(value, "WeChat Files").replace('\\', '/')
        return value
    except WindowsError:
        pass
    return None


def get_wechat_dll_dir_path_by_memo_maps():
    pids = process_utils.get_process_ids_by_name("WeChat.exe")
    if len(pids) == 0:
        print("没有运行微信。")
        return None
    else:
        process_id = pids[0]
        try:
            for f in psutil.Process(process_id).memory_maps():
                normalized_path = f.path.replace('\\', '/')
                # print(normalized_path)
                # 检查路径是否以 data_path 开头
                if normalized_path.endswith('WeChatWin.dll'):
                    dll_dir_path = os.path.dirname(normalized_path)
                    # print(dll_dir_path)
                    return dll_dir_path
        except psutil.AccessDenied:
            print(f"无法访问进程ID为 {process_id} 的内存映射文件，权限不足。")
        except psutil.NoSuchProcess:
            print(f"进程ID为 {process_id} 的进程不存在或已退出。")
        except Exception as e:
            print(f"发生意外错误: {e}")


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
    current_user = getpass.getuser()
    if not wechat_path:
        return None

    if status == "已开启":
        print(current_user)
        process_utils.create_process_with_medium_il(wechat_path, None)
        time.sleep(0.2)
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
            time.sleep(1.1)
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
                    handle_utils.do_click(button_handle, button_cx, button_cy)
                    time.sleep(1.2)
        # ————————————————————————————————原生开发————————————————————————————————
        elif sub_exe == "原生":
            pids = process_utils.get_process_ids_by_name("WeChat.exe")
            account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)  # 加载 JSON 数据

            for pid in pids:
                # 查找 JSON 中哪个 account 的 pid 匹配
                matching_account = None
                for account, details in account_data.items():
                    if details.get("pid") == pid:
                        matching_account = account
                        break

                if not matching_account:
                    handle_utils.close_mutex_by_id(pid)
                    continue

                has_mutex = account_data[matching_account].get("has_mutex", True)  # 默认为 True
                if has_mutex:
                    # 尝试关闭互斥体
                    success = handle_utils.close_mutex_by_id(pid)
                    if success:
                        # 更新 has_mutex 为 False 并保存
                        account_data[matching_account]["has_mutex"] = False
                        json_utils.save_json_data(Config.ACC_DATA_JSON_PATH, account_data)
                    else:
                        print(f"关闭互斥体失败，PID: {pid}")
                else:
                    print(f"PID {pid} 已经关闭过互斥体，跳过")

            # 所有操作完成后，执行创建进程的操作
            process_utils.create_process_with_medium_il(wechat_path, None)

    wechat_hwnd = handle_utils.wait_for_window_open("WeChatLoginWndForPC", 8)

    if sub_exe_process:
        sub_exe_process.terminate()
    if wechat_hwnd:
        print("打开了登录窗口")
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
                handle_utils.do_click(handle, int(wechat_width * 0.5), int(wechat_height * 0.75))
            else:
                handles.remove(handle)

        time.sleep(5)
        # 检测到出现开始，直接列表再次为空结束
        if flag and len(handles) == 0:
            return


if __name__ == '__main__':
    open_wechat("未开启")
