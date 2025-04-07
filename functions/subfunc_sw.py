import subprocess
import time

import psutil
import win32con
import win32gui

from functions import func_setting, subfunc_file
from public_class.enums import Position, Keywords, SW
from resources import Config
from utils import hwnd_utils, process_utils, pywinhandle, handle_utils, sys_utils
from utils.logger_utils import mylogger as logger


# TODO: 完善4.0的python模式


def is_hwnd_a_main_wnd_of_sw(hwnd, sw):
    """
    检测窗口是否是某个账号的主窗口
    :param hwnd:
    :param sw:
    :return:
    """
    expected_class, = subfunc_file.get_details_from_remote_setting_json(sw, main_wnd_class=None)
    class_name = win32gui.GetClassName(hwnd)
    print(expected_class, class_name)
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
        return has_maximize


def switch_to_sw_account_wnd(item_id, root):
    sw, acc = item_id.split("/")
    main_wnd_class, = subfunc_file.get_details_from_remote_setting_json(
        sw, main_wnd_class=None)
    classes = [main_wnd_class]
    main_hwnd, = subfunc_file.get_sw_acc_data(sw, acc, main_hwnd=None)

    # 程序主窗口左移
    hwnd_utils.set_size_and_bring_tk_wnd_to_(root, None, None, Position.LEFT)
    # 隐藏所有平台主窗口
    hwnd_utils.hide_all_by_wnd_classes(classes)
    # 恢复平台指定主窗口
    hwnd_utils.restore_window(main_hwnd)


def kill_sw_multiple_processes(sw):
    """清理多开器的进程"""
    print("清理多余多开器窗口...")
    # 遍历所有的进程
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # 检查进程名是否以"WeChatMultiple_"开头
            if proc.name() and proc.name().startswith(f'{sw}Multiple_'):
                proc.kill()
                print(f"Killed process tree for {proc.name()} (PID: {proc.pid})")

        except Exception as e:
            logger.error(e)
    print(f"清理{sw}Multiple_***子程序完成!")


def get_mutex_dict(sw):
    """拿到当前时间下系统中所有微信进程的互斥体情况"""
    print("获取互斥体情况...")
    executable, = subfunc_file.get_details_from_remote_setting_json(sw, executable=None)
    if executable is None:
        return dict()
    pids = process_utils.get_process_ids_by_name(executable)
    print(f"获取到的{sw}进程列表：{pids}")
    has_mutex_dict = dict()
    for pid in pids:
        # 没有在all_wechat节点中，则这个是尚未判断的，默认有互斥体
        has_mutex, = subfunc_file.get_sw_acc_data(sw, Keywords.PID_MUTEX, **{f"{pid}": True})
        if has_mutex:
            subfunc_file.update_sw_acc_data(sw, Keywords.PID_MUTEX, **{f"{pid}": True})
            has_mutex_dict.update({pid: has_mutex})
    print(f"获取互斥体情况完成!互斥体列表：{has_mutex_dict}")
    return has_mutex_dict


def open_sw(sw, status, has_mutex_dictionary=None):
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
    wechat_path = func_setting.get_sw_install_path(sw)
    executable_name, lock_handles, cfg_handles = subfunc_file.get_details_from_remote_setting_json(
        sw, executable=None, lock_handle_regex_list=None, cfg_handle_regex_list=None)
    if not wechat_path:
        return None

    if status == "已开启":
        print(f"当前是全局多开模式")
        multiple_mode = "全局多开"
        create_process_without_admin(wechat_path)
        time.sleep(0.1)
    else:
        # 获取当前选择的多开子程序
        multiple_mode = subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, 'rest_mode')
        # ————————————————————————————————WeChatMultiple_Anhkgg.exe————————————————————————————————
        if multiple_mode == "WeChatMultiple_Anhkgg.exe":
            sub_exe_process = create_process_without_admin(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{multiple_mode}",
                creation_flags=subprocess.CREATE_NO_WINDOW
            )
        # ————————————————————————————————WeChatMultiple_wfql.exe————————————————————————————————
        elif multiple_mode == "WeChatMultiple_wfql.exe":
            sub_exe_process = create_process_without_admin(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{multiple_mode}",
                creation_flags=subprocess.CREATE_NO_WINDOW
            )
        # ————————————————————————————————WeChatMultiple_lyie15.exe————————————————————————————————
        elif multiple_mode == "WeChatMultiple_lyie15.exe":
            sub_exe_process = create_process_without_admin(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{multiple_mode}"
            )
            sub_exe_hwnd = hwnd_utils.wait_open_to_get_hwnd("WTWindow", 8)
            print(f"子程序窗口：{sub_exe_hwnd}")
            if sub_exe_hwnd:
                button_handle = hwnd_utils.get_child_hwnd_list_of_(
                    sub_exe_hwnd
                )[1]
                if button_handle:
                    button_details = hwnd_utils.get_hwnd_details_of_(button_handle)
                    button_cx = int(button_details["width"] / 2)
                    button_cy = int(button_details["height"] / 2)
                    hwnd_utils.do_click_in_wnd(button_handle, button_cx, button_cy)
        # ————————————————————————————————handle————————————————————————————————
        elif multiple_mode == "handle":
            success_lists = handle_utils.close_sw_mutex_by_handle(
                Config.HANDLE_EXE_PATH, executable_name, lock_handles)
            if success_lists:
                # 更新 has_mutex 为 False 并保存
                print(f"成功关闭{success_lists}：{time.time() - start_time:.4f}秒")

            # 所有操作完成后，执行创建进程的操作
            print(f"打开：{wechat_path}")
            create_process_without_admin(wechat_path, None)
        # ————————————————————————————————python[强力]————————————————————————————————
        elif multiple_mode == "python[S]":
            pids = process_utils.get_process_ids_by_name(executable_name)
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
        elif multiple_mode == "python":
            if len(has_mutex_dictionary) > 0:
                print(has_mutex_dictionary)
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

    return sub_exe_process, multiple_mode


