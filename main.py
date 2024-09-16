import argparse
import ctypes
import os
import sys
import tkinter as tk

from ui.loading_ui import LoadingWindow
from ui.main_ui import MainWindow


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


def main():
    print(f"是否管理员模式：{is_admin()}")
    root = tk.Tk()
    loading_window = LoadingWindow(root)
    MainWindow(root, loading_window, debug=args.debug)
    root.mainloop()


if __name__ == "__main__":
    # 创建参数解析器
    parser = argparse.ArgumentParser(description="Process command line flags.")
    # 添加 --debug 和 -d 选项
    parser.add_argument('--debug', '-d', action='store_true', help="Enable debug mode.")
    # 解析命令行参数
    args = parser.parse_args()
    # 检查是否有 --debug 或 -d 参数
    if args.debug:
        print("当前是调试模式")
        from utils import print_override
        print_override.test()
    else:
        print("当前是普通模式")
    if not is_admin():
        print("当前没有管理员权限，尝试获取...")
        if not elevate():
            print("无法获得管理员权限，程序将退出。")
            sys.exit(1)
    else:
        print("已获得管理员权限，正在执行主逻辑...")
        main()
