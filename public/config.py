import configparser
import ctypes
import os
import platform
import tkinter as tk
import winreg

from public.enums import LocalCfg, SW, SwStates, MultirunMode


# 如需使用缩放因子，请直接拷贝以下部分*****************************************************************
def get_scale_factor():
    """
    获取屏幕缩放因子，根据不同系统版本自动选择适配方法：
    - Windows 7：使用注册表获取缩放因子，精确但仅适用于早期系统。
    - Windows 10 及以上：使用 ctypes 调用 shcore 获取缩放因子，更准确。
    - 其他情况：返回默认缩放因子 1。
    """
    # 获取用户设置的缩放因子
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    proj_path = os.path.abspath(os.path.join(current_file_dir, '..'))
    setting_ini_path = fr'{proj_path}\user_files\setting.ini'
    scale = "auto"
    if os.path.exists(setting_ini_path):
        try:
            config = configparser.ConfigParser()
            config.read(setting_ini_path)
            scale = int(config['global']['scale'])
        except Exception as e:
            print(e)
            scale = "auto"

    # 找不到用户的设置或用户选择auto
    if scale == "auto":
        version = int(platform.release())  # 获取 Windows 版本号
        if version == 7:
            # Windows 7 下，使用注册表获取缩放因子
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as key:
                    log_pixels, _ = winreg.QueryValueEx(key, "LogPixels")
                    return log_pixels / 96  # 96 DPI 是标准 100%
            except FileNotFoundError as e:
                print(f"无法从注册表获取缩放因子: {e}")
                return 1
        elif version >= 10:
            # Windows 10 及以上，使用 ctypes 调用 shcore 获取缩放因子
            try:
                return float(ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100)
            except Exception as e:
                print(f"无法从 shcore 获取缩放因子: {e}")
                return 1
        else:
            # 其他系统返回默认缩放因子
            return 1
    else:
        # 用户选择了具体的缩放因子
        return int(scale) / 100


# 获取屏幕缩放因子
SCALE_FACTOR = get_scale_factor()


def scale_dict(d, sf):
    return {k: int(v * sf) for k, v in d.items()}


# 获取屏幕缩放因子
current_file_dir = os.path.dirname(os.path.abspath(__file__))


