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

    VIEW = "view"
    LOGIN_SIZE = "login_size"
    REST_MODE = "rest_mode"
    LOGIN_SORT = "login_sort"
    LOGOUT_SORT = "logout_sort"

class SW(str, Enum):
    WECHAT = "WeChat"
    WEIXIN = "Weixin"
    QQ = "QQ"

if __name__ == '__main__':
    print(Keywords.GLOBAL_SECTION)
    print(Keywords.GLOBAL_SECTION == "global")