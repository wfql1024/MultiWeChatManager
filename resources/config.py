import os

current_file_dir = os.path.dirname(os.path.abspath(__file__))


class Config:
    VER_STATUS = 'Beta'
    INI_KEY_CUR_VER = 'current_version'
    INI_KEY_DELAY_TIME = 'delay_time'
    INI_SECTION = 'default'
    INI_KEY_INSTALL_PATH = 'install_path'
    INI_KEY_DATA_PATH = 'data_path'
    INI_KEY_DLL_DIR_PATH = 'dll_dir_path'
    INI_KEY_SCREEN_SIZE = 'screen_size'
    INI_KEY_LOGIN_SIZE = 'login_size'
    INI_KEY_SUB_EXE = 'sub_executable'

    JSON_KEY_NOTE = 'note'
    JSON_KEY_PID = 'pid'
    JSON_KEY_NICKNAME = 'nickname'
    JSON_KEY_ALIAS = 'alias'
    JSON_KEY_AVATAR_URL = 'avatar_url'
    JSON_KEY_HAS_MUTEX = 'has_mutex'

    DEFAULT_SUB_EXE = 'WeChatMultiple_Anhkgg.exe'

    PROJ_PATH = os.path.abspath(os.path.join(current_file_dir, '..'))
    PROJ_USER_PATH = fr'{PROJ_PATH}\user_files'
    PROJ_EXTERNAL_RES_PATH = fr'{PROJ_PATH}\external_res'

    STATISTIC_JSON_PATH = fr'{PROJ_USER_PATH}\statistics.json'
    ACC_DATA_JSON_PATH = fr'{PROJ_USER_PATH}\account_data.json'
    SETTING_INI_PATH = fr'{PROJ_USER_PATH}\setting.ini'
    PROJ_ICO_PATH = fr'{PROJ_EXTERNAL_RES_PATH}\SunnyMultiWxMng.ico'
    REWARDS_PNG_PATH = fr'{PROJ_EXTERNAL_RES_PATH}\Rewards.png'
    VER_CONFIG_JSON_PATH = fr'{PROJ_USER_PATH}\version_config.json'
    VERSION_FILE = fr'{PROJ_PATH}\version.txt'
