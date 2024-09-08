import os

current_file_dir = os.path.dirname(os.path.abspath(__file__))


class Config:
    INI_KEY_DELAY_TIME = 'delay_time'
    VIDEO_TUTORIAL_LINK = "https://space.bilibili.com/3546733357304606"
    APP_VERSION = "v2.0.8 Beta"
    INI_SECTION = 'default'
    INI_KEY_INSTALL_PATH = 'install_path'
    INI_KEY_DATA_PATH = 'data_path'
    INI_KEY_VER_PATH = 'last_ver_path'
    INI_KEY_SCREEN_SIZE = 'screen_size'
    INI_KEY_LOGIN_SIZE = 'login_size'
    INI_KEY_SUB_EXE = 'sub_executable'

    DEFAULT_SUB_EXE = 'WeChatMultiple_Anhkgg.exe'

    PROJ_PATH = os.path.abspath(os.path.join(current_file_dir, '..'))
    PROJ_USER_PATH = fr'{PROJ_PATH}\user_files'
    PROJ_EXTERNAL_RES_PATH = fr'{PROJ_PATH}\external_res'

    ACC_DATA_JSON_PATH = fr'{PROJ_USER_PATH}\account_data.json'
    SETTING_INI_PATH = fr'{PROJ_USER_PATH}\setting.ini'
    PROJ_ICO_PATH = fr'{PROJ_EXTERNAL_RES_PATH}\SunnyMultiWxMng.ico'
    REWARDS_PNG_PATH = fr'{PROJ_EXTERNAL_RES_PATH}\Rewards.png'