class Config:
    VER_STATUS = 'Beta'

    INI_DEFAULT_VALUE = {
        # 默认为空的可不写
        LocalCfg.GLOBAL_SECTION: {
            LocalCfg.SCREEN_SIZE: f"1920*1080",
            LocalCfg.USE_PROXY: False,
            # -软件相关
            LocalCfg.ENABLE_NEW_FUNC: True,
            LocalCfg.USED_TRAY: False,
            LocalCfg.USED_REFRESH: False,
            LocalCfg.USED_SIDEBAR: False,
            # -排序相关
            LocalCfg.HIDDEN_SORT: "#0,True",
            LocalCfg.AUTO_START_SORT: "#0,True",
            LocalCfg.ENABLE_SORT: "#0,True",
            LocalCfg.DISABLE_SORT: "#0,True",
            LocalCfg.ALL_SORT: "#0,True",
            # -标签页相关
            LocalCfg.ROOT_TAB: "login",
            LocalCfg.MNG_TAB: "acc",
            LocalCfg.LOGIN_TAB: SW.WECHAT,
            # -视图相关
            LocalCfg.SCALE: "auto",
            LocalCfg.SIGN_VISIBLE: True,
            LocalCfg.USE_TXT_AVT: True,
            # -登录相关
            LocalCfg.HIDE_WND: False,
            LocalCfg.KILL_IDLE_LOGIN_WND: False,
            LocalCfg.UNLOCK_CFG: False,
            LocalCfg.ALL_HAS_MUTEX: True,
            LocalCfg.CALL_MODE: "HANDLE",
            LocalCfg.AUTO_PRESS: True,
        },
        SW.DEFAULT: {
            LocalCfg.VIEW: "tree",
            LocalCfg.LOGIN_SORT: "配置,False",
            LocalCfg.LOGOUT_SORT: "配置,False",
            LocalCfg.LOGIN_SIZE: f"{int(280 * SCALE_FACTOR)}*{int(380 * SCALE_FACTOR)}",
            LocalCfg.REST_MULTIRUN_MODE: MultirunMode.BUILTIN,
            LocalCfg.STATE: SwStates.VISIBLE,
            LocalCfg.COEXIST_MODE: "default"
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
    FEEDBACK_PNG_PATH = fr'{PROJ_EXTERNAL_RES_PATH}/Feedback.png'
    TASK_TP_XML_PATH = fr'{PROJ_USER_PATH}/task_template.xml'
    STATISTIC_JSON_PATH = fr'{PROJ_USER_PATH}/statistics.json'
    TAB_ACC_JSON_PATH = fr'{PROJ_USER_PATH}/tab_acc_data.json'
    SETTING_INI_PATH = fr'{PROJ_USER_PATH}/setting.ini'
    VER_ADAPTATION_JSON_PATH = fr'{PROJ_USER_PATH}/version_adaptation.json'
    REMOTE_SETTING_JSON_PATH = fr'{PROJ_USER_PATH}/remote_setting.json'
    EXTRA_SETTING_JSON_PATH = fr'{PROJ_USER_PATH}/extra_setting.json'
    LOCAL_SETTING_JSON_PATH = fr'{PROJ_USER_PATH}/local_setting.json'

    # 尺寸定义
    SF = SCALE_FACTOR

    # 尺寸定义
    PROJ_WND_SIZE = (int(500 * SF), int(700 * SF))  # 程序窗口尺寸
    LOADING_WND_SIZE = (int(240 * SF), int(80 * SF))  # 登录窗口尺寸
    SETTING_WND_SIZE = (int(750 * SF), int(210 * SF))  # 设置窗口尺寸
    UPDATE_LOG_WND_SIZE = (int(480 * SF), int(400 * SF))  # 更新日志窗口尺寸
    ABOUT_WND_SIZE = (int(500 * SF), int(540 * SF))  # 关于窗口尺寸
    DEBUG_WND_SIZE = (int(800 * SF), int(600 * SF))  # 调试窗口尺寸
    DETAIL_WND_SIZE = (int(240 * SF), int(360 * SF))  # 详情窗口尺寸
    STATISTIC_WND_SIZE = (int(360 * SF), int(432 * SF))  # 统计窗口尺寸
    ACC_MNG_WND_SIZE = (int(400 * SF), int(550 * SF))  # 账号管理窗口尺寸
    SIDEBAR_WIDTH = int(60 * SF)  # 侧边栏宽度

    LOADING_PRG_LEN = int(200 * SF)  # 加载进度条长度

    ERR_LBL_PAD_X = int(20 * SF)  # 错误标签内边距
    ERR_LBL_PAD_Y = int(20 * SF)  # 错误标签内边距
    BTN_FRAME_PAD = (int(4 * SF), int(4 * SF))  # 按钮框架内边距
    CUS_BTN_PAD_X = int(4 * SF)  # 定制按钮内边距x
    CUS_BTN_PAD_Y = int(4 * SF)  # 定制按钮内边距y
    CUS_BTN_PAD = (CUS_BTN_PAD_X, CUS_BTN_PAD_Y)  # 普通按钮内边距
    TK_BTN_WIDTH = int(10 * (1 + (SF - 1) / 3))  # 普通按钮宽度
    CUS_BTN_WIDTH = int(50 * SF)  # 定制按钮宽度

    LOG_IO_LBL_FONTSIZE = 10  # 登录登出表标签字体大小
    LOG_IO_FRM_PAD_X = (int(12 * SF), int(0 * SF))  # 登录登出表框架左右边距
    LOG_IO_FRM_PAD_Y = (int(4 * SF), int(4 * SF))  # 登录登出表框架上下边距
    LOG_IO_LBL_PAD_Y = (int(8 * SF), int(8 * SF))  # 登录登出表标签上下内边距

    AVT_SIZE = (int(32 * SF), int(32 * SF))  # 头像标签大小

    CLZ_ROW_FRM_PAD_Y = (int(2 * SF), int(2 * SF))  # 经典视图行框架上下内边距
    CLZ_ROW_LBL_PAD_X = (int(0 * SF), int(8 * SF))  # 经典视图行标签左右内边距
    CLZ_CFG_LBL_PAD_X = (int(4 * SF), int(4 * SF))  # 经典视图配置标签左右内边距

    TREE_ROW_HEIGHT = int(40 * SF)  # 列表视图行高度

    # 原始值（未缩放）
    _COLUMN_WIDTH = {
        "ID": 45,
        "SEC_ID": 60,
        "配置": 116,
        "PID": 64,
        "展示": 122,
        "隐藏": 64,
        "自启动": 64,
        "快捷键": 64,
        "状态": 64,
        "版本": 100,
        "安装路径": 160,
        "存储路径": 160,
        "DLL路径": 160,
    }
    _COLUMN_MIN_WIDTH = {
        "ID": 45,
        "SEC_ID": 60,
        "配置": 116,
        "PID": 64,
        "展示": 112,
        "隐藏": 64,
        "自启动": 64,
        "快捷键": 64,
        "状态": 64,
        "版本": 100,
        "安装路径": 160,
        "存储路径": 160,
        "DLL路径": 160,
    }
    # 统一缩放
    COLUMN_WIDTH = scale_dict(_COLUMN_WIDTH, SF)
    COLUMN_MIN_WIDTH = scale_dict(_COLUMN_MIN_WIDTH, SF)

    TREE_ID_MIN_WIDTH = int(45 * SF)  # 列表视图ID列最小宽度
    TREE_ID_WIDTH = int(45 * SF)  # 列表视图ID列宽度
    TREE_CFG_MIN_WIDTH = int(116 * SF)  # 列表视图配置列最小宽度
    TREE_CFG_WIDTH = int(116 * SF)  # 列表视图配置列宽度
    TREE_PID_MIN_WIDTH = int(64 * SF)  # 列表视图PID列最小宽度
    TREE_PID_WIDTH = int(64 * SF)  # 列表视图PID列宽度
    TREE_DSP_MIN_WIDTH = int(112 * SF)  # 列表视图展示列最小宽度
    TREE_DSP_WIDTH = int(122 * SF)  # 列表视图展示列宽度

    LOGO_SIZE = (int(48 * SF), int(48 * SF))  # 程序logo大小
    GRID_PAD = (int(4 * SF), int(4 * SF))  # 链接网格左右/上下边距

    W_GRID_PACK = {
        "sticky": "w",
        "padx": GRID_PAD,
        "pady": GRID_PAD
    }
    WE_GRID_PACK = {
        "sticky": "we",
        "padx": GRID_PAD,
        "pady": GRID_PAD
    }
    NEWS_GRID_PACK = {
        "sticky": "news",
        "padx": GRID_PAD,
        "pady": GRID_PAD
    }

    # 框架
    FRM_PAD = (int(16 * SF), int(16 * SF))  # 常规框架内边距
    FRM_PACK = {
        "fill": tk.BOTH,
        "expand": True
    }

    L_FRM_PAD = (int(0 * SF), int(0 * SF), int(12 * SF), int(0 * SF))  # 常规左框架内边距
    R_FRM_PAD = (int(12 * SF), int(0 * SF), int(0 * SF), int(0 * SF))  # 常规右框架内边距
    T_FRM_PAD = (int(0 * SF), int(0 * SF), int(0 * SF), int(12 * SF))  # 常规上框架内边距
    B_FRM_PAD = (int(0 * SF), int(12 * SF), int(0 * SF), int(0 * SF))  # 常规下框架内边距
    L_FRM_PACK = {
        "side": tk.LEFT,
        "fill": tk.Y,
        "expand": False
    }
    R_FRM_PACK = {
        "side": tk.RIGHT,
        "fill": tk.Y,
        "expand": False
    }
    T_FRM_PACK = {
        "side": tk.TOP,
        "fill": tk.X,
        "expand": False
    }
    B_FRM_PACK = {
        "side": tk.BOTTOM,
        "fill": tk.X,
        "expand": False
    }

    # 控件
    L_PAD_X = (int(12 * SF), int(0 * SF))  # 水平铺设居左控件左右边距
    R_PAD_X = (int(0 * SF), int(12 * SF))  # 水平铺设居右控件左右边距
    T_PAD_Y = (int(12 * SF), int(0 * SF))  # 垂直铺设居上控件上下边距
    B_PAD_Y = (int(0 * SF), int(12 * SF))  # 垂直铺设居下控件上下边距

    L_WGT_PACK = {
        "side": tk.LEFT,
        "fill": tk.Y,
        "padx": L_PAD_X
    }
    R_WGT_PACK = {
        "side": tk.RIGHT,
        "fill": tk.Y,
        "padx": R_PAD_X
    }
    T_WGT_PACK = {
        "side": tk.TOP,
        "fill": tk.X,
        "pady": T_PAD_Y
    }
    B_WGT_PACK = {
        "side": tk.BOTTOM,
        "fill": tk.X,
        "pady": B_PAD_Y
    }

    IPAD_X = int(6 * SF)  # 水平铺设居右控件内边距
    IPAD_Y = int(6 * SF)  # 垂直铺设居上控件内边距

    FIRST_TITLE_FONTSIZE = 10  # 粗体标题字体大小
    SECOND_TITLE_FONTSIZE = 10  # 标题字体大小
    LINK_FONTSIZE = 9  # 链接字体大小
    LITTLE_FONTSIZE = 8  # 微小字体大小

    STATUS_BAR_BD = 1  # 状态条边框宽度
    STATUS_BAR_HEIGHT = 1  # 状态条高度

    COLOR_DIFF = {
        "selected": (3, 8, 11),
        "hover": (14, 17, 13)
    }
