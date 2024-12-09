import os
from resources import constants

# 获取屏幕缩放因子
SCALE_FACTOR = constants.get_scale_factor()
current_file_dir = os.path.dirname(os.path.abspath(__file__))

class Config:
    VER_STATUS = 'Beta'

    INI_GLOBAL_SECTION = 'global'

    INI_KEY_INSTALL_PATH = 'install_path'
    INI_KEY_DATA_PATH = 'data_path'
    INI_KEY_DLL_DIR_PATH = 'dll_dir_path'
    INI_KEY_SCREEN_SIZE = 'screen_size'
    INI_KEY_LOGIN_SIZE = 'login_size'
    INI_KEY_SUB_EXE = 'sub_executable'
    INI_KEY_ENABLE_NEW_FUNC = 'enable_new_func'

    INI_KEY = {
        "sub_exe": "sub_executable",
        "view": "view",
        "enable_new_func": "enable_new_func",
        "login_col_to_sort": "login_col_to_sort",
        "logout_col_to_sort": "logout_col_to_sort",
        "login_sort_asc": "login_sort_asc",
        "logout_sort_asc": "logout_sort_asc",
        "tab": "tab",
        "login_size": "login_size",
        "scale": "scale"
    }

    INI_DEFAULT_VALUE = {
        "sub_exe": "python",
        "enable_new_func": "true",
        "tab": "WeChat",
        "scale": "auto",
        "WeChat": {
            "view": "tree",
            "login_col_to_sort": "配置",
            "logout_col_to_sort": "配置",
            "login_sort_asc": "true",
            "logout_sort_asc": "true",
            "login_size": f"{int(280 * SCALE_FACTOR)}*{int(380 * SCALE_FACTOR)}",
            "sub_exe": "python",
        },
        "Weixin": {
            "view": "tree",
            "login_col_to_sort": "配置",
            "logout_col_to_sort": "配置",
            "login_sort_asc": "true",
            "logout_sort_asc": "true",
            "login_size": f"{int(280 * SCALE_FACTOR)}*{int(380 * SCALE_FACTOR)}",
            "sub_exe": "handle",
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
    STATISTIC_JSON_PATH = fr'{PROJ_USER_PATH}\statistics.json'
    TAB_ACC_JSON_PATH = fr'{PROJ_USER_PATH}\tab_acc_data.json'
    SETTING_INI_PATH = fr'{PROJ_USER_PATH}\setting.ini'
    VER_ADAPTATION_JSON_PATH = fr'{PROJ_USER_PATH}\version_adaptation.json'
    REMOTE_SETTING_JSON_PATH = fr'{PROJ_USER_PATH}\remote_setting.json'
    LOCAL_SETTING_YML_PATH = fr'{PROJ_USER_PATH}\local_setting.yml'
