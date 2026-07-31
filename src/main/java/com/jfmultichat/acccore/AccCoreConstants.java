package com.jfmultichat.acccore;

/**
 * AccCore 常量定义 — 账号数据 JSON 的键名及状态枚举
 */
public final class AccCoreConstants {

    private AccCoreConstants() {}

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
        public static final String IID = "iid";
        public static final String AVATAR = "avatar";
        public static final String DISPLAY = "display";
        public static final String CONFIG_STATUS = "config_status";
    }

    // ==================== 配置状态枚举 ====================

    public static final class CfgStatus {
        private CfgStatus() {}

        public static final String NO_CFG = "no_cfg";
    }

    // ==================== 窗口类型 ====================

    public static final class WndType {
        private WndType() {}

        public static final String LOGIN = "login";
        public static final String MAIN = "main";
    }
}
