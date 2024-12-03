import time

import psutil
import win32gui

from functions import func_setting, subfunc_file
from resources import Config
from utils import hwnd_utils, process_utils, ini_utils, pywinhandle, handle_utils, sys_utils
from utils.logger_utils import mylogger as logger


def switch_to_wechat_account(window, account):
    hwnd_utils.bring_wnd_to_left(window)
    classes = ["WeChatMainWndForPC"]
    hwnd_utils.hide_all_wnd_by_classes(classes)
    main_hwnd, = subfunc_file.get_acc_details_from_json_by_tab("WeChat", account, main_hwnd=None)
    hwnd_utils.restore_window(main_hwnd)


def kill_wechat_multiple_processes(sw="WeChat"):
    """清理多开器的进程"""
    print("清理多余多开器窗口...")
    # 遍历所有的进程
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # 检查进程名是否以"WeChatMultiple_"开头
            if proc.name() and proc.name().startswith(f'{sw}WeChatMultiple_'):
                proc.kill()
                print(f"Killed process tree for {proc.name()} (PID: {proc.pid})")

        except Exception as e:
            logger.error(e)

def get_mutex_dict(sw="WeChat"):
    """拿到当前时间下系统中所有微信进程的互斥体情况"""
    print("获取互斥体情况...")
    executable = subfunc_file.get_details_from_remote_setting_json(sw, executable=None)
    pids = process_utils.get_process_ids_by_name(executable)
    has_mutex_dict = dict()
    for pid in pids:
        # 没有在all_wechat节点中，则这个是尚未判断的，默认有互斥体
        has_mutex, = subfunc_file.get_acc_details_from_json_by_tab(sw, "all_wechat", **{f"{pid}": True})
        if has_mutex:
            subfunc_file.update_acc_details_to_json_by_tab(sw, "all_wechat", **{f"{pid}": True})
            has_mutex_dict.update({pid: has_mutex})
    return has_mutex_dict

def open_wechat(status, has_mutex_dictionary=None, sw="WeChat"):
    """
    根据状态以不同方式打开微信
    :param sw: 选择软件标签
    :param status: 状态
    :param has_mutex_dictionary: 有互斥体账号的列表
    :return: 微信窗口句柄
    """
    # print(f"传入{sw}")
    if has_mutex_dictionary is None:
        has_mutex_dictionary = dict()
    print(f"进入了打开微信的方法...")
    start_time = time.time()
    sub_exe_process = None
    wechat_path = func_setting.get_sw_install_path(sw=sw)
    executable = subfunc_file.get_details_from_remote_setting_json(sw, executable=None)
    if not wechat_path:
        return None

    if status == "已开启":
        print(f"当前是全局多开模式")
        sub_exe = "全局多开"
        create_process_without_admin(wechat_path)
        time.sleep(0.1)
    else:
        # 获取当前选择的多开子程序
        sub_exe = ini_utils.get_setting_from_ini(
            Config.SETTING_INI_PATH,
            sw,
            Config.INI_KEY_SUB_EXE,
        )
        # ————————————————————————————————WeChatMultiple_Anhkgg.exe————————————————————————————————
        if sub_exe == "WeChatMultiple_Anhkgg.exe":
            sub_exe_process = create_process_without_admin(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}",
                creation_flags=process_utils.CREATE_NO_WINDOW
            )
        # ————————————————————————————————WeChatMultiple_wfql.exe————————————————————————————————
        elif sub_exe == "WeChatMultiple_wfql.exe":
            sub_exe_process = create_process_without_admin(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}",
                creation_flags=process_utils.CREATE_NO_WINDOW
            )
        # ————————————————————————————————WeChatMultiple_lyie15.exe————————————————————————————————
        elif sub_exe == "WeChatMultiple_lyie15.exe":
            sub_exe_process = create_process_without_admin(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}"
            )
            sub_exe_hwnd = hwnd_utils.wait_for_wnd_open("WTWindow", 8)
            if sub_exe_hwnd:
                button_handle = hwnd_utils.get_all_child_hwnd(
                    sub_exe_hwnd
                )[1]
                if button_handle:
                    button_details = hwnd_utils.get_wnd_details_from_hwnd(button_handle)
                    button_cx = int(button_details["width"] / 2)
                    button_cy = int(button_details["height"] / 2)
                    hwnd_utils.do_click_in_wnd(button_handle, button_cx, button_cy)
        # ————————————————————————————————handle————————————————————————————————
        elif sub_exe == "handle":
            executable, handle_regex_list = subfunc_file.get_details_from_remote_setting_json(
                sw, executable=None, handle_regex_list=None)
            success_lists = handle_utils.close_all_old_wechat_mutex_by_handle(
                Config.HANDLE_EXE_PATH, executable, handle_regex_list)
            if success_lists:
                # 更新 has_mutex 为 False 并保存
                print(f"成功关闭{success_lists}：{time.time() - start_time:.4f}秒")

            # 所有操作完成后，执行创建进程的操作
            print(f"打开：{wechat_path}")
            create_process_without_admin(wechat_path, None)
        # ————————————————————————————————python[强力]————————————————————————————————
        elif sub_exe == "python[S]":
            pids = process_utils.get_process_ids_by_name(executable)
            if len(pids) > 0:
                success = pywinhandle.close_handles(
                    pywinhandle.find_handles(
                        pids,
                        ['_WeChat_App_Instance_Identity_Mutex_Name']
                    )
                )
                if success:
                    # 更新 has_mutex 为 False 并保存
                    print(f"成功关闭：{time.time() - start_time:.4f}秒")
                else:
                    print(f"关闭互斥体失败: {str(pids)}")

            # 所有操作完成后，执行创建进程的操作
            create_process_without_admin(wechat_path, None)
        # ————————————————————————————————python————————————————————————————————
        elif sub_exe == "python":
            if len(has_mutex_dictionary) > 0:
                pids, values = zip(*has_mutex_dictionary.items())
                success = pywinhandle.close_handles(
                    pywinhandle.find_handles(
                        pids,
                        ['_WeChat_App_Instance_Identity_Mutex_Name']
                    )
                )
                if success:
                    # 更新 has_mutex 为 False 并保存
                    print(f"成功关闭：{time.time() - start_time:.4f}秒")
                else:
                    print(f"关闭互斥体失败: {str(pids)}")
            create_process_without_admin(wechat_path, None)

    return sub_exe_process, sub_exe


