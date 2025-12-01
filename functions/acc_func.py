from func_core.acc_func_core import AccInfoFuncCore, AccOperatorCore
from functions.sw_func import Sw


class Acc:
    _instances = {}

    def __new__(cls, sw_id, acc_id):
        # 如果实例已存在，优先返回旧实例
        if sw_id in cls._instances:
            if acc_id in cls._instances[sw_id]:
                return cls._instances[sw_id][acc_id]
        # 否则创建新实例
        instance = super().__new__(cls)
        if sw_id not in cls._instances:
            cls._instances[sw_id] = {}
        cls._instances[sw_id][acc_id] = instance
        return instance

    def __init__(self, sw_id, acc_id):
        # 防止重复初始化
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.sw_id = sw_id
        self.acc_id = acc_id
        self.sw = Sw(sw_id)
        # ------- 初始化成员 -------
        self._details = {}
        self._main_hwnd = {}

    @classmethod
    def reinit(cls, sw_id, acc_id):
        """强制重新构造实例，相同 id 会替换之前的实例。"""
        instance = super(Acc, cls).__new__(cls)  # 直接创建新实例
        cls._instances[sw_id] = instance  # 覆盖旧实例
        instance.__init__(sw_id, acc_id)  # 重新初始化
        return instance

    """属性"""

    def set_avatar(self):
        """手动选择头像保存"""
        return AccInfoFuncCore.manual_choose_avatar_for_acc(self.sw_id, self.acc_id)

    def delete_avatar(self):
        """删除头像"""
        return AccInfoFuncCore.delete_avatar_for_acc(self.sw_id, self.acc_id)

    def get_details(self):
        """获取详情"""
        return AccInfoFuncCore.get_acc_details(self.sw_id, self.acc_id)

    def get_main_hwnd(self):
        hwnd, _ = AccInfoFuncCore.get_main_hwnd_of_accounts(self.sw_id, [self.acc_id])
        return hwnd

    def get_data(self, *addr, **kwargs):
        return AccInfoFuncCore.get_sw_acc_data(self.sw_id, self.acc_id, *addr, **kwargs)

    def update_data(self, *addr, **kwargs):
        return AccInfoFuncCore.update_sw_acc_data(self.sw_id, self.acc_id, *addr, **kwargs)

    @property
    def main_hwnd(self):
        main_hwnd = self._main_hwnd
        if main_hwnd is None:
            main_hwnd = self.get_main_hwnd()
            self._main_hwnd = main_hwnd
        return self._main_hwnd

    @property
    def details(self):
        details = self._details
        if details is None:
            details = self.get_details()
        self._details = details
        return self._details

    def is_coexist(self):
        return AccInfoFuncCore.is_acc_coexist(self.sw_id, self.acc_id)

    def get_linked_real_acc(self):
        return AccInfoFuncCore.get_real_acc(self.sw_id, self.acc_id)

    """登录配置"""

    def operate_config(self, method):
        return AccOperatorCore.operate_acc_config(self.sw_id, self.acc_id, method)

    def create_config(self):
        return AccOperatorCore.open_sw_and_ask(self.sw_id, self.acc_id)

    def get_login_config_status(self):
        return AccInfoFuncCore.get_sw_acc_login_cfg_status(self.sw_id, self.acc_id)

    """操作"""

    def show_wnd(self):
        return AccOperatorCore.switch_to_sw_account_wnd(self.sw_id, self.acc_id)

    def quit(self):
        return AccOperatorCore.quit_accounts(self.sw_id, [self.acc_id])

    def kill_mutex(self):
        return AccOperatorCore.kill_mutex_of_acc(self.sw_id, self.acc_id)