def get_login_size(tab, status):
    redundant_wnd_list, login_wnd_class, executable_name, cfg_handles = subfunc_file.get_details_from_remote_setting_json(
        tab, redundant_wnd_class=None, login_wnd_class=None, executable=None, cfg_handle_regex_list=None)
    print(login_wnd_class)
    hwnd_utils.close_all_by_wnd_classes(redundant_wnd_list)

    # 关闭配置文件锁
    handle_utils.close_sw_mutex_by_handle(
        Config.HANDLE_EXE_PATH, executable_name, cfg_handles)

    kill_sw_multiple_processes(tab)
    has_mutex_dict = get_mutex_dict(tab)
    sub_exe_process, sub_exe = open_sw(tab, status, has_mutex_dict)
    wechat_hwnd = hwnd_utils.wait_open_to_get_hwnd(login_wnd_class, timeout=8)
    if wechat_hwnd:
        print(f"打开了登录窗口{wechat_hwnd}")
        if sub_exe_process:
            sub_exe_process.terminate()
        time.sleep(2)
        login_wnd_details = hwnd_utils.get_hwnd_details_of_(wechat_hwnd)
        login_wnd = login_wnd_details["window"]
        login_width = login_wnd_details["width"]
        login_height = login_wnd_details["height"]
        logger.info(f"获得了窗口尺寸：{login_width}, {login_height}")
        login_wnd.close()
        return login_width, login_height


def create_process_without_admin(executable, args=None, creation_flags=subprocess.CREATE_NO_WINDOW):
    if (sys_utils.get_sys_major_version_name() == "win11" or
            sys_utils.get_sys_major_version_name() == "win10"):
        # return process_utils.create_process_with_logon(
        #     "xxxxx@xx.com", "xxxxxxxxx", executable, args, creation_flags)
        # return process_utils.create_process_with_task_scheduler(executable, args)  # 会继承父进程的权限，废弃
        # return process_utils.create_process_with_re_token_default(executable, args, creation_flags)
        return process_utils.create_process_with_re_token_handle(executable, args, creation_flags)
        # return process_utils.create_process_for_win7(executable, args, creation_flags)
    else:
        return process_utils.create_process_for_win7(executable, args, creation_flags)


def logging_in_listener():
    handles = set()
    flag = False

    while True:
        handle = win32gui.FindWindow("WeChatLoginWndForPC", None)
        if handle:
            handles.add(handle)
            flag = True
        print(f"当前有微信窗口：{handles}")
        for handle in list(handles):
            if win32gui.IsWindow(handle):
                wechat_wnd_details = hwnd_utils.get_hwnd_details_of_(handle)
                wechat_width = wechat_wnd_details["width"]
                wechat_height = wechat_wnd_details["height"]
                hwnd_utils.do_click_in_wnd(handle, int(wechat_width * 0.5), int(wechat_height * 0.75))
            else:
                handles.remove(handle)

        time.sleep(5)
        # 检测到出现开始，直接列表再次为空结束
        if flag and len(handles) == 0:
            return
