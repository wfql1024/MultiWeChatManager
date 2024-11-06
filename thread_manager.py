import threading
from tkinter import messagebox

from functions import func_account


def _handle_manual_login_result(manual_login_result, create_account_list, bring_window_to_front):
    if manual_login_result:
        print(f"ThreadManager: 手动登录成功，正在刷新")
    else:
        messagebox.showerror("错误", "手动登录失败，请重试")
    create_account_list()
    bring_window_to_front()


def _handle_create_config_result(config_result, create_main_frame):
    if config_result:
        print(f"ThreadManager: 配置创建成功")
    else:
        print(f"ThreadManager: 配置创建失败")
    create_main_frame()


class ThreadManager:
    def __init__(self, master):
        self.auto_login_thread = None
        self.manual_login_thread = None
        self.master = master
        self.condition = threading.Condition()

    def create_config_thread(self, account, func_test_and_create_config, status, create_main_frame):
        def thread_func():
            result = func_test_and_create_config(account, status)
            self.master.after(0, _handle_create_config_result, result, create_main_frame)

        threading.Thread(target=thread_func).start()

    def manual_login_account_thread(self, manual_login_func, status, create_account_list, bring_window_to_front):
        self.manual_login_thread = threading.Thread(target=self._manual_login_thread, args=(
            manual_login_func, status, create_account_list, bring_window_to_front))
        self.manual_login_thread.start()

    def _manual_login_thread(self, manual_login_func, status, create_account_list, bring_window_to_front):
        manual_login_result = manual_login_func(status)
        self.master.after(0, _handle_manual_login_result, manual_login_result, create_account_list,
                          bring_window_to_front)
