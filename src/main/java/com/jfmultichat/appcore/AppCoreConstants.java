package com.jfmultichat.appcore;

/**
 * AppCore 常量定义 — 全局配置 JSON 的键名及默认值
 */
public final class AppCoreConstants {

    private AppCoreConstants() {}

    // ==================== RootConfig 字段 ====================

    public static final class RootCfgKey {
        private RootCfgKey() {}

        public static final String USER_DATA_PATH = "user_data_path";
        public static final String PROXY_IP = "proxy_ip";
        public static final String PROXY_PORT = "proxy_port";
        public static final String USE_PROXY = "use_proxy";
        public static final String REMOTE_SW_URL = "remote_sw_url";
        public static final String REMOTE_GLOBAL_URL = "remote_global_url";
        public static final String REMOTE_SW_NS = "RemoteSw";
        public static final String REMOTE_GLOBAL_NS = "RemoteGlobal";
        public static final String APP_CURRENT_VERSION = "app_current_version";
    }

    // ==================== GlobalSetting 键 ====================

    public static final class GlobalSettingKey {
        private GlobalSettingKey() {}

        public static final String THEME = "theme";
        public static final String SCREEN_SIZE = "screen_size";
        public static final String IN_TRAY = "in_tray";
        public static final String NEXT_CHECK_TIME = "next_check_time";
        public static final String ALL_HAS_MUTEX = "all_has_mutex";
        public static final String KILL_IDLE_LOGIN_WND = "kill_idle_login_wnd";
        public static final String UNLOCK_CFG = "unlock_cfg";
        public static final String AUTO_PRESS = "auto_press";
        public static final String USE_TXT_AVT = "use_txt_avt";
        public static final String PREFER_COEXIST = "prefer_coexist";
        public static final String PROXY_IP = "proxy_ip";
        public static final String PROXY_PORT = "proxy_port";
        public static final String USE_PROXY = "use_proxy";
    }

    // ==================== Sw 级 Setting 键 ====================

    public static final class SwSettingKey {
        private SwSettingKey() {}

        public static final String STATE = "state";
        public static final String INST_PATH = "inst_path";
        public static final String DATA_DIR = "data_dir";
        public static final String DLL_DIR = "dll_dir";
        public static final String REMARK = "remark";
        public static final String COEXIST_MODE = "coexist_mode";
        public static final String REST_MULTIRUN_MODE = "rest_multirun_mode";
        public static final String LOGIN_SIZE = "login_size";
        public static final String CLICK_BTNS = "click_btns";
        public static final String AUTO_START = "auto_start";
    }

    // ==================== RemoteGlobal 键 ====================

    public static final class RemoteGlobalKey {
        private RemoteGlobalKey() {}

        public static final String SP_SW = "sp_sw";
        public static final String UPDATE = "update";
        public static final String THANKS = "thanks";
        public static final String ABOUT = "about";
    }

    // ==================== RemoteSw 键 ====================

    public static final class RemoteSwKey {
        private RemoteSwKey() {}

        public static final String ALIAS = "alias";
        public static final String EXECUTABLE = "executable";
        public static final String EXECUTABLE_WILDCARDS = "executable_wildcards";
        public static final String DATA_DIR_NAME = "data_dir_name";
        public static final String MUTEX_HANDLES = "mutex_handles";
        public static final String CONFIG_HANDLES = "config_handles";
        public static final String CONFIG_ADDRESSES = "config_addresses";
        public static final String MUTEX_HANDLE_WILDCARDS = "mutex_handle_wildcards";
        public static final String CONFIG_HANDLE_WILDCARDS = "config_handle_wildcards";
        public static final String EXCLUDED_DIRS = "excluded_dirs";
        public static final String COEXIST = "coexist";
        public static final String MULTI = "multirun";
        public static final String REVOKE = "anti-revoke";
        public static final String WND_CLASS = "wnd_class";
        public static final String PATH_DETECT = "path_detect";
        public static final String PATH_CHECK = "path_check";
        public static final String PATCH_ADDRESSES = "patch_addresses";
        public static final String TRIMS = "trims";
        public static final String AUTO_CLICK = "auto_click";

        public static final String CHANNELS = "channels";
        public static final String EXE_WILDCARD = "exe_wildcard";
        public static final String ORDINALS = "ordinals";
        public static final String MUTEX_WC = "mutex_wc";
        public static final String FEATURES = "features";
        public static final String PRECISES = "precises";
        public static final String ADDR = "addr";
        public static final String PATCH_RULES = "patch_rules";
        public static final String MULTI_STATE = "multi_state";
        public static final String NATIVE = "native";
        public static final String PATCH_WILDCARD = "patch_wildcard";
    }

    // ==================== 账号数据键 ====================

    public static final class AccKey {
        private AccKey() {}

        public static final String PID = "pid";
        public static final String HAS_MUTEX = "has_mutex";
        public static final String MAIN_HWND = "main_hwnd";
        public static final String AVATAR_URL = "avatar_url";
        public static final String NICKNAME = "nickname";
        public static final String ALIAS = "alias";
        public static final String REMARK = "remark";
        public static final String LOGIN_WND_CLASS = "login_wnd_class";
        public static final String LINKED_ACC = "linked_acc";
        public static final String CHANNEL = "channel";
        public static final String ORDINAL = "ordinal";
        public static final String AUTO_START = "auto_start";
        public static final String HOTKEY = "hotkey";
        public static final String HIDDEN = "hidden";
        public static final String RELAY = "relay";
        public static final String PID_MUTEX = "pid_mutex";
    }

    // ==================== 软件状态枚举 ====================

    public static final class SwState {
        private SwState() {}

        public static final String HIDDEN = "hidden";
        public static final String VISIBLE = "visible";
        public static final String DISABLED = "disabled";
    }

    // ==================== 配置状态枚举 ====================

    public static final class CfgStatus {
        private CfgStatus() {}

        public static final String NO_CFG = "no_cfg";
    }

    // ==================== 路径类型 ====================

    public static final class PathType {
        private PathType() {}

        public static final String INST_PATH = "inst_path";
        public static final String DATA_DIR = "data_dir";
        public static final String DLL_DIR = "dll_dir";
    }

    // ==================== 窗口类型 ====================

    public static final class WndType {
        private WndType() {}

        public static final String LOGIN = "login";
        public static final String MAIN = "main";
    }

    // ==================== 多开模式 ====================

    public static final class MultirunMode {
        private MultirunMode() {}

        public static final String FREELY_MULTIRUN = "freely_multirun";
        public static final String BUILTIN = "builtin";
    }
}
