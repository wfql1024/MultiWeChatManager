import argparse
import ctypes
import os
import sys
import tkinter as tk

from ui import main_ui


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
    # # 启动键盘监听器线程
    # keyboard_thread = threading.Thread(target=start_keyboard_listener, daemon=True)
    # keyboard_thread.start()

    # 创建参数解析器
    parser = argparse.ArgumentParser(description="Process command line flags.")
    # 添加 --debug 和 -d 选项
    parser.add_argument('--debug', '-d', action='store_true', help="Enable debug mode.")
    parser.add_argument('--new', '-n', action='store_true', help="Enable new mode.")
    # 解析命令行参数
    args, unknown = parser.parse_known_args()
    # 检查是否有 --debug 或 -d 参数

    print("权限：" + "管理员身份" if ctypes.windll.shell32.IsUserAnAdmin() == 1 else "非管理员身份")
    print("调试模式：" + str(args.debug))

    root = tk.Tk()
    main_ui.RootClass(root, args)
    root.mainloop()


if __name__ == "__main__":
    # if sys.platform == 'win32':
    #     kernel32 = ctypes.WinDLL('kernel32')
    #     user32 = ctypes.WinDLL('user32')
    #     # 立即隐藏窗口
    #     user32.ShowWindow(kernel32.GetConsoleWindow(), 0)  # 0=SW_HIDE
    #     # 防止后续创建新控制台
    #     kernel32.FreeConsole()
    #     # 重定向所有输出到黑洞
    #     sys.stdout = open(os.devnull, 'w')

    if not is_admin():
        print("当前没有管理员权限，尝试获取...")
        if not elevate():
            print("无法获得管理员权限，程序将退出。")
            sys.exit(1)
    else:
        print("已获得管理员权限，正在执行主逻辑...")
        main()
