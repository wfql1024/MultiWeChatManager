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
        except:
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
    MainWindow(root, loading_window)
    root.mainloop()


if __name__ == "__main__":
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("当前没有管理员权限，尝试获取...")
        if not elevate():
            print("无法获得管理员权限，程序将退出。")
            sys.exit(1)
        # 如果 elevate() 成功，程序会在新的管理员权限进程中重新启动
        # 所以这里不需要 else 语句
    else:
        print("已获得管理员权限，正在执行主逻辑...")
        main()
