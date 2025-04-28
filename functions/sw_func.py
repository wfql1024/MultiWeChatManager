import glob
import os
import shutil
import subprocess
import sys
import threading
import time
import winreg
from tkinter import messagebox
from typing import Union, Tuple, Optional

import psutil
import win32com
import win32con
import win32gui
import winshell
from win32com.client import Dispatch

from functions import subfunc_file
from public_class.enums import LocalCfg, SW, AccKeys, MultirunMode, RemoteCfg
from public_class.global_members import GlobalMembers
from resources import Config
from utils import file_utils, process_utils, pywinhandle, handle_utils, hwnd_utils, sys_utils, image_utils
from utils.file_utils import DllUtils
from utils.hwnd_utils import TkWndUtils
from utils.logger_utils import mylogger as logger


class SwInfoFunc:
    @staticmethod
    def identify_dll(sw, mode, dll_dir):
        """检查当前的dll状态，判断是否为全局多开或者不可用"""
        # 条件检查
        config_data = subfunc_file.read_remote_cfg_in_rules()
        if not config_data:
            return None, "错误：没有数据"
        patch_dll, ver_dict = subfunc_file.get_details_from_remote_setting_json(sw, patch_dll=None, **{mode: None})
        if patch_dll is None or ver_dict is None:
            return None, f"错误：{mode}平台未适配"
        ver_dict = config_data.get(sw, {}).get(mode, None)
        dll_path = os.path.join(dll_dir, patch_dll).replace("\\", "/")
        tag, msg, _, _ = SwInfoUtils.identify_dll_of_ver_by_dict(ver_dict, dll_path)
        return tag, msg

    @staticmethod
    def get_sw_install_path(sw: str, ignore_local_record=False) -> Union[None, str]:
        """
        获取微信安装路径
        :param sw: 平台
        :param ignore_local_record: 是否忽略本地记录
        :return: 路径
        """
        print("获取安装路径...")
        _, _, result = SwInfoUtils.try_get_path(sw, LocalCfg.INST_PATH, ignore_local_record)
        return result

    @staticmethod
    def get_sw_data_dir(sw: str, ignore_local_record=False):
        """
        获取微信数据路径
        :param sw: 平台
        :param ignore_local_record: 是否忽略本地记录
        :return: 路径
        """
        print("获取数据存储路径...")
        _, _, result = SwInfoUtils.try_get_path(sw, LocalCfg.DATA_DIR, ignore_local_record)
        return result

    @staticmethod
    def get_sw_dll_dir(sw: str, ignore_local_record=False):
        """获取微信dll所在文件夹"""
        print("获取dll目录...")
        _, _, result = SwInfoUtils.try_get_path(sw, LocalCfg.DLL_DIR, ignore_local_record)
        return result

    @staticmethod
    def get_sw_inst_path_and_ver(sw: str, ignore_local_record=False):
        """获取当前使用的版本号"""
        # print(sw)
        install_path = SwInfoFunc.get_sw_install_path(sw, ignore_local_record)
        # print(install_path)
        if install_path is not None:
            if os.path.exists(install_path):
                return install_path, file_utils.get_file_version(install_path)
            return install_path, None
        return None, None


