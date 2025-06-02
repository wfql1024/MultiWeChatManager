import os

from public_class.enums import LocalCfg, SW, SwStates
from resources import constants

# 获取屏幕缩放因子
SCALE_FACTOR = constants.get_scale_factor()
current_file_dir = os.path.dirname(os.path.abspath(__file__))


class Config:
    VER_STATUS = 'Beta'

    INI_DEFAULT_VALUE = {
        LocalCfg.GLOBAL_SECTION: {
            LocalCfg.SCREEN_SIZE: f"1920*1080",
            LocalCfg.HIDE_WND: "False",
            LocalCfg.ENABLE_NEW_FUNC: "True",
            LocalCfg.ROOT_TAB: "login",
            LocalCfg.MNG_TAB: "acc",
            LocalCfg.LOGIN_TAB: SW.WECHAT,
            LocalCfg.SCALE: "auto",
            LocalCfg.SIGN_VISIBLE: "True",
            LocalCfg.HIDDEN_SORT: "#0,True",
            LocalCfg.AUTO_START_SORT: "#0,True",
            LocalCfg.ENABLE_SORT: "#0,True",
            LocalCfg.DISABLE_SORT: "#0,True",
            LocalCfg.ALL_SORT: "#0,True",
            LocalCfg.AUTO_PRESS: "True",
            LocalCfg.CALL_MODE: "HANDLE",
            LocalCfg.NEXT_CHECK_TIME: None,
            LocalCfg.USE_PROXY: "True",
            LocalCfg.USE_TXT_AVT: True,
        },
        SW.DEFAULT: {
            LocalCfg.VIEW: "tree",
            LocalCfg.LOGIN_SORT: "配置,True",
            LocalCfg.LOGOUT_SORT: "配置,True",
            LocalCfg.LOGIN_SIZE: f"{int(280 * SCALE_FACTOR)}*{int(380 * SCALE_FACTOR)}",
            LocalCfg.REST_MULTIRUN_MODE: "python",
            LocalCfg.STATE: SwStates.VISIBLE
        }
    }

    PROJ_PATH = os.path.abspath(os.path.join(current_file_dir, '..'))
    PROJ_EXTERNAL_RES_PATH = fr'{PROJ_PATH}/external_res'
    PROJ_USER_PATH = fr'{PROJ_PATH}/user_files'
    PROJ_META_PATH = fr'{PROJ_PATH}/.meta'

    HANDLE_EXE_PATH = fr'{PROJ_EXTERNAL_RES_PATH}/handle.exe'
    WECHAT_DUMP_EXE_PATH = fr'{PROJ_EXTERNAL_RES_PATH}/wechat-dump-rs.exe'
    VERSION_FILE = fr'{PROJ_META_PATH}/version.txt'
    PROJ_ICO_PATH = fr'{PROJ_EXTERNAL_RES_PATH}/JFMC.ico'
    REWARDS_PNG_PATH = fr'{PROJ_EXTERNAL_RES_PATH}/Rewards.png'
    TASK_TP_XML_PATH = fr'{PROJ_USER_PATH}/task_template.xml'
    STATISTIC_JSON_PATH = fr'{PROJ_USER_PATH}/statistics.json'
    TAB_ACC_JSON_PATH = fr'{PROJ_USER_PATH}/tab_acc_data.json'
    SETTING_INI_PATH = fr'{PROJ_USER_PATH}/setting.ini'
    VER_ADAPTATION_JSON_PATH = fr'{PROJ_USER_PATH}/version_adaptation.json'
    REMOTE_SETTING_JSON_PATH = fr'{PROJ_USER_PATH}/remote_setting.json'
    EXTRA_SETTING_JSON_PATH = fr'{PROJ_USER_PATH}/extra_setting.json'
    LOCAL_SETTING_JSON_PATH = fr'{PROJ_USER_PATH}/local_setting.json'
