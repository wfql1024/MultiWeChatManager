import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import ttk, messagebox

import psutil

from data_access import RootSetting
from public import config, Config
from public.enums import RootCfgKey
from utils.logger_utils import Logger

CREATE_NO_WINDOW = 0x08000000
exe_name_keywords = ["JhiFeng", "Multi", "多开", "多聊"]

SF = config.get_scale_factor()


def find_dir(start_dir, dirname):
    """递归查找指定文件"""
    for root, dirs, files in os.walk(start_dir):
        if dirname in dirs:
            return os.path.join(root, dirname)
    return None


def find_file(start_dir, filename):
    """递归查找指定文件"""
    for root, dirs, files in os.walk(start_dir):
        if filename in files:
            return os.path.join(root, filename)
    return None


def find_file_fuzzy_with_keywords(start_dir, keywords, extension=None):
    """
    递归模糊查找包含任意关键字的文件
    :param start_dir: 起始目录
    :param keywords: 关键字列表，文件名需要包含列表中的任意一个关键字
    :param extension: 可选，文件扩展名（如 '.exe'），默认为 None 表示不限制扩展名
    :return: 符合条件的第一个文件路径，或 None
    """
    for root, dirs, files in os.walk(start_dir):
        for file in files:
            if any(keyword in file for keyword in keywords) and (extension is None or file.endswith(extension)):
                return os.path.join(root, file)
    return None


def elevate():
    if ctypes.windll.shell32.IsUserAnAdmin():
        return True
    else:
        try:
            hinstance = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            if hinstance <= 32:
                return False
            return True
        except Exception as e:
            print(e)
            return False


