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


class ThreadManager:
    def __init__(self, master, ui_helper, account_manager):
        self.master = master
        self.ui_helper = ui_helper
        self.account_manager = account_manager

    def create_and_test_config(self, account, create_and_test_func, save_callback, refresh_callback):
        def thread_func():
            result = create_and_test_func(account, save_callback)
            self.master.after(0, self._handle_config_result, result, refresh_callback)

        threading.Thread(target=thread_func).start()

    def _handle_config_result(self, config_result, refresh_callback):
        if config_result:
            print("ThreadManager: 配置创建成功")
        else:
            print("ThreadManager: 配置创建失败")
        refresh_callback()

    def manual_login_account(self, manual_login_func, create_account_list, bring_window_to_front):
        self.login_thread = threading.Thread(target=self._manual_login_thread, args=(
            manual_login_func, create_account_list, bring_window_to_front))
        self.login_thread.start()

    def _manual_login_thread(self, manual_login_func, create_account_list, bring_window_to_front):
        manual_login_result = manual_login_func()
        self.master.after(0, _handle_manual_login_result, manual_login_result, create_account_list,
                          bring_window_to_front)

    def auto_login_account(self, account, auto_login_func, create_account_list, bring_window_to_front):
        self.login_thread = threading.Thread(target=self._auto_login_thread, args=(
            account, auto_login_func, create_account_list, bring_window_to_front))
        self.login_thread.start()

    def _auto_login_thread(self, account, auto_login_func, create_account_list, bring_window_to_front):
        auto_login_result = auto_login_func(account)
        self.master.after(0, _handle_auto_login_result, account, auto_login_result, create_account_list,
                          bring_window_to_front)



    def _create_and_test_config_thread(self, account, create_and_test_func, save_callback, center_window,
                                       create_account_list):
        config_result = create_and_test_func(self, account, save_callback, center_window)
        self.master.after(0, self._handle_config_result, config_result, create_account_list)
