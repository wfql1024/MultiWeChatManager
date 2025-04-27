import subprocess
import time

import psutil
import win32con
import win32gui

import func_setting
from functions import subfunc_file
from public_class.enums import SW, MultirunMode, AccKeys
from resources import Config
from utils import hwnd_utils, process_utils, pywinhandle, handle_utils, sys_utils
from utils.logger_utils import mylogger as logger


# TODO: 完善4.0的python模式√


def is_hwnd_a_main_wnd_of_acc_on_sw(hwnd, sw, acc):
    """检测窗口是否是某个账号的主窗口"""
    pid, = subfunc_file.get_sw_acc_data(sw, acc, pid=None)
    if pid is None:
        return False
    # 判断hwnd是否属于指定的pid
    if hwnd_utils.get_hwnd_details_of_(hwnd)["pid"] != pid:
        return False
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


def organize_sw_mutex_dict(sw):
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
        has_mutex, = subfunc_file.get_sw_acc_data(sw, AccKeys.PID_MUTEX, **{f"{pid}": True})
        if has_mutex:
            subfunc_file.update_sw_acc_data(sw, AccKeys.PID_MUTEX, **{f"{pid}": True})
            has_mutex_dict.update({pid: has_mutex})
    print(f"获取互斥体情况完成!互斥体列表：{has_mutex_dict}")
    return has_mutex_dict


def open_sw(sw, multirun_mode):
    """
    根据状态以不同方式打开微信
    :param sw: 选择软件标签
    :param multirun_mode: 多开模式
    :return: 微信窗口句柄
    """
    print(f"进入了打开微信的方法...")
    sub_exe_process = None
    wechat_path = func_setting.get_sw_install_path(sw)
    if not wechat_path:
        return None

    if multirun_mode == "全局多开":
        print(f"当前是全局多开模式")
        create_process_without_admin(wechat_path)
    else:
        sub_exe_process = _open_sw_without_freely_multirun(sw, multirun_mode)
    return sub_exe_process


def _open_sw_without_freely_multirun(sw, multirun_mode):
    """非全局多开模式下打开微信"""
    start_time = time.time()
    sub_exe_process = None
    wechat_path = func_setting.get_sw_install_path(sw)
    # ————————————————————————————————WeChatMultiple_Anhkgg.exe————————————————————————————————
    if multirun_mode == "WeChatMultiple_Anhkgg.exe":
        sub_exe_process = create_process_without_admin(
            f"{Config.PROJ_EXTERNAL_RES_PATH}/{multirun_mode}",
            creation_flags=subprocess.CREATE_NO_WINDOW
        )
    # ————————————————————————————————WeChatMultiple_lyie15.exe————————————————————————————————
    elif multirun_mode == "WeChatMultiple_lyie15.exe":
        sub_exe_process = create_process_without_admin(
            f"{Config.PROJ_EXTERNAL_RES_PATH}/{multirun_mode}"
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
    elif multirun_mode == MultirunMode.HANDLE or multirun_mode == MultirunMode.PYTHON:
        success = kill_mutex_by_inner_mode(sw, multirun_mode)
        if success:
            # 更新 has_mutex 为 False 并保存
            print(f"成功关闭：{time.time() - start_time:.4f}秒")
        else:
            print(f"关闭互斥体失败！")
        create_process_without_admin(wechat_path, None)

    return sub_exe_process


def kill_mutex_by_forced_inner_mode(sw, multirun_mode):
    executable_name, lock_handles, cfg_handles = subfunc_file.get_details_from_remote_setting_json(
        sw, executable=None, lock_handle_regex_list=None, cfg_handle_regex_list=None)
    # ————————————————————————————————python[强力]————————————————————————————————
    if multirun_mode == MultirunMode.PYTHON:
        pids = process_utils.get_process_ids_by_name(executable_name)
        handle_regex_list, = subfunc_file.get_details_from_remote_setting_json(sw, lock_handle_regex_list=None)
        handle_names = [handle["handle_name"] for handle in handle_regex_list]
        if len(pids) > 0:
            success = pywinhandle.close_handles(
                pywinhandle.find_handles(
                    pids,
                    handle_names
                )
            )
            return success
    # ————————————————————————————————handle————————————————————————————————
    else:
        success, success_lists = handle_utils.close_sw_mutex_by_handle(
            Config.HANDLE_EXE_PATH, executable_name, lock_handles)
        if len(success_lists) > 0:
            print(f"成功关闭：{success_lists}")
        return success


def kill_mutex_by_inner_mode(sw, multirun_mode):
    """关闭平台进程的所有互斥体，如果不选择python模式，则使用handle模式"""
    executable_name, lock_handles, cfg_handles = subfunc_file.get_details_from_remote_setting_json(
        sw, executable=None, lock_handle_regex_list=None, cfg_handle_regex_list=None)
    # ————————————————————————————————python————————————————————————————————
    if multirun_mode == "python":
        handle_regex_list, = subfunc_file.get_details_from_remote_setting_json(sw, lock_handle_regex_list=None)
        handle_names = [handle["handle_name"] for handle in handle_regex_list]
        has_mutex_dict = organize_sw_mutex_dict(sw)
        if len(has_mutex_dict) > 0:
            print("互斥体列表：", has_mutex_dict)
            pids, values = zip(*has_mutex_dict.items())
            success = pywinhandle.close_handles(
                pywinhandle.find_handles(
                    pids,
                    handle_names
                )
            )
            return success
    # ————————————————————————————————handle————————————————————————————————
    else:
        success, success_lists = handle_utils.close_sw_mutex_by_handle(
            Config.HANDLE_EXE_PATH, executable_name, lock_handles)
        if len(success_lists) > 0:
            print(f"成功关闭：{success_lists}")
        return success


def kill_mutex_of_pid(sw, pid):
    handle_regex_list, = subfunc_file.get_details_from_remote_setting_json(sw, lock_handle_regex_list=None)
    handle_names = [handle["handle_name"] for handle in handle_regex_list]
    success = pywinhandle.close_handles(
        pywinhandle.find_handles(
            [pid],
            handle_names
        )
    )
    return success


def get_login_size(sw, multirun_mode):
    redundant_wnd_list, login_wnd_class, executable_name, cfg_handles = subfunc_file.get_details_from_remote_setting_json(
        sw, redundant_wnd_class=None, login_wnd_class=None, executable=None, cfg_handle_regex_list=None)
    print(login_wnd_class)
    hwnd_utils.close_all_by_wnd_classes(redundant_wnd_list)

    # 关闭配置文件锁
    handle_utils.close_sw_mutex_by_handle(
        Config.HANDLE_EXE_PATH, executable_name, cfg_handles)

    kill_sw_multiple_processes(sw)
    sub_exe_process = open_sw(sw, multirun_mode)
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
    """在管理员身份的程序中，以非管理员身份创建进程，即打开的子程序不得继承父进程的权限"""
    cur_sys_ver = sys_utils.get_sys_major_version_name()
    if cur_sys_ver == "win11" or cur_sys_ver == "win10":
        # return process_utils.create_process_with_logon(
        #     "xxxxx@xx.com", "xxxx", executable, args, creation_flags)  # 使用微软账号登录，下策
        # return process_utils.create_process_with_task_scheduler(executable, args)  # 会继承父进程的权限，废弃
        # # 拿默认令牌通过资源管理器身份创建
        # return process_utils.create_process_with_re_token_default(executable, args, creation_flags)
        # # 拿Handle令牌通过资源管理器身份创建
        return process_utils.create_process_with_re_token_handle(executable, args, creation_flags)
    else:
        return process_utils.create_process_for_win7(executable, args, creation_flags)