def is_admin():
    """检查当前进程是否具有管理员权限。"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except AttributeError:
        # 非 Windows 系统，默认返回 True
        return os.geteuid() == 0


def quit_main():
    if getattr(sys, 'frozen', False):
        # 遍历所有进程，找到包含关键字的进程名并结束
        for keyword in exe_name_keywords:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and keyword in proc.info['name']:
                        subprocess.run(
                            ["taskkill", "/f", "/pid", str(proc.info['pid'])],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        Logger().info(f"已结束进程: {proc.info['name']} (PID: {proc.info['pid']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass


def update_and_reopen(args, root):
    try:
        # 提取参数
        old_ver = args.old_ver
        new_ver = args.new_ver
        inst_dir = args.inst_dir
        download_path = args.download_path

        old_ver_inst_dir = os.path.join(inst_dir, ".old", f"[{old_ver}]")
        os.makedirs(old_ver_inst_dir, exist_ok=True)

        # 从旧版根配置中找到旧版用户文件夹, 并推出新版用户文件夹位置存入新版的根配置中
        old_ver_root_dir = RootSetting.get_ver_root_dir(old_ver)
        old_ver_root_config_path = old_ver_root_dir + "/" + Config.ROOT_CONFIG_PATH_SUFFIX
        old_ver_root_config = RootSetting(old_ver_root_config_path)
        old_ver_user_dir, = old_ver_root_config.get_(**{RootCfgKey.USER_DIR: None})

        new_ver_root_dir = RootSetting.get_ver_root_dir(new_ver)
        new_ver_root_config_path = new_ver_root_dir + "/" + Config.ROOT_CONFIG_PATH_SUFFIX
        new_ver_root_config = RootSetting(new_ver_root_config_path)

        try:
            if isinstance(old_ver_user_dir, str):
                # 从旧版根配置获得用户文件夹路径, 替换路径中的版本号即可
                new_ver_user_dir = old_ver_user_dir.replace(old_ver, new_ver)
            else:
                # 旧版没有配置, 说明是旧架构, 直接从安装位置拿
                old_ver_user_dir = find_dir(old_ver_inst_dir, 'user_files')
                new_ver_user_dir = new_ver_root_config.fetch_user_dir_or_set_default()
        except Exception as e:
            Logger().warning(e)
            new_ver_user_dir = new_ver_root_config.fetch_user_dir_or_set_default()

        new_ver_root_config.update_(**{RootCfgKey.USER_DIR: new_ver_user_dir})

        try:
            quit_main()
        except Exception as e:
            Logger().error(f"结束进程时出错: {e}")
            messagebox.showerror("错误", f"非常抱歉！{e}，请手动关闭旧版程序后点确定！")
            quit_main()

        # 1. 解压下载的压缩包
        update_exe_path = sys.executable
        tmp_zip = download_path
        tmp_dir = os.path.dirname(update_exe_path)
        try:
            with zipfile.ZipFile(tmp_zip, 'r') as zip_ref:
                zip_ref.extractall(tmp_dir)
        except Exception as e:
            Logger().error(e)
            messagebox.showerror("错误",
                                 f"非常抱歉解压新版失败！{e}，将打开压缩文件所在目录和当前安装目录，稍后可手动解压替换，或稍后重试！")
            os.startfile(tmp_dir)
            os.startfile(inst_dir)
            root.after(0, root.destroy)  # 安全销毁

        # 2. 拷贝 install_path 中的所有文件和文件夹（排除 “.old” 文件夹）
        for item in os.listdir(inst_dir):
            try:
                item_path = os.path.join(inst_dir, item)
                if os.path.isdir(item_path) and item == ".old":
                    continue  # 排除 ".old" 文件夹
                # shutil.move(item_path, old_ver_inst_dir)  # 移动所有项目到目标文件夹
                if os.path.isdir(item_path):
                    shutil.copytree(item_path, os.path.join(old_ver_inst_dir, item))
                if os.path.isfile(item_path):
                    shutil.copy2(item_path, os.path.join(old_ver_inst_dir, item))
            except Exception as e:
                Logger().error(e)
                messagebox.showerror("错误",
                                     f"非常抱歉备份旧版失败！{e}，\n"
                                     f"将打开压缩文件所在目录和当前安装目录，请备份好user文件夹后手动安装！")
                os.startfile(tmp_dir)
                os.startfile(inst_dir)
                root.after(0, root.destroy)  # 安全销毁

        # 3. 拷贝旧版 version 文件夹中的 user_files 文件夹 并覆盖到到 新版本临时文件夹 中的 external_res 同级目录
        # 新文件架构之后, 用户文件夹并不一定仍在安装目录中...
        # tmp_external_res_path = find_dir(tmp_dir, 'external_res')
        # old_ver_user_dir = find_dir(old_ver_inst_dir, 'user_files')
        Logger().info(new_ver_user_dir, old_ver_user_dir)
        if old_ver_user_dir is not None and new_ver_user_dir is not None:
            # new_ver_user_dir = os.path.join(os.path.dirname(tmp_external_res_path), 'user_files')
            if os.path.exists(new_ver_user_dir):
                shutil.rmtree(new_ver_user_dir)
            try:
                shutil.copytree(str(old_ver_user_dir), new_ver_user_dir)
            except Exception as e:
                Logger().error(e)
                messagebox.showerror("错误",
                                     f"非常抱歉迁移user_files失败，\n"
                                     f"将打开新版本临时目录和备份目录，请拷贝旧版user文件夹后手动安装！")
                os.startfile(os.path.dirname(tmp_dir))
                os.startfile(old_ver_inst_dir)
                root.after(0, root.destroy)  # 安全销毁
        else:
            Logger().error("未找到 external_res 文件夹或 user_files 文件夹。")
            messagebox.showerror("错误",
                                 f"未找到 external_res 文件夹或 user_files 文件夹。\n"
                                 f"将打开压缩文件所在目录和备份目录，请备份好user文件夹后手动安装！")
            os.startfile(tmp_dir)
            os.startfile(old_ver_inst_dir)
            root.after(0, root.destroy)  # 安全销毁

        # 4. 拷贝 tmp_dir 中 "?.exe" 所在的目录的所有文件和文件夹到 install_path 中并覆盖
        tmp_new_exe_path = find_file_fuzzy_with_keywords(tmp_dir, exe_name_keywords, ".exe")
        # 删除inst_dir中除了".old"文件夹外的所有文件和文件夹
        for item in os.listdir(inst_dir):
            try:
                item_path = os.path.join(inst_dir, item)
                if os.path.isdir(item_path) and item != ".old":
                    shutil.rmtree(item_path)  # 删除目标文件夹
                elif os.path.isfile(item_path) and not item.endswith(".log"):
                    os.remove(item_path)  # 删除目标文件
            except Exception as e:
                Logger().error(f"删除对应旧文件出错: {e}")
        # 拷贝
        if tmp_new_exe_path is not None:
            tmp_new_exe_dir = os.path.dirname(tmp_new_exe_path)
            for item in os.listdir(tmp_new_exe_dir):
                item_path = os.path.join(tmp_new_exe_dir, item)
                target_path = os.path.join(inst_dir, item)
                # 先删除
                try:
                    if os.path.exists(target_path):
                        if os.path.isdir(target_path):
                            shutil.rmtree(target_path)  # 删除目标文件夹
                        else:
                            os.remove(target_path)  # 删除目标文件
                except Exception as e:
                    Logger().error(f"删除对应旧文件出错: {e}")
                # 再拷贝
                try:
                    if os.path.isdir(item_path):
                        shutil.copytree(item_path, target_path)  # 拷贝文件夹
                    else:
                        shutil.copy2(item_path, target_path)  # 拷贝文件
                except Exception as e:
                    Logger().error(f"覆盖对应旧文件错误: {e}")
        else:
            Logger().error("未找到新版程序")
            messagebox.showerror("错误",
                                 f"未找到新版程序，\n"
                                 f"将打开压缩文件所在目录和备份目录，请备份好user文件夹后手动安装！")
            os.startfile(tmp_dir)
            os.startfile(old_ver_inst_dir)
            root.after(0, root.destroy)  # 安全销毁

        # 5. 启动 install_path 中的 "?.exe"
        # exe_files = glob.glob(os.path.join(inst_dir, f"*.exe"))
        exe_files = [str(p) for p in Path(inst_dir).rglob(f"*.exe")]
        exe2open = None
        if len(exe_files) == 0:
            Logger().error("未找到程序")
        elif len(exe_files) == 1:
            exe2open = exe_files[0]
        else:
            for e in exe_files:
                if any(keyword in e for keyword in exe_name_keywords):
                    exe2open = e
                    break

        if exe2open is not None:
            # 启动新程序
            subprocess.Popen([exe2open, "--new"])
            Logger().info("新版程序已启动，参数: --new")
        else:
            Logger().error("新版程序不存在。")
            messagebox.showerror("错误",
                                 f"未找到新版程序，\n"
                                 f"将打开压缩文件所在目录和备份目录，请备份好user文件夹后手动安装！")
            os.startfile(tmp_dir)
            os.startfile(old_ver_inst_dir)
            root.after(0, root.destroy)  # 安全销毁
    except Exception as e:
        Logger().error(e)
    finally:
        # 在主线程中销毁窗口
        root.after(0, root.destroy)  # 安全销毁


def test_to_destroy(root):
    time.sleep(10)
    # 在主线程中销毁窗口
    root.after(0, root.destroy)  # 安全销毁


def main():
    # 不使用代理
    os.environ['http_proxy'] = ''
    os.environ['https_proxy'] = ''
    os.environ['no_proxy'] = '*'
    Logger().error(f"是否管理员模式：{is_admin()}")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')

    # 创建参数解析器
    parser = argparse.ArgumentParser(description="Process command line flags.")
    # 添加 --debug 和 -d 选项
    parser.add_argument('--debug', '-d', action='store_true', help="Enable debug mode.")
    parser.add_argument("old_ver", help="更新前版本号")
    parser.add_argument("new_ver", help="新版版本号")
    parser.add_argument("inst_dir", help="安装目录")
    parser.add_argument("download_path", help="下载路径")
    # 解析命令行参数
    args, unknown = parser.parse_known_args()
    if unknown:
        Logger().debug(f"忽略的参数: {unknown}")

    root = tk.Tk()
    root.title("更新程序")

    # 打开升级程序窗口
    window_width = int(240 * SF)
    window_height = int(80 * SF)
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    # 禁用窗口大小调整
    root.resizable(False, False)
    # 移除窗口装饰并设置为工具窗口
    root.attributes('-toolwindow', True)
    root.grab_set()

    label = ttk.Label(root, text="正在升级，请勿关闭该窗口……")
    label.pack(pady=int(16 * SF))

    progress = ttk.Progressbar(root, mode="indeterminate", length=int(200 * SF))
    progress.pack(pady=int(8 * SF))

    progress.start(5)

    # 将更新和重启的操作放在一个线程中执行
    threading.Thread(target=update_and_reopen, args=(args, root)).start()
    # threading.Thread(target=test_to_destroy, args=(root,)).start()

    root.mainloop()
    Logger().info("窗口已经关闭，才会执行下面")
    # sys.exit()


if __name__ == "__main__":
    if not is_admin():
        Logger().warning("当前没有管理员权限，尝试获取...")
        if not elevate():
            Logger().error("无法获得管理员权限，程序将退出。")
            sys.exit(1)
    else:
        Logger().info("已获得管理员权限，正在执行主逻辑...")
        main()
