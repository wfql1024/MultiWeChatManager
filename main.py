import ctypes
import os
import sys
import tkinter as tk
from ctypes import wintypes
from ui.loading_ui import LoadingWindow
from ui.main_ui import MainWindow


def is_admin():
    """检查当前进程是否具有管理员权限。在 Windows 上使用 ctypes 调用。在非 Windows 平台上默认返回 True。"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except AttributeError:
        # 非 Windows 系统，默认返回 True
        return os.geteuid() == 0


def run_as_admin():
    """以管理员权限重新启动当前脚本。仅在 Windows 系统上有效。"""
    if sys.platform == 'win32':
        python_exe = sys.executable
        params = ' '.join([f'"{arg}"' for arg in sys.argv])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", python_exe, params, None, 1)
        sys.exit()
    else:
        print("此操作需要管理员权限，请手动以管理员身份运行脚本。")
        sys.exit()


def main():
    root = tk.Tk()
    loading_window = LoadingWindow(root)
    MainWindow(root, loading_window)
    root.mainloop()


if __name__ == "__main__":
    if '--noconsole' not in sys.argv:
        if not is_admin():
            print("当前没有管理员权限，尝试以管理员权限重新启动...")
            run_as_admin()
        else:
            print("已获得管理员权限，正在执行主逻辑...")
    else:
        if not is_admin():
            print("当前没有管理员权限，尝试以管理员权限重新启动...")
        main()
