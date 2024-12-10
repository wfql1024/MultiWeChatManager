import configparser
import ctypes
import os
import platform
import winreg
import tkinter as tk

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
        config = configparser.ConfigParser()
        config.read(setting_ini_path)
        try:
            scale = int(config['global']['scale'])
        except ValueError:
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
# 如需使用缩放因子，请直接拷贝以上部分*****************************************************************

class Constants:
    SF = SCALE_FACTOR
    # 尺寸定义
    LOADING_LBL_PAD_Y = int(16 * SF)  # 加载标签上下内边距
    LOADING_PRG_PAD_Y = int(8 * SF)  # 加载进度条上下内边距
    LOADING_PRG_LEN = int(200 * SF)  # 加载进度条长度

    PROJ_WND_SIZE = (int(400 * SF), int(550 * SF))  # 程序窗口尺寸
    LOADING_WND_SIZE = (int(240 * SF), int(80 * SF))  # 登录窗口尺寸
    SETTING_WND_SIZE = (int(600 * SF), int(200 * SF))  # 设置窗口尺寸
    UPDATE_LOG_WND_SIZE = (int(480 * SF), int(400 * SF))  # 更新日志窗口尺寸
    ABOUT_WND_SIZE = (int(500 * SF), int(500 * SF))  # 关于窗口尺寸
    DEBUG_WND_SIZE = (int(800 * SF), int(600 * SF))  # 调试窗口尺寸
    DETAIL_WND_SIZE = (int(240 * SF), int(320 * SF))  # 详情窗口尺寸
    STATISTIC_WND_SIZE = (int(336 * SF), int(432 * SF))  # 统计窗口尺寸

    CANVAS_START_POS = (int(0 * SF), int(0 * SF))  # 画布起始位置
    ERR_LBL_PAD_X = int(20 * SF)  # 错误标签内边距
    ERR_LBL_PAD_Y = int(20 * SF)  # 错误标签内边距
    BTN_FRAME_PAD = (int(4 * SF), int(4 * SF))  # 按钮框架内边距
    CUS_BTN_PAD = (int(4 * SF), int(4 * SF))  # 普通按钮内边距
    CUS_BTN_WIDTH = int(
        10 * ((SF - 1) / 3 + 1) if SF > 1 else 10 * (1 - (1 - SF) / 3))  # 普通按钮宽度

    LOG_IO_LBL_FONTSIZE = 10  # 登录登出表标签字体大小
    LOG_IO_FRM_PAD_X = (int(12 * SF), int(0 * SF))  # 登录登出表框架左右边距
    LOG_IO_FRM_PAD_Y = (int(4 * SF), int(4 * SF))  # 登录登出表框架上下边距
    LOG_IO_LBL_PAD_Y = (int(8 * SF), int(8 * SF))  # 登录登出表标签上下内边距

    BLANK_AVT_SIZE = (int(32 * SF), int(32 * SF))  # 空白头像标签大小

    CLZ_ROW_FRM_PAD_Y = (int(2 * SF), int(2 * SF))  # 经典视图行框架上下内边距
    CLZ_ROW_LBL_PAD_X = (int(0 * SF), int(8 * SF))  # 经典视图行标签左右内边距
    CLZ_CFG_LBL_PAD_X = (int(4 * SF), int(4 * SF))  # 经典视图配置标签左右内边距
    CLZ_AVT_LBL_SIZE = (int(32 * SF), int(32 * SF))  # 经典视图头像标签大小

    TREE_ROW_HEIGHT = int(40 * SF)  # 列表视图行高度
    TREE_ID_MIN_WIDTH = int(45 * SF)  # 列表视图ID列最小宽度
    TREE_ID_WIDTH = int(45 * SF)  # 列表视图ID列宽度
    TREE_CFG_MIN_WIDTH = int(116 * SF)  # 列表视图配置列最小宽度
    TREE_CFG_WIDTH = int(116 * SF)  # 列表视图配置列宽度
    TREE_PID_MIN_WIDTH = int(64 * SF)  # 列表视图PID列最小宽度
    TREE_PID_WIDTH = int(64 * SF)  # 列表视图PID列宽度
    TREE_DSP_MIN_WIDTH = int(112 * SF)  # 列表视图展示列最小宽度
    TREE_DSP_WIDTH = int(122 * SF)  # 列表视图展示列宽度
    TREE_AVT_LBL_SIZE = (int(32 * SF), int(32 * SF))  # 列表视图头像标签大小

    DETAIL_AVT_LBL_SIZE = (int(32 * SF), int(32 * SF))  # 详情页头像标签大小

    LOGO_FRM_PAD = (int(16 * SF), int(16 * SF))  # 程序logo框架内边距
    LOGO_SIZE = (int(48 * SF), int(48 * SF))  # 程序logo大小
    BLANK_LOGO_SIZE = (int(48 * SF), int(48 * SF))
    CONTENT_FRM_PAD = (int(4 * SF), int(4 * SF))  # 内容框架内边距
    VER_FRM_PAD_Y = (int(24 * SF), int(0 * SF))  # 版本框架上下内边距
    SECOND_TITLE_PAD_Y = (int(8 * SF), int(0 * SF))  # 标题框架上下内边距
    ABOUT_GRID_PAD_X = (int(4 * SF), int(4 * SF))  # 内部小网格左右内边距
    ABOUT_BTM_FRM_PAD_X = (int(0 * SF), int(16 * SF))  # 关于页底部左右内边距
    ABOUT_BTM_FRM_PAD_Y = (int(16 * SF), int(16 * SF))  # 关于页底部上下内边距


    # 框架
    NOR_FRM_PAD = (int(16 * SF), int(16 * SF))  # 常规框架内边距
    NOR_L_FRM_PAD = (int(0 * SF), int(0 * SF), int(12 * SF), int(0 * SF))  # 常规左框架内边距
    NOR_R_FRM_PAD = (int(12 * SF), int(0 * SF), int(0 * SF), int(0 * SF))  # 常规右框架内边距
    NOR_T_FRM_PAD = (int(0 * SF), int(0 * SF), int(0 * SF), int(12 * SF))  # 常规上框架内边距
    NOR_B_FRM_PAD = (int(0 * SF), int(12 * SF), int(0 * SF), int(0 * SF))  # 常规下框架内边距
    NOR_L_FRM_PACK = {
        "side": tk.LEFT,
        "fill": tk.Y,
        "expand": False
    }
    NOR_R_FRM_PACK = {
        "side": tk.RIGHT,
        "fill": tk.Y,
        "expand": False
    }
    NOR_T_FRM_PACK = {
        "side": tk.TOP,
        "fill": tk.X,
        "expand": False
    }
    NOR_B_FRM_PACK = {
        "side": tk.BOTTOM,
        "fill": tk.X,
        "expand": False
    }

    # 控件
    NOR_L_HOR_PAD_X = (int(12 * SF), int(0 * SF))  # 水平铺设居左控件左右边距
    NOR_R_HOR_PAD_X = (int(0 * SF), int(12 * SF))  # 水平铺设居右控件左右边距
    NOR_T_VER_PAD_Y = (int(12 * SF), int(0 * SF))  # 垂直铺设居上控件上下边距
    NOR_B_VER_PAD_Y = (int(0 * SF), int(12 * SF))  # 垂直铺设居下控件上下边距
    NOR_L_HOR_IPAD_X = int(6 * SF)  # 水平铺设居左控件内边距
    NOR_R_HOR_IPAD_X = int(6 * SF)  # 水平铺设居右控件内边距
    NOR_T_VER_IPAD_Y = int(6 * SF)  # 垂直铺设居上控件内边距
    NOR_B_VER_IPAD_Y = int(6 * SF)  # 垂直铺设居下控件内边距

    NOR_L_HOR_WGT_PACK = {
        "side": tk.LEFT,
        "fill": tk.Y,
        "padx": NOR_L_HOR_PAD_X
    }
    NOR_R_HOR_WGT_PACK = {
        "side": tk.RIGHT,
        "fill": tk.Y,
        "padx": NOR_R_HOR_PAD_X
    }
    NOR_T_VER_WGT_PACK = {
        "side": tk.TOP,
        "fill": tk.X,
        "pady": NOR_T_VER_PAD_Y
    }
    NOR_B_VER_WGT_PACK = {
        "side": tk.BOTTOM,
        "fill": tk.X,
        "pady": NOR_B_VER_PAD_Y
    }

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
