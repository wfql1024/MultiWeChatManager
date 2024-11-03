import argparse
import ctypes
import shutil
import subprocess
import threading
import tkinter as tk
import os
import sys
import zipfile
from tkinter import ttk

CREATE_NO_WINDOW = 0x08000000


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
        exe_path = sys.executable
        try:
            # 查找进程ID并结束进程
            subprocess.run(["taskkill", "/f", "/im", "微信多开管理器.exe"], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
            print("已结束 '微信多开管理器.exe'")
        except Exception as e:
            print(f"结束进程时出错: {e}")


def update_and_reopen(args, root):
    # 提取参数
    before_version = args.before_version
    install_dir = args.install_dir

    quit_main()

    # 0. 解压下载的压缩包
    update_exe_path = sys.executable
    tmp_dir = os.path.dirname(update_exe_path)
    tmp_zip = os.path.join(tmp_dir, "temp.zip")
    try:
        with zipfile.ZipFile(tmp_zip, 'r') as zip_ref:
            zip_ref.extractall(tmp_dir)
    except Exception as e:
        print(e)

    # 1. 创建 version 文件夹
    version_dir = os.path.join(install_dir, f"[{before_version}]")
    os.makedirs(version_dir, exist_ok=True)

    # 2. 移动 install_path 中的所有文件和文件夹（排除 “[xxx]” 文件夹）
    try:
        for item in os.listdir(install_dir):
            item_path = os.path.join(install_dir, item)
            if os.path.isdir(item_path) and item.startswith("[") and item.endswith("]"):
                continue  # 排除 "[xxx]" 文件夹
            shutil.move(item_path, version_dir)  # 移动文件和文件夹
    except Exception as e:
        print(e)

    # 3. 拷贝 tmp_dir 中 "微信多开管理器.exe" 所在的目录的所有文件和文件夹到 install_path 中
    new_exe_path = find_file(tmp_dir, "微信多开管理器.exe")
    if new_exe_path:
        exe_dir = os.path.dirname(new_exe_path)
        for item in os.listdir(exe_dir):
            item_path = os.path.join(exe_dir, item)
            target_path = os.path.join(install_dir, item)
            if os.path.exists(target_path):
                if os.path.isdir(target_path):
                    shutil.rmtree(target_path)  # 删除目标文件夹
                else:
                    os.remove(target_path)  # 删除目标文件
            try:
                if os.path.isdir(item_path):
                    shutil.copytree(item_path, target_path)  # 拷贝文件夹
                else:
                    shutil.copy(item_path, target_path)  # 拷贝文件
            except Exception as e:
                print(f"拷贝错误: {e}")
    else:
        print("未找到微信多开管理器.exe")

    # 4. 拷贝 version 文件夹中的 user_files 文件夹到 install_path 中的 external_res 同级目录
    external_res_path = find_dir(install_dir, 'external_res')
    user_files_src = find_dir(version_dir, 'user_files')
    print(external_res_path, user_files_src)
    if user_files_src and external_res_path:
        dest_path = os.path.join(os.path.dirname(external_res_path), 'user_files')
        if os.path.exists(dest_path):
            shutil.rmtree(dest_path)
        try:
            shutil.copytree(str(user_files_src), dest_path)
        except Exception as e:
            print(e)
    else:
        print("未找到 external_res 文件夹或 user_files 文件夹不存在。")

    # 5. 启动 install_path 中的 "微信多开管理器.exe"
    wechat_exe_path = os.path.join(install_dir, "微信多开管理器.exe")
    if os.path.exists(wechat_exe_path):
        os.startfile(wechat_exe_path)  # 在 Windows 上启动 exe 文件
    else:
        print("微信多开管理器.exe 不存在。")

    root.destory()


def main():
    # 设置环境变量，告诉 Python 不使用代理
    os.environ['http_proxy'] = ''
    os.environ['https_proxy'] = ''
    os.environ['no_proxy'] = '*'
    print(f"是否管理员模式：{is_admin()}")
    # 创建参数解析器
    parser = argparse.ArgumentParser(description="Process command line flags.")
    # 添加 --debug 和 -d 选项
    parser.add_argument('--debug', '-d', action='store_true', help="Enable debug mode.")
    parser.add_argument("before_version", help="更新前版本号")
    parser.add_argument("install_dir", help="安装路径")
    # 解析命令行参数
    args, unknown = parser.parse_known_args()

    root = tk.Tk()
    root.title("更新程序")

    # 打开升级程序窗口
    window_width = 300
    window_height = 100
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
    label.pack(pady=20)

    progress = ttk.Progressbar(root, mode="indeterminate", length=250)
    progress.pack(pady=10)

    progress.start(5)

    # 将更新和重启的操作放在一个线程中执行
    threading.Thread(target=update_and_reopen, args=(args, root)).start()

    root.mainloop()


if __name__ == "__main__":
    if not is_admin():
        print("当前没有管理员权限，尝试获取...")
        if not elevate():
            print("无法获得管理员权限，程序将退出。")
            sys.exit(1)
    else:
        print("已获得管理员权限，正在执行主逻辑...")
        main()