class SwOperator:
    @staticmethod
    def close_classes_but_sw_main_wnd(wnd_classes, sw):
        """关闭某些类名的窗口，但排除主窗口"""
        if wnd_classes is None:
            return
        if len(wnd_classes) == 0:
            return
        for class_name in wnd_classes:
            try:
                while True:
                    hwnd = win32gui.FindWindow(class_name, None)
                    if hwnd:
                        print(hwnd)
                        if not SwOperatorUtils.is_hwnd_a_main_wnd_of_sw(hwnd, sw):
                            print("这个需要关闭")
                            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                            time.sleep(0.5)  # 等待窗口关闭
                    else:
                        print(f"已清理所有{class_name}窗口！")
                        break
            except Exception as ex:
                logger.error(ex)

    @staticmethod
    def switch_dll(sw, mode, dll_dir) -> Tuple[Optional[bool], str]:
        """
        切换全局多开状态
        :param sw: 平台
        :param mode: 修改的模式
        :param dll_dir: dll目录
        :return: 成功与否，提示信息
        """
        if mode == RemoteCfg.MULTI:
            mode_text = "全局多开"
        elif mode == RemoteCfg.REVOKE:
            mode_text = "防撤回"
        else:
            return False, "未知模式"

        config_data = subfunc_file.read_remote_cfg_in_rules()
        if not config_data:
            return False, "没有数据"
        executable, = subfunc_file.get_details_from_remote_setting_json(sw, executable=None)
        if executable is None:
            return False, "该平台暂未适配"
        # 提醒用户手动终止微信进程
        answer = SwOperator._ask_for_manual_terminate_or_force(executable)
        if answer is not True:
            return False, "用户取消操作"

        # 条件检查
        patch_dll, = subfunc_file.get_details_from_remote_setting_json(sw, patch_dll=None)
        if patch_dll is None:
            return False, "该平台未适配"
        dll_path = os.path.join(dll_dir, patch_dll).replace("\\", "/")
        ver_dict = config_data.get(sw, {}).get(mode, None)
        # 定义目标路径和文件名
        tag, msg, original_patterns, modified_patterns = SwInfoUtils.identify_dll_of_ver_by_dict(
            ver_dict, dll_path)
        dll_path = os.path.join(dll_dir, patch_dll)
        try:
            if tag is True:
                print(f"当前：{mode}已开启")
                success = DllUtils.batch_atomic_replace_hex_patterns(
                    dll_path, (modified_patterns, original_patterns))
                if success:
                    return True, f"成功关闭:{mode_text}"

            elif tag is False:
                print(f"当前：{mode}未开启")
                SwOperator._backup_dll(sw, dll_dir)

                success = DllUtils.batch_atomic_replace_hex_patterns(
                    dll_path, (original_patterns, modified_patterns))
                if success:
                    return True, f"成功开启:{mode_text}"
            return False, f"切换{mode_text}失败！请稍后重试！"
        except (psutil.AccessDenied, PermissionError, Exception) as e:
            error_msg = {
                PermissionError: "权限不足，无法修改 DLL 文件。",
                psutil.AccessDenied: "无法终止微信进程，请以管理员身份运行程序。",
                Exception: "发生错误。"
            }.get(type(e), "发生未知错误。")
            logger.error(f"切换{mode_text}时发生错误: {str(e)}")
            return False, f"切换{mode_text}时发生错误: {str(e)}\n{error_msg}"

    @staticmethod
    def _ask_for_manual_terminate_or_force(executable):
        processes = []
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.name().lower() == executable.lower():
                processes.append(proc)
        if processes:
            answer = messagebox.askokcancel(
                "警告",
                f"检测到正在使用{executable}。该操作需要退出进程，请先手动退出，否则将会强制关闭。是否继续？"
            )
            if answer is not True:
                return

            still_running = process_utils.try_terminate_executable(executable)
            if len(still_running) != 0:
                messagebox.showerror("错误", f"无法终止微信进程：{still_running}")
                return False
            return True

        return True

    @staticmethod
    def _backup_dll(sw, dll_dir):
        """备份当前的dll"""
        # 获取桌面路径
        desktop_path = winshell.desktop()

        patch_dll, = subfunc_file.get_details_from_remote_setting_json(sw, patch_dll=None)
        dll_path = os.path.join(dll_dir, patch_dll)

        bak_path = os.path.join(dll_dir, f"{patch_dll}.bak")
        bak_desktop_path = os.path.join(desktop_path, f"{patch_dll}.bak")
        curr_ver = file_utils.get_file_version(dll_path)
        not_same_version = True
        if os.path.exists(bak_path):
            not_same_version = file_utils.get_file_version(bak_path) != curr_ver

        if not os.path.exists(bak_path) or (
                os.path.exists(bak_path) and not_same_version):
            print("没有备份")
            messagebox.showinfo("提醒",
                                "当前是您该版本首次切换模式，已将原本的WeChatWin.dll拷贝为WeChatWin_bak.dll，并也拷贝到桌面，可另外备份保存。")
            shutil.copyfile(dll_path, bak_path)
            shutil.copyfile(dll_path, bak_desktop_path)

    @staticmethod
    def thread_to_manual_login(sw):
        threading.Thread(
            target=SwOperator._manual_login,
            args=(sw,)
        ).start()

    @staticmethod
    def _manual_login(sw):
        """
        根据状态进行手动登录过程
        :param sw: 选择的软件标签
        :return: 成功与否
        """
        root_class = GlobalMembers.root_class
        root = root_class.root
        acc_tab_ui = root_class.acc_tab_ui

        # 初始化操作：清空闲置的登录窗口、多开器，清空并拉取各账户的登录和互斥体情况
        start_time = time.time()
        redundant_wnd_list, login_wnd_class, executable_name, cfg_handles = subfunc_file.get_details_from_remote_setting_json(
            sw, redundant_wnd_class=None, login_wnd_class=None, executable=None, cfg_handle_regex_list=None)
        if redundant_wnd_list is None or login_wnd_class is None or cfg_handles is None or executable_name is None:
            messagebox.showinfo("错误", "尚未适配！")
            return

        # hwnd_utils.close_all_by_wnd_classes(redundant_wnd_list)
        # 关闭配置文件锁
        handle_utils.close_sw_mutex_by_handle(
            Config.HANDLE_EXE_PATH, executable_name, cfg_handles)
        SwOperator.kill_sw_multiple_processes(sw)
        time.sleep(0.5)
        subfunc_file.clear_some_acc_data(sw, AccKeys.PID_MUTEX)
        subfunc_file.update_all_acc_in_acc_json(sw)

        multirun_mode = root_class.sw_classes[sw].multirun_mode
        sub_exe_process = SwOperator.open_sw(sw, multirun_mode)
        wechat_hwnd = hwnd_utils.wait_open_to_get_hwnd(login_wnd_class, 20)
        if wechat_hwnd:
            subfunc_file.set_all_acc_values_to_false(sw)
            subfunc_file.update_statistic_data(sw, 'manual', '_', multirun_mode, time.time() - start_time)
            print(f"打开了登录窗口{wechat_hwnd}")
            if sub_exe_process:
                sub_exe_process.terminate()
            if hwnd_utils.wait_hwnd_close(wechat_hwnd, timeout=60):
                print(f"手动登录成功，正在刷新...")
            else:
                messagebox.showinfo("提示", "登录窗口长时间未操作，即将刷新列表")
        else:
            logger.warning(f"打开失败，请重试！")
            messagebox.showerror("错误", "手动登录失败，请重试")

        # 刷新菜单和窗口前置
        root_class.root.after(0, acc_tab_ui.refresh_frame, sw)
        TkWndUtils.bring_wnd_to_front(root, root)

    @staticmethod
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

    @staticmethod
    def _organize_sw_mutex_dict(sw):
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

    @staticmethod
    def open_sw(sw, multirun_mode):
        """
        根据状态以不同方式打开微信
        :param sw: 选择软件标签
        :param multirun_mode: 多开模式
        :return: 微信窗口句柄
        """
        print(f"进入了打开微信的方法...")
        sub_exe_process = None
        wechat_path = SwInfoFunc.get_sw_install_path(sw)
        if not wechat_path:
            return None

        if multirun_mode == "全局多开":
            print(f"当前是全局多开模式")
            SwOperator._create_process_without_admin(wechat_path)
        else:
            sub_exe_process = SwOperator._open_sw_without_freely_multirun(sw, multirun_mode)
        return sub_exe_process

    @staticmethod
    def _open_sw_without_freely_multirun(sw, multirun_mode):
        """非全局多开模式下打开微信"""
        start_time = time.time()
        sub_exe_process = None
        wechat_path = SwInfoFunc.get_sw_install_path(sw)
        # ————————————————————————————————WeChatMultiple_Anhkgg.exe————————————————————————————————
        if multirun_mode == "WeChatMultiple_Anhkgg.exe":
            sub_exe_process = SwOperator._create_process_without_admin(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{multirun_mode}",
                creation_flags=subprocess.CREATE_NO_WINDOW
            )
        # ————————————————————————————————WeChatMultiple_lyie15.exe————————————————————————————————
        elif multirun_mode == "WeChatMultiple_lyie15.exe":
            sub_exe_process = SwOperator._create_process_without_admin(
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
            success = SwOperator._kill_mutex_by_inner_mode(sw, multirun_mode)
            if success:
                # 更新 has_mutex 为 False 并保存
                print(f"成功关闭：{time.time() - start_time:.4f}秒")
            else:
                print(f"关闭互斥体失败！")
            SwOperator._create_process_without_admin(wechat_path, None)

        return sub_exe_process

    @staticmethod
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

    @staticmethod
    def _kill_mutex_by_inner_mode(sw, multirun_mode):
        """关闭平台进程的所有互斥体，如果不选择python模式，则使用handle模式"""
        executable_name, lock_handles, cfg_handles = subfunc_file.get_details_from_remote_setting_json(
            sw, executable=None, lock_handle_regex_list=None, cfg_handle_regex_list=None)
        # ————————————————————————————————python————————————————————————————————
        if multirun_mode == "python":
            handle_regex_list, = subfunc_file.get_details_from_remote_setting_json(sw, lock_handle_regex_list=None)
            handle_names = [handle["handle_name"] for handle in handle_regex_list]
            has_mutex_dict = SwOperator._organize_sw_mutex_dict(sw)
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

    @staticmethod
    def kill_mutex_of_pid(sw, acc):
        pid, = subfunc_file.get_sw_acc_data(sw, acc, pid=None)
        if pid is None:
            return False
        handle_regex_list, = subfunc_file.get_details_from_remote_setting_json(sw, lock_handle_regex_list=None)
        handle_names = [handle["handle_name"] for handle in handle_regex_list]
        success = pywinhandle.close_handles(
            pywinhandle.find_handles(
                [pid],
                handle_names
            )
        )
        print(f"kill mutex: {success}")
        if success:
            subfunc_file.update_sw_acc_data(sw, acc, has_mutex=False)
        return success

    @staticmethod
    def get_login_size(sw, multirun_mode):
        redundant_wnd_list, login_wnd_class, executable_name, cfg_handles = subfunc_file.get_details_from_remote_setting_json(
            sw, redundant_wnd_class=None, login_wnd_class=None, executable=None, cfg_handle_regex_list=None)
        print(login_wnd_class)
        SwOperator.close_classes_but_sw_main_wnd(redundant_wnd_list, sw)

        # 关闭配置文件锁
        handle_utils.close_sw_mutex_by_handle(
            Config.HANDLE_EXE_PATH, executable_name, cfg_handles)

        SwOperator.kill_sw_multiple_processes(sw)
        sub_exe_process = SwOperator.open_sw(sw, multirun_mode)
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

    @staticmethod
    def _create_process_without_admin(executable, args=None, creation_flags=subprocess.CREATE_NO_WINDOW):
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

    @staticmethod
    def open_config_file(sw):
        """打开配置文件夹"""
        data_path = SwInfoFunc.get_sw_data_dir(sw)
        if os.path.exists(data_path):
            config_path_suffix, = subfunc_file.get_details_from_remote_setting_json(sw, config_path_suffix=None)
            if config_path_suffix is None:
                messagebox.showinfo("提醒", f"{sw}平台还没有适配")
                return
            config_path = os.path.join(data_path, config_path_suffix)
            if os.path.exists(config_path):
                os.startfile(config_path)

    @staticmethod
    def clear_config_file(sw, after):
        """清除配置文件"""
        confirm = messagebox.askokcancel(
            "确认清除",
            f"该操作将会清空{sw}登录配置文件，请确认是否需要清除？"
        )
        if confirm:
            data_path = SwInfoFunc.get_sw_data_dir(sw)
            config_path_suffix, config_file_list = subfunc_file.get_details_from_remote_setting_json(
                sw, config_path_suffix=None, config_file_list=None)
            if (config_path_suffix is None or config_file_list is None or
                    not isinstance(config_file_list, list) or len(config_file_list) == 0):
                messagebox.showinfo("提醒", f"{sw}平台还没有适配")
                return

            files_to_delete = []

            for file in config_file_list:
                config_path = os.path.join(data_path, str(config_path_suffix))
                # 获取所有 `.data` 文件，除了 `config.data`
                file_suffix = file.split(".")[-1]
                data_files = glob.glob(os.path.join(config_path, f'*.{file_suffix}').replace("\\", "/"))
                files_to_delete.extend([f for f in data_files if not os.path.split(config_path) == config_path_suffix])
                # print(file_suffix)
                # print(data_files)
                # print(files_to_delete)
            if len(files_to_delete) > 0:
                # 删除这些文件
                try:
                    file_utils.move_files_to_recycle_bin(files_to_delete)
                    print(f"已删除: {files_to_delete}")
                except Exception as e:
                    logger.error(f"无法删除 {files_to_delete}: {e}")
            after(message=f"清除{sw}登录配置完成！")

    @staticmethod
    def open_dll_dir(sw):
        """打开注册表所在文件夹，并将光标移动到文件"""
        dll_dir = SwInfoFunc.get_sw_dll_dir(sw)
        if os.path.exists(dll_dir):
            dll_file, = subfunc_file.get_details_from_remote_setting_json(sw, patch_dll=None)
            if dll_file is None:
                messagebox.showinfo("提醒", f"{sw}平台还没有适配")
                return
            # 打开文件夹
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.CurrentDirectory = dll_dir
            shell.Run(f'explorer /select,{dll_file}')

    @staticmethod
    def create_multiple_lnk(sw, status, after):
        """
        创建快捷多开
        :return: 是否成功
        """

        def get_all_configs():
            """
            获取已经配置的账号列表
            :return: 已经配置的账号列表
            """
            target_path = os.path.join(SwInfoFunc.get_sw_data_dir(sw), 'All Users', 'config')
            all_configs = []
            # 遍历目标目录中的所有文件
            for file_name in os.listdir(target_path):
                # 只处理以 .data 结尾的文件
                if file_name.endswith('.data') and file_name != 'config.data':
                    # 获取不含扩展名的文件名
                    file_name_without_ext = os.path.splitext(file_name)[0]
                    # 添加到列表中
                    all_configs.append(file_name_without_ext)

            return all_configs

        # 获取已经配置的列表
        configured_accounts = get_all_configs()
        if len(configured_accounts) == 0:
            messagebox.showinfo("提醒", "您还没有创建过登录配置")
            return False

        for account in configured_accounts:
            # 对每一个账号进行创建
            result = SwOperator._create_lnk_for_account(sw, account, status)
            if result is False:
                continue
        after()
        print("创建快捷启动成功！")
        return True

    @staticmethod
    def _create_lnk_for_account(sw, account, multiple_status):
        """
        为账号创建快捷开启
        :param sw: 选择的软件标签
        :param account: 账号
        :param multiple_status: 是否多开状态
        :return: 是否成功
        """
        # 确保可以创建快捷启动
        data_path = SwInfoFunc.get_sw_data_dir(sw)
        wechat_path = SwInfoFunc.get_sw_install_path(sw)
        if not data_path or not wechat_path:
            messagebox.showerror("错误", "无法获取数据路径")
            return False
        avatar_path = os.path.join(Config.PROJ_USER_PATH, sw, f"{account}", f"{account}.jpg")
        if not os.path.exists(avatar_path):
            avatar_path = os.path.join(Config.PROJ_USER_PATH, "default.jpg")

        # 构建源文件和目标文件路径
        source_file = os.path.join(data_path, "All Users", "config", f"{account}.data").replace('/', '\\')
        target_file = os.path.join(data_path, "All Users", "config", "config.data").replace('/', '\\')
        close_mutex_executable = os.path.join(Config.PROJ_EXTERNAL_RES_PATH, "WeChatMultiple_Anhkgg.exe")
        if multiple_status == "已开启":
            close_mutex_code = ""
            prefix = "[要开全局] - "
            exe_path = wechat_path
        else:
            close_mutex_code = \
                f"""
                            \n{close_mutex_executable}
                        """
            prefix = ""
            # 判断环境
            if getattr(sys, 'frozen', False):  # 打包环境
                exe_path = sys.executable  # 当前程序的 exe
            else:  # PyCharm 或其他开发环境
                exe_path = close_mutex_executable  # 使用 handle_path

        bat_content = f"""
                    @echo off
                    chcp 65001
                    REM 复制配置文件
                    copy "{source_file}" "{target_file}"
                    if errorlevel 1 (
                        echo 复制配置文件失败
                        exit /b 1
                    )
                    echo 复制配置文件成功

                    REM 根据状态启动微信
                    @echo off{close_mutex_code}
                    cmd /u /c "start "" "{wechat_path}""
                    if errorlevel 1 (
                    echo 启动微信失败，请检查路径是否正确。
                    pause
                    exit /b 1
                    )
                    """

        # 确保路径存在
        account_file_path = os.path.join(Config.PROJ_USER_PATH, sw, f'{account}')
        if not os.path.exists(account_file_path):
            os.makedirs(account_file_path)
        # 保存为批处理文件
        bat_file_path = os.path.join(Config.PROJ_USER_PATH, sw, f'{account}', f'{prefix}{account}.bat')
        # 以带有BOM的UTF-8格式写入bat文件
        with open(bat_file_path, 'w', encoding='utf-8-sig') as bat_file:
            bat_file.write(bat_content)
        print(f"批处理文件已生成: {bat_file_path}")

        # 获取桌面路径
        desktop = winshell.desktop()
        # 获取批处理文件名并去除后缀
        bat_file_name = os.path.splitext(os.path.basename(bat_file_path))[0]
        # 构建快捷方式路径
        shortcut_path = os.path.join(desktop, f"{bat_file_name}.lnk")

        # 图标文件路径
        acc_dir = os.path.join(Config.PROJ_USER_PATH, str(sw), f"{account}")
        exe_name = os.path.splitext(os.path.basename(exe_path))[0]

        # 步骤1：提取图标为图片
        extracted_exe_png_path = os.path.join(acc_dir, f"{exe_name}_extracted.png")
        image_utils.extract_icon_to_png(exe_path, extracted_exe_png_path)

        # 步骤2：合成图片
        ico_jpg_path = os.path.join(acc_dir, f"{account}_{exe_name}.png")
        image_utils.add_diminished_se_corner_mark_to_image(avatar_path, extracted_exe_png_path, ico_jpg_path)

        # 步骤3：对图片转格式
        ico_path = os.path.join(acc_dir, f"{account}_{exe_name}.ico")
        image_utils.png_to_ico(ico_jpg_path, ico_path)

        # 清理临时文件
        os.remove(extracted_exe_png_path)

        # 创建快捷方式
        with winshell.shortcut(shortcut_path) as shortcut:
            shortcut.path = bat_file_path
            shortcut.working_directory = os.path.dirname(bat_file_path)
            # 修正icon_location的传递方式，传入一个包含路径和索引的元组
            shortcut.icon_location = (ico_path, 0)

        print(f"桌面快捷方式已生成: {os.path.basename(shortcut_path)}")
        return True


class SwInfoUtils:
    @staticmethod
    def is_valid_sw_path(path_type, sw, path):
        if path is None or path == "":
            return False
        print(path_type)
        if path_type == LocalCfg.INST_PATH:
            executable, = subfunc_file.get_details_from_remote_setting_json(sw, executable=None)
            path_ext = os.path.splitext(path)[1].lower()
            exe_ext = os.path.splitext(executable)[1].lower()
            return path_ext == exe_ext
        elif path_type == LocalCfg.DATA_DIR:
            suffix, = subfunc_file.get_details_from_remote_setting_json(sw, data_dir_check_suffix=None)
            return os.path.isdir(os.path.join(path, suffix))
        elif path_type == LocalCfg.DLL_DIR:
            suffix, = subfunc_file.get_details_from_remote_setting_json(sw, dll_dir_check_suffix=None)
            return os.path.isfile(os.path.join(path, suffix))

    @staticmethod
    def get_sw_install_path_from_process(sw: str) -> list:
        executable, = subfunc_file.get_details_from_remote_setting_json(sw, executable=None)
        results = []
        for process in psutil.process_iter(['name', 'exe']):
            if process.name() == executable:
                path = process.exe().replace('\\', '/')
                results.append(path)
                logger.info(f"通过查找进程方式获取了安装地址：{path}")
                break
        return results

    @staticmethod
    def get_sw_install_path_from_machine_register(sw: str) -> list:
        sub_key, executable = subfunc_file.get_details_from_remote_setting_json(
            sw, mac_reg_sub_key=None, executable=None)
        results = []
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_key)

            found_path = winreg.QueryValueEx(key, "InstallLocation")[0].replace('\\', '/')
            winreg.CloseKey(key)
            logger.info(f"通过设备注册表获取了安装地址：{found_path}")
            if found_path:
                results.append(os.path.join(found_path, executable).replace('\\', '/'))

            found_path = winreg.QueryValueEx(key, "DisplayIcon")[0].replace('\\', '/')
            winreg.CloseKey(key)
            logger.info(f"通过设备注册表获取了安装地址：{found_path}")
            if found_path:
                results.append(found_path.replace('\\', '/'))
        except Exception as e:
            logger.error(e)
        return results

    @staticmethod
    def get_sw_install_path_from_user_register(sw: str) -> list:
        sub_key, executable = subfunc_file.get_details_from_remote_setting_json(
            sw, user_reg_sub_key=None, executable=None)
        results = []
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key)
            found_path = winreg.QueryValueEx(key, "InstallPath")[0].replace('\\', '/')
            winreg.CloseKey(key)
            logger.info(f"通过用户注册表获取了安装地址：{found_path}")
            if found_path:
                results.append(os.path.join(found_path, executable).replace('\\', '/'))
        except Exception as we:
            logger.error(we)
        return results

    @staticmethod
    def get_sw_install_path_by_guess(sw: str) -> list:
        suffix, = subfunc_file.get_details_from_remote_setting_json(sw, inst_path_guess_suffix=None)
        guess_paths = [
            os.path.join(os.environ.get('ProgramFiles'), suffix).replace('\\', '/'),
            os.path.join(os.environ.get('ProgramFiles(x86)'), suffix).replace('\\', '/'),
        ]
        return guess_paths

    @staticmethod
    def get_sw_data_dir_from_user_register(sw: str) -> list:
        sub_key, dir_name = subfunc_file.get_details_from_remote_setting_json(
            sw, user_reg_sub_key=None, data_dir_name=None)
        results = []
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, "FileSavePath")
            winreg.CloseKey(key)
            value = os.path.join(value, dir_name).replace('\\', '/')
            results.append(value)
        except Exception as we:
            logger.error(we)
        return results

    @staticmethod
    def get_sw_data_dir_by_guess(sw: str) -> list:
        data_dir_name, data_dir_guess_suffix = subfunc_file.get_details_from_remote_setting_json(
            sw, data_dir_name=None, data_dir_guess_suffix=None)
        guess_paths = [
            os.path.join(os.path.expanduser('~'), 'Documents', data_dir_name).replace('\\', '/'),
        ]
        return guess_paths

    @staticmethod
    def get_sw_dll_dir_by_memo_maps(sw: str) -> list:
        dll_name, executable = subfunc_file.get_details_from_remote_setting_json(
            sw, dll_dir_check_suffix=None, executable=None)
        results = []
        pids = process_utils.get_process_ids_by_name(executable)
        if len(pids) == 0:
            logger.warning(f"没有运行该程序。")
            return []
        else:
            process_id = pids[0]
            try:
                for f in psutil.Process(process_id).memory_maps():
                    normalized_path = f.path.replace('\\', '/')
                    # print(normalized_path)
                    if normalized_path.endswith(dll_name):
                        dll_dir_path = os.path.dirname(normalized_path)
                        # print(dll_dir_path)
                        results.append(dll_dir_path)
            except psutil.AccessDenied:
                logger.error(f"无法访问进程ID为 {process_id} 的内存映射文件，权限不足。")
            except psutil.NoSuchProcess:
                logger.error(f"进程ID为 {process_id} 的进程不存在或已退出。")
            except Exception as e:
                logger.error(f"发生意外错误: {e}")
        return results

    @staticmethod
    def identify_dll_of_ver_by_dict(data, dll_path) \
            -> Tuple[Optional[bool], str, Optional[list], Optional[list]]:
        cur_sw_ver = file_utils.get_file_version(dll_path)
        ver_adaptation = data.get(cur_sw_ver, None)
        if ver_adaptation is None:
            return None, f"错误：未找到版本{cur_sw_ver}的适配", None, None

        # 一个版本可能有多个匹配，只要有一个匹配成功就返回
        for match in ver_adaptation:
            original_list = match["original"]
            modified_list = match["modified"]
            has_original_list = DllUtils.find_patterns_from_dll_in_hexadecimal(dll_path, *original_list)
            has_modified_list = DllUtils.find_patterns_from_dll_in_hexadecimal(dll_path, *modified_list)
            # list转成集合，集合中只允许有一个元素，True表示list全都是True，False表示list全都是False，其他情况不合法
            has_original_set = set(has_original_list)
            has_modified_set = set(has_modified_list)
            if len(has_original_set) != 1 or len(has_modified_set) != 1:
                continue
            all_original = True if True in has_original_set else False if False in has_original_set else None
            all_modified = True if True in has_modified_set else False if False in has_modified_set else None
            if all_original is True and all_modified is False:
                return False, "未开启", original_list, modified_list
            elif all_original is False and all_modified is True:
                return True, "已开启", original_list, modified_list
            elif all_original is True or all_modified is True:
                return None, "错误，非独一无二的特征码", None, None
        return None, "不可用", None, None

    @staticmethod
    def _create_path_finders_of_(path_tag, ignore_local_record=False) -> list:
        """定义方法列表"""
        if path_tag == LocalCfg.INST_PATH:
            return [
                SwInfoUtils.get_sw_install_path_from_process,
                ((lambda sw: []) if ignore_local_record
                 else SwInfoUtils._create_sw_method_to_get_path_from_local_record(LocalCfg.INST_PATH)),
                SwInfoUtils.get_sw_install_path_from_machine_register,
                SwInfoUtils.get_sw_install_path_from_user_register,
                SwInfoUtils.get_sw_install_path_by_guess,
            ]
        elif path_tag == LocalCfg.DATA_DIR:
            return [
                ((lambda sw: []) if ignore_local_record
                 else SwInfoUtils._create_sw_method_to_get_path_from_local_record(LocalCfg.DATA_DIR)),
                SwInfoUtils.get_sw_data_dir_from_user_register,
                SwInfoUtils.get_sw_data_dir_by_guess,
                SwInfoUtils._get_sw_data_dir_from_other_sw,
            ]
        elif path_tag == LocalCfg.DLL_DIR:
            return [
                ((lambda sw: []) if ignore_local_record
                 else SwInfoUtils._create_sw_method_to_get_path_from_local_record(LocalCfg.DLL_DIR)),
                SwInfoUtils.get_sw_dll_dir_by_memo_maps,
                SwInfoUtils._get_sw_dll_dir_by_files,
            ]
        else:
            return [
                (lambda sw: [])
            ]

    @staticmethod
    def _create_check_method_of_(path_type):
        """定义检查方法"""

        def check_sw_path_func(sw, path):
            return SwInfoUtils.is_valid_sw_path(path_type, sw, path)

        return check_sw_path_func

    @staticmethod
    def _create_sw_method_to_get_path_from_local_record(path_tag):
        """
        创建路径查找函数
        :param path_tag: 路径类型
        :return: 路径查找函数
        """

        def get_sw_path_from_local_record(sw: str) -> list:
            path = subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, path_tag)
            return [path] if path is not None else []

        return get_sw_path_from_local_record

    @staticmethod
    def try_get_path(sw: str, path_type: str, ignore_local_record) \
            -> Union[Tuple[bool, bool, Union[None, str]]]:
        """
        获取微信数据路径的结果元组
        :param ignore_local_record: 是否忽略本地记录
        :param path_type: 路径类型
        :param sw: 平台
        :return: 成功，是否改变，结果
        """
        success = False
        changed = False
        result = None

        path_finders = SwInfoUtils._create_path_finders_of_(path_type, ignore_local_record)
        check_sw_path_func = SwInfoUtils._create_check_method_of_(path_type)
        if check_sw_path_func is None:
            return success, changed, result

        # 尝试各种方法
        for index, finder in enumerate(path_finders):
            if finder is None:
                continue
            paths = finder(sw=sw)
            logger.info(f"使用{finder.__name__}方法得到{sw}的路径列表：{paths}")
            path_list = list(paths)  # 如果确定返回值是可迭代对象，强制转换为列表
            if not path_list:
                continue
            # 检验地址并退出所有循环
            for path in path_list:
                if check_sw_path_func(sw, path):
                    print(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果 {path}")
                    standardized_path = os.path.abspath(path).replace('\\', '/')
                    changed = subfunc_file.save_a_setting_and_callback(sw, path_type, standardized_path)
                    result = standardized_path
                    success = True
                    break
            if success:
                break

        return success, changed, result

    @staticmethod
    def _get_sw_data_dir_from_other_sw(sw: str) -> list:
        """通过其他软件的方式获取微信数据文件夹"""
        data_dir_name, = subfunc_file.get_details_from_remote_setting_json(
            sw, data_dir_name=None)
        paths = []
        if data_dir_name is None or data_dir_name == "":
            paths = []
        if sw == SW.WEIXIN:
            other_path = SwInfoUtils._create_sw_method_to_get_path_from_local_record(LocalCfg.DATA_DIR)(SW.WECHAT)
            if other_path and len(other_path) != 0:
                paths = [os.path.join(os.path.dirname(other_path[0]), data_dir_name).replace('\\', '/')]
            else:
                paths = []
        if sw == SW.WECHAT:
            other_path = SwInfoFunc.get_sw_data_dir(SW.WEIXIN)
            if other_path and len(other_path) != 0:
                return [os.path.join(os.path.dirname(other_path[0]), data_dir_name).replace('\\', '/')]
            else:
                return []

        return paths

    @staticmethod
    def _get_sw_dll_dir_by_files(sw: str) -> list:
        """通过文件遍历方式获取dll文件夹"""
        dll_name, = subfunc_file.get_details_from_remote_setting_json(
            sw, dll_dir_check_suffix=None)
        install_path = SwInfoFunc.get_sw_install_path(sw)
        if install_path and install_path != "":
            install_dir = os.path.dirname(install_path)
        else:
            return []

        version_folders = []
        # 遍历所有文件及子文件夹
        for root, dirs, files in os.walk(install_dir):
            if dll_name in files:
                version_folders.append(root)  # 将包含WeChatWin.dll的目录添加到列表中

        if not version_folders:
            return []

        # 只有一个文件夹，直接返回
        if len(version_folders) == 1:
            dll_dir = version_folders[0].replace('\\', '/')
            print(f"只有一个文件夹：{dll_dir}")
            return [dll_dir]

        return [file_utils.get_newest_full_version_dir(version_folders)]


class SwOperatorUtils:
    @staticmethod
    def is_hwnd_a_main_wnd_of_sw(hwnd, sw):
        # TODO: 需要优化
        """检测窗口是否是某个平台的主窗口"""
        executable, = subfunc_file.get_details_from_remote_setting_json(sw, executable=None)
        # 判断hwnd是否属于指定的程序
        pid = hwnd_utils.get_hwnd_details_of_(hwnd)["pid"]
        if psutil.Process(pid).exe() != executable:
            return False
        expected_class, = subfunc_file.get_details_from_remote_setting_json(sw, main_wnd_class=None)
        class_name = win32gui.GetClassName(hwnd)
        # print(expected_class, class_name)
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

    pass
