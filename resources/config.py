import os

from resources import constants
from public_class.enums import Keywords, SW

# 获取屏幕缩放因子
SCALE_FACTOR = constants.get_scale_factor()
current_file_dir = os.path.dirname(os.path.abspath(__file__))


class Config:
    VER_STATUS = 'Beta'

    INI_DEFAULT_VALUE = {
        Keywords.SCREEN_SIZE: f"1920*1080",
        Keywords.HIDE_WND: "False",
        Keywords.ENABLE_NEW_FUNC: "True",
        Keywords.TAB: SW.WECHAT,
        Keywords.SCALE: "auto",
        Keywords.SIGN_VISIBLE: "True",
        Keywords.HIDDEN_SORT: "#0,True",
        Keywords.AUTO_START_SORT: "#0,True",
        Keywords.ALL_SORT: "#0,True",
        Keywords.AUTO_PRESS: "True",
        Keywords.CALL_MODE: "HANDLE",
        Keywords.NEXT_CHECK_TIME: None,

        SW.WECHAT: {
            Keywords.VIEW: "tree",
            Keywords.LOGIN_SORT: "配置,True",
            Keywords.LOGOUT_SORT: "配置,True",
            Keywords.LOGIN_SIZE: f"{int(280 * SCALE_FACTOR)}*{int(380 * SCALE_FACTOR)}",
            Keywords.REST_MODE: "python",
        },
        SW.WEIXIN: {
            Keywords.VIEW: "tree",
            Keywords.LOGIN_SORT: "配置,True",
            Keywords.LOGOUT_SORT: "配置,True",
            Keywords.LOGIN_SIZE: f"{int(280 * SCALE_FACTOR)}*{int(380 * SCALE_FACTOR)}",
            Keywords.REST_MODE: "handle",
        },
    }

    PROJ_PATH = os.path.abspath(os.path.join(current_file_dir, '..'))
    PROJ_EXTERNAL_RES_PATH = fr'{PROJ_PATH}/external_res'
    PROJ_USER_PATH = fr'{PROJ_PATH}/user_files'
    PROJ_META_PATH = fr'{PROJ_PATH}/.meta'

    HANDLE_EXE_PATH = fr'{PROJ_EXTERNAL_RES_PATH}/handle.exe'
    WECHAT_DUMP_EXE_PATH = fr'{PROJ_EXTERNAL_RES_PATH}/wechat-dump-rs.exe'
    VERSION_FILE = fr'{PROJ_META_PATH}/version.txt'
    PROJ_ICO_PATH = fr'{PROJ_EXTERNAL_RES_PATH}/SunnyMultiWxMng.ico'
    REWARDS_PNG_PATH = fr'{PROJ_EXTERNAL_RES_PATH}/Rewards.png'
    TASK_TP_XML_PATH = fr'{PROJ_USER_PATH}/task_template.xml'
    STATISTIC_JSON_PATH = fr'{PROJ_USER_PATH}/statistics.json'
    TAB_ACC_JSON_PATH = fr'{PROJ_USER_PATH}/tab_acc_data.json'
    SETTING_INI_PATH = fr'{PROJ_USER_PATH}/setting.ini'
    VER_ADAPTATION_JSON_PATH = fr'{PROJ_USER_PATH}/version_adaptation.json'
    REMOTE_SETTING_JSON_PATH = fr'{PROJ_USER_PATH}/remote_setting.json'
    LOCAL_SETTING_YML_PATH = fr'{PROJ_USER_PATH}/local_setting.yml'
