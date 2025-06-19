import threading
import time
from typing import Dict

from functions import subfunc_file
from functions.acc_func import AccInfoFunc, AccOperator
from public_class.enums import LocalCfg, SwStates
from public_class.global_members import GlobalMembers
from utils.logger_utils import mylogger as logger


class MultiSwFunc:
    """多平台功能"""

    @staticmethod
    def get_all_enable_sw() -> list:
        """获取所有启用的平台"""
        all_sw_dict, = subfunc_file.get_remote_cfg(LocalCfg.GLOBAL_SECTION, all_sw=None)
        all_enable_sw = []
        for sw in all_sw_dict:
            state = subfunc_file.get_settings(sw, LocalCfg.STATE)
            if state == SwStates.HIDDEN or state == SwStates.VISIBLE:
                all_enable_sw.append(sw)
        return all_enable_sw

    @staticmethod
    def get_all_visible_sw() -> list:
        """获取所有可见的平台"""
        all_sw_dict, = subfunc_file.get_remote_cfg(LocalCfg.GLOBAL_SECTION, all_sw=None)
        all_visible_sw = []
        for sw in all_sw_dict:
            state = subfunc_file.get_settings(sw, LocalCfg.STATE)
            if state == SwStates.VISIBLE:
                all_visible_sw.append(sw)
        return all_visible_sw

    @staticmethod
    def _login_auto_start_accounts():
        root_class = GlobalMembers.root_class
        root = root_class.root
        login_ui = root_class.login_ui

        # all_sw_dict, = subfunc_file.get_remote_cfg(LocalCfg.GLOBAL_SECTION, all_sw=None)
        # all_sw = [key for key in all_sw_dict.keys()]
        all_sw = MultiSwFunc.get_all_enable_sw()

        print("所有平台：", all_sw)

        # 获取需要自启动的账号
        can_auto_start: Dict[str, set] = {

        }
        for sw in all_sw:
            if sw not in can_auto_start:
                can_auto_start[sw] = set()
            sw_data = subfunc_file.get_sw_acc_data(sw)
            if sw_data is None:
                continue
            for acc in sw_data:
                auto_start, = subfunc_file.get_sw_acc_data(sw, acc, auto_start=None)
                if auto_start is True:
                    can_auto_start[sw].add(acc)
        print(f"设置了自启动：{can_auto_start}")

        # 获取已经登录的账号
        for sw in all_sw:
            # try:
            if sw == login_ui.sw:
                logins = root_class.sw_classes[sw].login_accounts
            else:
                success, result = AccInfoFunc.get_sw_acc_list(root, root_class, sw)
                if success is not True:
                    continue
                acc_list_dict, _, _ = result
                logins = acc_list_dict["login"]
            for acc in logins:
                can_auto_start[sw].discard(acc)
        # except Exception as e:
        #     logger.error(e.with_traceback())
        #     continue

        if any(len(sw_set) != 0 for sw, sw_set in can_auto_start.items()):
            print(f"排除已登录之后需要登录：{can_auto_start}")
            # 打印即将自动登录的提示
            for i in range(0, 3):
                print(f"即将自动登录：{3 - i}秒")
                time.sleep(1)
            login_dict = {}
            for sw, acc_set in can_auto_start.items():
                if not isinstance(acc_set, set) or len(acc_set) == 0:
                    continue
                login_dict[sw] = list(acc_set)
            print(login_dict)

            # 遍历登录需要自启但未登录的账号
            try:
                AccOperator.thread_to_auto_login_accounts(login_dict)
            except Exception as e:
                logger.error(e)
        else:
            print("自启动账号都已登录完毕！")
            return

    @staticmethod
    def thread_to_login_auto_start_accounts():
        try:
            threading.Thread(target=MultiSwFunc._login_auto_start_accounts).start()
        except Exception as e:
            logger.error(e)


class MainFunc:
    pass