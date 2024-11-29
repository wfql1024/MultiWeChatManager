import os

current_file_dir = os.path.dirname(os.path.abspath(__file__))


class Config:
    VER_STATUS = 'Beta'

    INI_SECTION = 'default'
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
    }

    INI_DEFAULT_VALUE = {
        "sub_exe": "python",
        "view": "tree",
        "enable_new_func": "true",
        "login_col_to_sort": "配置",
        "logout_col_to_sort": "配置",
        "login_sort_asc": "true",
        "logout_sort_asc": "true",
    }

    PROJ_PATH = os.path.abspath(os.path.join(current_file_dir, '..'))
    PROJ_EXTERNAL_RES_PATH = fr'{PROJ_PATH}\external_res'
    PROJ_USER_PATH = fr'{PROJ_PATH}\user_files'

    HANDLE_EXE_PATH = fr'{PROJ_EXTERNAL_RES_PATH}\handle.exe'
    VERSION_FILE = fr'{PROJ_PATH}\version.txt'
    PROJ_ICO_PATH = fr'{PROJ_EXTERNAL_RES_PATH}\SunnyMultiWxMng.ico'
    REWARDS_PNG_PATH = fr'{PROJ_EXTERNAL_RES_PATH}\Rewards.png'
    STATISTIC_JSON_PATH = fr'{PROJ_USER_PATH}\statistics.json'
    ACC_DATA_JSON_PATH = fr'{PROJ_USER_PATH}\account_data.json'
    SETTING_INI_PATH = fr'{PROJ_USER_PATH}\setting.ini'
    VER_ADAPTATION_JSON_PATH = fr'{PROJ_USER_PATH}\version_adaptation.json'
