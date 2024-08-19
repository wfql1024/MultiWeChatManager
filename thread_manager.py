import threading
from tkinter import messagebox


def _handle_auto_login_result(account, auto_login_result, create_account_list, bring_window_to_front):
    if auto_login_result:
        print("自动登录完成")
    else:
        messagebox.showerror("错误", f"{account} 自动登录失败")
    create_account_list()
    bring_window_to_front()


def _handle_manual_login_result(manual_login_result, create_account_list, bring_window_to_front):
    if manual_login_result:
        print("ThreadManager: 手动登录成功，正在刷新")
    else:
        messagebox.showerror("错误", "手动登录失败，请重试")
    create_account_list()
    bring_window_to_front()


def _handle_create_config_result(config_result, create_main_frame):
    if config_result:
        print("ThreadManager: 配置创建成功")
    else:
        print("ThreadManager: 配置创建失败")
    create_main_frame()


class ThreadManager:
    def __init__(self, master, account_manager):
        self.auto_login_thread = None
        self.manual_login_thread = None
        self.master = master
        self.account_manager = account_manager

    def create_config(self, account, test_and_create_config, create_main_frame):
        def thread_func():
            result = test_and_create_config(account)
            self.master.after(0, _handle_create_config_result, result, create_main_frame)

        threading.Thread(target=thread_func).start()

    def manual_login_account(self, manual_login_func, status, create_account_list, bring_window_to_front):
        self.manual_login_thread = threading.Thread(target=self._manual_login_thread, args=(
            manual_login_func, status, create_account_list, bring_window_to_front))
        self.manual_login_thread.start()

    def _manual_login_thread(self, manual_login_func, status, create_account_list, bring_window_to_front):
        manual_login_result = manual_login_func(status)
        self.master.after(0, _handle_manual_login_result, manual_login_result, create_account_list,
                          bring_window_to_front)

    def auto_login_account(self, auto_login_func, account, status, create_account_list, bring_window_to_front):
        self.auto_login_thread = threading.Thread(target=self._auto_login_thread, args=(
            auto_login_func, account, status, create_account_list, bring_window_to_front))
        self.auto_login_thread.start()

    def _auto_login_thread(self, auto_login_func, account, status, create_account_list, bring_window_to_front):
        auto_login_result = auto_login_func(account, status)
        self.master.after(0, _handle_auto_login_result, account, auto_login_result, create_account_list,
                          bring_window_to_front)

    def get_account_list_thread(self, account_manager, callback):
        def thread_func():
            result = account_manager.get_account_list()
            self.master.after(0, callback, result)

        threading.Thread(target=thread_func).start()
