import json
import threading

import keyboard

from legacy_python.functions.acc_func import AccOperator
from public_class.global_members import GlobalMembers
from legacy_python.utils.logger_utils import mylogger as logger


class HotkeyManager:
    def __init__(self):
        self.listener_thread = None
        self.stop_event = None

        self.hotkey_map = {
        }
        self.root_class = GlobalMembers.root_class

        self.listener_thread = None  # 监听线程
        self.stop_event = threading.Event()  # 用于控制线程退出

        # 在子线程中运行监听
        listener_thread = threading.Thread(target=self.start_hotkey_listener, daemon=True)
        listener_thread.start()

    def load_hotkeys_from_json(self, json_path):
        """ 从 JSON 文件加载快捷键映射 """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        hotkey_map = {}
        for sw, accounts in data.items():
            for acc, details in accounts.items():
                if isinstance(details, dict) and "hotkey" in details:
                    hotkey = details["hotkey"]
                    if hotkey is not None and hotkey != "":  # 确保 hotkey 不是 None 或 空字符串
                        hotkey_map[hotkey] = \
                            lambda software=sw, account=acc: AccOperator.switch_to_sw_account_wnd(
                                f"{software}/{account}")

        # 更新映射
        self.hotkey_map = hotkey_map
        # print(self.hotkey_map)

    def start_hotkey_listener(self):
        """ 启动全局快捷键监听 """
        if self.listener_thread and self.listener_thread.is_alive():
            return  # 避免重复启动

        # 先清除之前的快捷键绑定
        keyboard.unhook_all()

        # 注册新的快捷键
        for hk in self.hotkey_map:
            keyboard.add_hotkey(hk, lambda hotkey=hk: self.execute_task(hotkey))

        # 启动监听线程
        self.stop_event.clear()
        self.listener_thread = threading.Thread(target=self._hotkey_listener, daemon=True)
        self.listener_thread.start()

    def _hotkey_listener(self):
        """ 热键监听线程，等待退出信号 """
        while not self.stop_event.is_set():
            logger.info("监听快捷键中...")
            keyboard.wait()  # 等待快捷键事件，直到 stop_event 触发

    def stop_hotkey_listener(self):
        """ 停止全局快捷键监听 """
        if self.listener_thread and self.listener_thread.is_alive():
            self.stop_event.set()  # 设置退出信号
            keyboard.unhook_all()  # 取消所有快捷键监听
            self.listener_thread = None  # 清除线程引用

    def execute_task(self, hotkey):
        if hotkey in self.hotkey_map:
            self.hotkey_map[hotkey]()  # 执行绑定的任务