def get_login_size(tab, status):
    redundant_wnd_list, login_wnd_class = subfunc_file.get_details_from_remote_setting_json(
        tab, redundant_wnd_class=None, login_wnd_class=None)
    print(login_wnd_class)
    hwnd_utils.close_all_wnd_by_classes(redundant_wnd_list)

    kill_wechat_multiple_processes()
    has_mutex_dict = get_mutex_dict(tab)
    sub_exe_process, sub_exe = open_wechat(status, has_mutex_dict, sw=tab)
    wechat_hwnd = hwnd_utils.wait_for_wnd_open(login_wnd_class, timeout=8)
    if wechat_hwnd:
        print(f"打开了登录窗口{wechat_hwnd}")
        if sub_exe_process:
            sub_exe_process.terminate()
        time.sleep(2)
        login_wnd_details = hwnd_utils.get_wnd_details_from_hwnd(wechat_hwnd)
        login_wnd = login_wnd_details["window"]
        login_width = login_wnd_details["width"]
        login_height = login_wnd_details["height"]
        logger.info(f"获得了窗口尺寸：{login_width}, {login_height}")
        login_wnd.close()
        return login_width, login_height


def create_process_without_admin(executable, args=None, creation_flags=process_utils.CREATE_NEW_CONSOLE):
    if sys_utils.get_sys_major_version_name() == "win7":
        return process_utils.create_process_for_win7(executable, args, creation_flags)
    else:
        return process_utils.create_process_with_medium_il(executable, args, creation_flags)


def logging_in_listener():
    handles = set()
    flag = False

    while True:
        handle = win32gui.FindWindow("WeChatLoginWndForPC")
        if handle:
            handles.add(handle)
            flag = True
        print(f"当前有微信窗口：{handles}")
        for handle in list(handles):
            if win32gui.IsWindow(handle):
                wechat_wnd_details = hwnd_utils.get_wnd_details_from_hwnd(handle)
                wechat_width = wechat_wnd_details["width"]
                wechat_height = wechat_wnd_details["height"]
                hwnd_utils.do_click_in_wnd(handle, int(wechat_width * 0.5), int(wechat_height * 0.75))
            else:
                handles.remove(handle)

        time.sleep(5)
        # 检测到出现开始，直接列表再次为空结束
        if flag and len(handles) == 0:
            return
