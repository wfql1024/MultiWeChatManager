import threading
import time
from typing import Dict

from functions import subfunc_file
from functions.acc_func import AccInfoFunc, AccOperator
from public.enums import LocalCfg, SwStates, RemoteCfg
from utils.logger_utils import Logger


class MultiSwFunc:
    """多平台功能"""

    @staticmethod
    def get_all_enable_sw() -> list:
        """获取所有启用的平台"""
        all_sw_list, = subfunc_file.get_remote_cfg(LocalCfg.GLOBAL_SECTION, **{RemoteCfg.SP_SW: []})
        all_enable_sw = []
        for sw in all_sw_list:
            state = subfunc_file.get_settings(sw, LocalCfg.STATE)
            if state == SwStates.HIDDEN or state == SwStates.VISIBLE:
                all_enable_sw.append(sw)
        return all_enable_sw

    @staticmethod
    def get_all_visible_sw() -> list:
        """获取所有可见的平台"""
        all_sw_list, = subfunc_file.get_remote_cfg(LocalCfg.GLOBAL_SECTION, **{RemoteCfg.SP_SW: []})
        all_visible_sw = []
        for sw in all_sw_list:
            state = subfunc_file.get_settings(sw, LocalCfg.STATE)
            if state == SwStates.VISIBLE:
                all_visible_sw.append(sw)
        return all_visible_sw

    @classmethod
    def _login_auto_start_accounts(cls):
        all_sw = cls.get_all_enable_sw()
        print("所有平台：", all_sw)
        # 获取需要自启动的账号
        accounts_to_auto_start: Dict[str, set] = {}
        for sw in all_sw:
            if sw not in accounts_to_auto_start:
                accounts_to_auto_start[sw] = set()
            sw_data = subfunc_file.get_sw_acc_data(sw)
            if sw_data is None:
                continue
            for acc in sw_data:
                auto_start, = subfunc_file.get_sw_acc_data(sw, acc, auto_start=None)
                if auto_start is True:
                    accounts_to_auto_start[sw].add(acc)
        print(f"设置了自启动：{accounts_to_auto_start}")
        # 获取已经登录的账号
        for sw in accounts_to_auto_start:
            success, result = AccInfoFunc.get_sw_acc_list(sw)
            if success is not True:
                continue
            acc_list_dict, _ = result
            logins = acc_list_dict["login"]
            if isinstance(logins, list):
                for acc in logins:
                    accounts_to_auto_start[sw].discard(acc)
        # 登录需要自启但未登录的账号
        if not any(len(sw_set) != 0 for sw, sw_set in accounts_to_auto_start.items()):
            print("自启动账号都已登录完毕！")
            return
        print(f"排除已登录之后需要登录：{accounts_to_auto_start}")
        # 打印即将自动登录的提示
        for i in range(0, 3):
            print(f"即将自动登录：{3 - i}秒")
            time.sleep(1)
        login_dict = {}
        for sw, acc_set in sorted(accounts_to_auto_start.items(), reverse=True):
            if not isinstance(acc_set, set) or len(acc_set) == 0:
                continue
            login_dict[sw] = list(acc_set)
        print(login_dict)
        # 遍历登录需要自启但未登录的账号
        try:
            AccOperator.start_login_accounts_thread(login_dict)
        except Exception as e:
            Logger().error(e)
            return

    @staticmethod
    def thread_to_login_auto_start_accounts():
        try:
            threading.Thread(target=MultiSwFunc._login_auto_start_accounts).start()
        except Exception as e:
            Logger().error(e)


class MainFunc:
    pass
