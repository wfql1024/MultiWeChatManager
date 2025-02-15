import os

from resources import constants

# 获取屏幕缩放因子
SCALE_FACTOR = constants.get_scale_factor()
current_file_dir = os.path.dirname(os.path.abspath(__file__))


class Config:
    VER_STATUS = 'Beta'

    INI_GLOBAL_SECTION = 'global'

    INI_KEY = {
        "inst_path": "install_path",
        "data_dir": "data_dir",
        "dll_dir": "dll_dir",
        "screen_size": "screen_size",
        "hide_wnd": "hide_wnd",
        "enable_new_func": "enable_new_func",
        "tab": "tab",
        "scale": "scale",
        "sign_visible": "sign_visible",
        "hidden_sort": "hidden_sort",
        "auto_start_sort": "auto_start_sort",
        "all_sort": "all_sort",
        "auto_press": "auto_press",
        "call_mode": "call_mode",

        "view": "view",
        "login_size": "login_size",
        "rest_mode": "rest_mode",
        "login_sort": "login_sort",
        "logout_sort": "logout_sort",

    }

    INI_DEFAULT_VALUE = {
        "screen_size": f"1920*1080",
        "hide_wnd": "False",
        "enable_new_func": "True",
        "tab": "WeChat",
        "scale": "auto",
        "sign_visible": "True",
        "hidden_sort": "#0,True",
        "auto_start_sort": "#0,True",
        "all_sort": "#0,True",
        "auto_press": "True",
        "call_mode": "HANDLE",

        "WeChat": {
            "view": "tree",
            "login_sort": "配置,True",
            "logout_sort": "配置,True",
            "login_size": f"{int(280 * SCALE_FACTOR)}*{int(380 * SCALE_FACTOR)}",
            "rest_mode": "python",
        },
        "Weixin": {
            "view": "tree",
            "login_sort": "配置,True",
            "logout_sort": "配置,True",
            "login_size": f"{int(280 * SCALE_FACTOR)}*{int(380 * SCALE_FACTOR)}",
            "rest_mode": "handle",
        },
    }

    PROJ_PATH = os.path.abspath(os.path.join(current_file_dir, '..'))
    PROJ_EXTERNAL_RES_PATH = fr'{PROJ_PATH}\external_res'
    PROJ_USER_PATH = fr'{PROJ_PATH}\user_files'
    PROJ_META_PATH = fr'{PROJ_PATH}\.meta'

    HANDLE_EXE_PATH = fr'{PROJ_EXTERNAL_RES_PATH}\handle.exe'
    WECHAT_DUMP_EXE_PATH = fr'{PROJ_EXTERNAL_RES_PATH}\wechat-dump-rs.exe'
    VERSION_FILE = fr'{PROJ_META_PATH}\version.txt'
    PROJ_ICO_PATH = fr'{PROJ_EXTERNAL_RES_PATH}\SunnyMultiWxMng.ico'
    REWARDS_PNG_PATH = fr'{PROJ_EXTERNAL_RES_PATH}\Rewards.png'
    TASK_TP_XML_PATH = fr'{PROJ_USER_PATH}\task_template.xml'
    STATISTIC_JSON_PATH = fr'{PROJ_USER_PATH}\statistics.json'
    TAB_ACC_JSON_PATH = fr'{PROJ_USER_PATH}\tab_acc_data.json'
    SETTING_INI_PATH = fr'{PROJ_USER_PATH}\setting.ini'
    VER_ADAPTATION_JSON_PATH = fr'{PROJ_USER_PATH}\version_adaptation.json'
    REMOTE_SETTING_JSON_PATH = fr'{PROJ_USER_PATH}\remote_setting.json'
    LOCAL_SETTING_YML_PATH = fr'{PROJ_USER_PATH}\local_setting.yml'
