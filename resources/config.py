import os

current_file_dir = os.path.dirname(os.path.abspath(__file__))


class Config:
    GITHUB_REPO = "https://github.com/wfql1024/MultiWeChatManager"
    BILIBILI_SPACE = "https://space.bilibili.com/3546733357304606"
    VIDEO_TUTORIAL_LINK = "https://space.bilibili.com/3546733357304606"
    THANKS_TEXT = ("启蒙：\nlyie15（吾爱破解）\n\n"
                   "好朋友、创意及技术探索、免费的测试：\n风_师（哔哩哔哩）\n\n"
                   "子工具提供：\nlyie15(吾爱破解）、Anhkgg（GitHub）、GsuhyFihx（吾爱破解）、"
                   "moyan123（吾爱破解）、Ｋ．雄雄（吾爱破解）\n\n"
                   "技术参考：\n"
                   "https://blog.csdn.net/weixin_43407838/article/details/125255441\n"
                   "https://blog.51cto.com/u_16213427/7225602")
    APP_VERSION = "2.0.0 Beta"
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
