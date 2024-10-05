import glob
import os
import shutil
import sys
from tkinter import messagebox
from typing import Tuple, Any

import win32com
import winshell
from win32com.client import Dispatch

from functions import func_setting
from resources import Config
from utils import image_utils


def open_user_file():
    """打开用户文件夹"""
    if not os.path.exists(Config.PROJ_USER_PATH):
        os.makedirs(Config.PROJ_USER_PATH)
    os.startfile(Config.PROJ_USER_PATH)


def clear_user_file(after):
    """清除用户文件夹"""
    confirm = messagebox.askokcancel(
        "确认清除",
        "该操作将会清空头像、昵称、配置的路径等数据，请确认是否需要清除？"
    )
    directory_path = Config.PROJ_USER_PATH
    if confirm:
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        messagebox.showinfo("重置完成", "目录已成功重置。")
        after()


def open_config_file():
    """打开配置文件夹"""
    data_path = func_setting.get_wechat_data_path()
    if os.path.exists(data_path):
        config_path = os.path.join(data_path, "All Users", "config")
        if os.path.exists(config_path):
            os.startfile(config_path)


def clear_config_file(after):
    """清除配置文件"""
    confirm = messagebox.askokcancel(
        "确认清除",
        "该操作将会清空登录配置文件，请确认是否需要清除？"
    )
    if confirm:
        data_path = func_setting.get_wechat_data_path()
        config_path = os.path.join(data_path, "All Users", "config")
        # 获取所有 `.data` 文件，除了 `config.data`
        data_files = glob.glob(os.path.join(config_path, "*.data"))
        files_to_delete = [file for file in data_files if not file.endswith("config.data")]
        if len(files_to_delete) > 0:
            # 删除这些文件
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    print(f"已删除: {file_path}")
                except Exception as e:
                    print(f"无法删除 {file_path}: {e}")
            after()


def clear_statistic_data(after):
    """清除统计数据"""
    confirm = messagebox.askokcancel(
        "确认清除",
        "该操作将会清空统计的数据，请确认是否需要清除？"
    )
    if confirm:
        file_path = Config.STATISTIC_JSON_PATH
        try:
            os.remove(file_path)
            print(f"已删除: {file_path}")
        except Exception as e:
            print(f"无法删除 {file_path}: {e}")
        after()


def open_dll_dir_path():
    """打开注册表所在文件夹，并将光标移动到文件"""
    dll_dir_path = func_setting.get_wechat_dll_dir_path()
    if os.path.exists(dll_dir_path):
        # 获取文件夹路径
        folder_path = os.path.dirname(dll_dir_path)

        # 打开文件夹
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.CurrentDirectory = dll_dir_path
        shell.Run(f'explorer /select,"WeChatWin.dll"')


def create_app_lnk():
    """创建程序快捷方式"""
    # 当前是打包后的环境
    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
    else:
        exe_path = os.path.abspath(r'./dist/微信多开管理器/微信多开管理器.exe')

    exe_dir = os.path.dirname(exe_path)
    exe_name = os.path.basename(exe_path)

    # 创建常规版本快捷方式
    shortcut_name = os.path.splitext(exe_name)[0]  # 去掉 .exe 后缀
    desktop = winshell.desktop()
    shortcut_path = os.path.join(desktop, f"{shortcut_name}.lnk")

    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = exe_path
    shortcut.WorkingDirectory = exe_dir
    shortcut.IconLocation = exe_path
    shortcut.save()

    # 打印常规版本创建成功信息
    print(f"常规版快捷方式已创建： {shortcut_path}")

    # 创建_调试版快捷方式，添加 --debug 参数
    debug_shortcut_path = os.path.join(desktop, f"{shortcut_name}_调试版.lnk")
    debug_shortcut = shell.CreateShortCut(debug_shortcut_path)
    debug_shortcut.TargetPath = exe_path
    debug_shortcut.Arguments = "--debug"  # 添加调试参数
    debug_shortcut.WorkingDirectory = exe_dir
    debug_shortcut.IconLocation = exe_path
    debug_shortcut.save()

    # 打印调试版创建成功信息
    print(f"调试版快捷方式已创建： {debug_shortcut_path}")


