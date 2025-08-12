# 定义对齐方式的枚举类
from enum import Enum


class MultirunMode(str, Enum):
    BUILTIN = "内置"
    FREELY_MULTIRUN = "全局多开"


class CallMode(str, Enum):
    HANDLE = "HANDLE"
    DEFAULT = "DEFAULT"
    LOGON = "LOGON"


class NotebookDirection(Enum):
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"


class Position(Enum):
    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


class RemoteCfg(str, Enum):
    """远程配置中的字段"""
    GLOBAL = "global"
    SP_SW = "support_sw"
    COEXIST_SEQUENCE = "coexist_sequence"

    REVOKE = "anti-revoke"
    MULTI = "multirun"
    COEXIST = "coexist"
    WND_CLASS = "wnd_class"
    NATIVE_MULTI = "native-multirun"
    NATIVE = "natively"
    # dll模式字段
    ORIGINAL = "original"
    MODIFIED = "modified"


class LocalCfg(str, Enum):
    """本地设置中的字段"""
    GLOBAL_SECTION = "global"

    # 设置项中的全局设置
    SCREEN_SIZE = "screen_size"
    HIDE_WND = "hide_wnd"
    ENABLE_NEW_FUNC = "enable_new_func"
    DISABLE_SORT = "disable_sort"
    ENABLE_SORT = "enable_sort"
    ROOT_TAB = "root_tab"
    MNG_TAB = "mng_tab"
    LOGIN_TAB = "login_tab"
    SCALE = "scale"
    SIGN_VISIBLE = "sign_visible"
    HIDDEN_SORT = "hidden_sort"
    AUTO_START_SORT = "auto_start_sort"
    ALL_SORT = "all_sort"
    AUTO_PRESS = "auto_press"
    CALL_MODE = "call_mode"
    ENCRYPTED_USERNAME = "encrypted_username"
    ENCRYPTED_PASSWORD = "encrypted_password"
    NEXT_CHECK_TIME = "next_check_time"
    USE_PROXY = "use_proxy"
    PROXY_IP = "proxy_ip"
    PROXY_PORT = "proxy_port"
    PROXY_USERNAME = "proxy_username"
    PROXY_PWD = "proxy_pwd"
    USE_TXT_AVT = "txt_avt"
    USED_TRAY = "used_tray"
    USED_REFRESH = "used_refresh"
    USED_SIDEBAR = "used_sidebar"

    # 设置项中的平台设置
    INST_PATH = "inst_path"
    INST_DIR = "inst_dir"
    DATA_DIR = "data_dir"
    DLL_DIR = "dll_dir"
    VIEW = "view"
    LOGIN_SIZE = "login_size"
    REST_MULTIRUN_MODE = "rest_mode"
    MULTIRUN_MODE = "multirun_mode"
    LOGIN_SORT = "login_sort"
    LOGOUT_SORT = "logout_sort"
    STATE = "state"
    NOTE = "note"
    KILL_IDLE_LOGIN_WND = "kill_idle_login_wnd"
    COEXIST_MODE = "coexist_mode"


class WndType(str, Enum):
    """窗口类型"""
    MAIN = "main"
    LOGIN = "login"

class SwStates(str, Enum):
    """平台状态"""
    VISIBLE = "visible"
    HIDDEN = "hidden"
    DISABLED = "disabled"


class AccKeys(str, Enum):
    """账号数据中的字段"""
    # 中转字段
    RELAY = "::RELAY"
    PID_MUTEX = "pid_mutex"
    # 以下为账号详情获取字段
    IID = "iid"
    AVATAR = "img"
    DISPLAY = "display_name"
    WRAP_DISPLAY = "wrapped_display_name"
    CONFIG_STATUS = "config_status"
    LINKED_ACC = "linked_acc"
    # 以下为账号详情存储字段
    NICKNAME = "nickname"
    ALIAS = "alias"
    AVATAR_URL = "avatar_url"
    PID = "pid"
    HAS_MUTEX = "has_mutex"
    AUTO_START = "auto_start"
    HOTKEY = "hotkey"
    HIDDEN = "hidden"


class SW(str, Enum):
    DEFAULT = "Default"
    WECHAT = "WeChat"
    WEIXIN = "Weixin"
    QQ = "QQ"
    QQNT = "QQNT"
    WXWORK = "WXWork"
    TIM = "TIM"
    DINGTALK = "DingTalk"
    FEISHU = "Feishu"
    BAIDU = "Baidu"


class OnlineStatus(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    UNKNOWN = "unknown"


class CfgStatus(str, Enum):
    NO_CFG = " 无配置"


if __name__ == "__main__":
    print(str(SwStates.HIDDEN.value))
