import os

current_file_dir = os.path.dirname(os.path.abspath(__file__))


class Config:
    VER_STATUS = 'Alpha'

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
        "view": "view"
    }

    INI_DEFAULT_VALUE = {
        "sub_exe": "python",
        "view": "tree"
    }

    JSON_KEY_NOTE = 'note'
    JSON_KEY_PID = 'pid'
    JSON_KEY_NICKNAME = 'nickname'
    JSON_KEY_ALIAS = 'alias'
    JSON_KEY_AVATAR_URL = 'avatar_url'
    JSON_KEY_HAS_MUTEX = 'has_mutex'

    PROJ_PATH = os.path.abspath(os.path.join(current_file_dir, '..'))
    PROJ_USER_PATH = fr'{PROJ_PATH}\user_files'
    PROJ_EXTERNAL_RES_PATH = fr'{PROJ_PATH}\external_res'

    STATISTIC_JSON_PATH = fr'{PROJ_USER_PATH}\statistics.json'
    ACC_DATA_JSON_PATH = fr'{PROJ_USER_PATH}\account_data.json'
    SETTING_INI_PATH = fr'{PROJ_USER_PATH}\setting.ini'
    PROJ_ICO_PATH = fr'{PROJ_EXTERNAL_RES_PATH}\SunnyMultiWxMng.ico'
    REWARDS_PNG_PATH = fr'{PROJ_EXTERNAL_RES_PATH}\Rewards.png'
    VERSION_FILE = fr'{PROJ_PATH}\version.txt'
    VER_CONFIG_JSON_PATH = fr'{PROJ_USER_PATH}\version_config.json'
    VER_ADAPTATION_JSON_PATH = fr'{PROJ_USER_PATH}\version_adaptation.json'
    UPDATE_LOG_PATH = fr'{PROJ_PATH}\update_log.md'
