# 定义对齐方式的枚举类
from enum import Enum


class Position(Enum):
    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"

class Keywords(str, Enum):
    GLOBAL_SECTION = "global"
    # 设置项中的全局设置
    INST_PATH = "inst_path"
    DATA_DIR = "data_dir"
    DLL_DIR = "dll_dir"
    SCREEN_SIZE = "screen_size"
    HIDE_WND = "hide_wnd"
    ENABLE_NEW_FUNC = "enable_new_func"
    TAB = "tab"
    SCALE = "scale"
    SIGN_VISIBLE = "sign_visible"
    HIDDEN_SORT = "hidden_sort"
    AUTO_START_SORT = "auto_start_sort"
    ALL_SORT = "all_sort"
    AUTO_PRESS = "auto_press"
    CALL_MODE = "call_mode"
    NEXT_CHECK_TIME = "next_check_time"
    # 设置项中的平台设置
    VIEW = "view"
    LOGIN_SIZE = "login_size"
    REST_MODE = "rest_mode"
    LOGIN_SORT = "login_sort"
    LOGOUT_SORT = "logout_sort"

    # 账号数据中的平台字段
    PID_MUTEX = "pid_mutex"
    # 账号数据中的平台字段
    NICKNAME = "nickname"
    AVATAR_URL = "avatar_url"
    PID = "pid"
    HAS_MUTEX = "has_mutex"
    AUTO_START = "auto_start"
    HOTKEY = "hotkey"
    HIDDEN = "hidden"


class SW(str, Enum):
    WECHAT = "WeChat"
    WEIXIN = "Weixin"
    QQ = "QQ"

class OnlineStatus(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    UNKNOWN = "unknown"

if __name__ == '__main__':
    print(Keywords.GLOBAL_SECTION)
    print(Keywords.GLOBAL_SECTION == "global")