def create_lnk_for_account(account, multiple_status):
    """
    为账号创建快捷开启
    :param account: 账号
    :param multiple_status: 是否多开状态
    :return: 是否成功
    """
    # 确保可以创建快捷启动
    data_path = func_setting.get_wechat_data_path()
    wechat_path = func_setting.get_wechat_install_path()
    if not data_path:
        return False
    avatar_path = os.path.join(Config.PROJ_USER_PATH, f"{account}", f"{account}.jpg")
    if not os.path.exists(avatar_path):
        messagebox.showerror("错误", "您尚未获取头像，不能够创建快捷启动！")
        return False

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
    account_file_path = os.path.join(Config.PROJ_USER_PATH, f'{account}')
    if not os.path.exists(account_file_path):
        os.makedirs(account_file_path)
    # 保存为批处理文件
    bat_file_path = os.path.join(Config.PROJ_USER_PATH, f'{account}', f'{prefix}{account}.bat')
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
    base_dir = os.path.dirname(avatar_path)
    exe_name = os.path.splitext(os.path.basename(exe_path))[0]

    # 步骤1：提取图标为图片
    extracted_exe_png_path = os.path.join(base_dir, f"{exe_name}_extracted.png")
    image_utils.extract_icon_to_png(exe_path, extracted_exe_png_path)

    # 步骤2：合成图片
    ico_jpg_path = os.path.join(base_dir, f"{account}_{exe_name}.png")
    image_utils.add_diminished_se_corner_mark_to_image(avatar_path, extracted_exe_png_path, ico_jpg_path)

    # 步骤3：对图片转格式
    ico_path = os.path.join(base_dir, f"{account}_{exe_name}.ico")
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


def create_multiple_lnk(status, after):
    """
    创建快捷多开
    :return: 是否成功
    """

    def get_all_configs():
        """
        获取已经配置的账号列表
        :return: 已经配置的账号列表
        """
        target_path = os.path.join(func_setting.get_wechat_data_path(), 'All Users', 'config')
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
        result = create_lnk_for_account(account, status)
        if result is False:
            after()
            return False

    return True


def reset(after):
    """
    重置应用设置和删除部分用户文件
    :param after: 结束后执行的方法：初始化
    :return: 无
    """
    # 显示确认对话框
    confirm = messagebox.askokcancel(
        "确认重置",
        "该操作需要关闭所有微信进程，将清空除配置文件外的所有文件及设置，请确认是否需要重置？"
    )
    directory_path = Config.PROJ_USER_PATH
    dll_dir_path = func_setting.get_wechat_dll_dir_path()
    if confirm:
        try:
            # 恢复原始的dll
            dll_path = os.path.join(dll_dir_path, "WeChatWin.dll")
            bak_path = os.path.join(dll_dir_path, "WeChatWin_bak.dll")

            # 检查 .bak 文件是否存在
            if os.path.exists(bak_path):
                # 如果 WeChatWin.dll 存在，删除它
                if os.path.exists(dll_path):
                    os.remove(dll_path)
                    print(f"Deleted: {dll_path}")

                # 将 .bak 文件重命名为 WeChatWin.dll
                os.rename(bak_path, dll_path)
                print(f"Restored: {dll_path} from {bak_path}")
            else:
                print(f"No action needed. {bak_path} not found.")

            # 确认后删除目录的所有内容
            for item in os.listdir(directory_path):
                item_path = os.path.join(directory_path, item)
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

            messagebox.showinfo("重置完成", "目录已成功重置。")
            after()
        except PermissionError as e:
            print(e)
            messagebox.showinfo("拒绝访问", "请确保微信已全部退出。")
    else:
        messagebox.showinfo("操作取消", "重置操作已取消。")
