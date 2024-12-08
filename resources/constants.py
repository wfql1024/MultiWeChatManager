import ctypes


class Constants:
    # 尺寸定义
    SCALE_FACTOR = float(ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100)  # 获取屏幕缩放因子

    PROJ_WND_SIZE = (int(400 * SCALE_FACTOR), int(550 * SCALE_FACTOR))  # 程序窗口尺寸
    ABOUT_WND_SIZE = (int(500 * SCALE_FACTOR), int(500 * SCALE_FACTOR))  # 关于窗口尺寸
    SETTING_WND_SIZE = (int(600 * SCALE_FACTOR), int(200 * SCALE_FACTOR))  # 设置窗口尺寸
    UPDATE_LOG_WND_SIZE = (int(480 * SCALE_FACTOR), int(400 * SCALE_FACTOR))  # 更新日志窗口尺寸

    CANVAS_START_POS = (int(12 * SCALE_FACTOR), int(0 * SCALE_FACTOR))  # 画布起始位置
    ERR_LBL_PAD_X = int(20 * SCALE_FACTOR)  # 错误标签内边距
    ERR_LBL_PAD_Y = int(20 * SCALE_FACTOR)  # 错误标签内边距
    BTN_FRAME_PAD = (int(4 * SCALE_FACTOR), int(4 * SCALE_FACTOR))  # 按钮框架内边距
    CUS_BTN_PAD = (int(4 * SCALE_FACTOR), int(4 * SCALE_FACTOR))  # 普通按钮内边距
    CUS_BTN_WIDTH = int(10 * ((SCALE_FACTOR - 1) / 2.5 + 1) if SCALE_FACTOR > 1 else (1 - (1 - SCALE_FACTOR) / 2.5))  # 普通按钮宽度

    LOG_IO_LBL_FONTSIZE = 10  # 登录登出表标签字体大小
    LOG_IO_FRM_PAD_X = (int(12 * SCALE_FACTOR), int(0 * SCALE_FACTOR))  # 登录登出表框架左右边距
    LOG_IO_FRM_PAD_Y = (int(4 * SCALE_FACTOR), int(4 * SCALE_FACTOR))  # 登录登出表框架上下边距
    LOG_IO_LBL_PAD_Y = (int(8 * SCALE_FACTOR), int(8 * SCALE_FACTOR))  # 登录登出表标签上下内边距

    BLANK_AVT_SIZE = (int(32 * SCALE_FACTOR), int(32 * SCALE_FACTOR))  # 列表视图头像标签大小

    CLZ_ROW_FRM_PAD_Y = (int(2 * SCALE_FACTOR), int(2 * SCALE_FACTOR))  # 经典视图行框架上下内边距
    CLZ_ROW_LBL_PAD_X = (int(0 * SCALE_FACTOR), int(8 * SCALE_FACTOR))  # 经典视图行标签左右内边距
    CLZ_CFG_LBL_PAD_X = (int(4 * SCALE_FACTOR), int(4 * SCALE_FACTOR))  # 经典视图配置标签左右内边距
    CLZ_AVT_LBL_SIZE = (int(32 * SCALE_FACTOR), int(32 * SCALE_FACTOR))  # 经典视图头像标签大小

    TREE_ROW_HEIGHT = int(40 * SCALE_FACTOR)  # 列表视图行高度
    TREE_ID_MIN_WIDTH = int(52 * SCALE_FACTOR)  # 列表视图ID列最小宽度
    TREE_ID_WIDTH = int(52 * SCALE_FACTOR)  # 列表视图ID列宽度
    TREE_CFG_MIN_WIDTH = int(116 * SCALE_FACTOR)  # 列表视图配置列最小宽度
    TREE_CFG_WIDTH = int(116 * SCALE_FACTOR)  # 列表视图配置列宽度
    TREE_PID_MIN_WIDTH = int(64 * SCALE_FACTOR)  # 列表视图PID列最小宽度
    TREE_PID_WIDTH = int(64 * SCALE_FACTOR)  # 列表视图PID列宽度
    TREE_DSP_MIN_WIDTH = int(112 * SCALE_FACTOR)  # 列表视图展示列最小宽度
    TREE_DSP_WIDTH = int(122 * SCALE_FACTOR)  # 列表视图展示列宽度
    TREE_AVT_LBL_SIZE = (int(32 * SCALE_FACTOR), int(32 * SCALE_FACTOR))  # 列表视图头像标签大小

    LOGO_FRM_PAD = (int(16 * SCALE_FACTOR), int(16 * SCALE_FACTOR))  # 程序logo框架内边距
    LOGO_SIZE = (int(48 * SCALE_FACTOR), int(48 * SCALE_FACTOR))  # 程序logo大小
    BLANK_LOGO_SIZE = (int(48 * SCALE_FACTOR), int(48 * SCALE_FACTOR))
    CONTENT_FRM_PAD = (int(4 * SCALE_FACTOR), int(4 * SCALE_FACTOR))  # 内容框架内边距
    VER_FRM_PAD_Y = (int(24 * SCALE_FACTOR), int(0 * SCALE_FACTOR))  # 版本框架上下内边距
    SECOND_TITLE_PAD_Y = (int(8 * SCALE_FACTOR), int(0 * SCALE_FACTOR))  # 标题框架上下内边距
    ABOUT_GRID_PAD_X = (int(4 * SCALE_FACTOR), int(4 * SCALE_FACTOR))  # 内部小网格左右内边距
    ABOUT_BTM_FRM_PAD_X = (int(0 * SCALE_FACTOR), int(16 * SCALE_FACTOR))  # 关于页底部左右内边距
    ABOUT_BTM_FRM_PAD_Y = (int(16 * SCALE_FACTOR), int(16 * SCALE_FACTOR))  # 关于页底部上下内边距
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
