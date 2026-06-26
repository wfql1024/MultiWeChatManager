package com.jfmultichat.swcore;

/**
 * 常量定义 — 所有值严格对照 legacy_python/scripts/original_remote_sw_v9.json 中的实际 JSON key。
 */
public final class SwCoreConstants {

    private SwCoreConstants() {}

    // ==================== RemoteSwKey — 远程平台配置 JSON 的键名 ====================

    public static final class RemoteSwKey {
        private RemoteSwKey() {}

        // 平台级字段
        public static final String ALIAS = "alias";
        public static final String EXECUTABLE = "executable";
        public static final String EXECUTABLE_WILDCARDS = "executable_wildcards";
        public static final String DATA_DIR_NAME = "data_dir_name";
        public static final String MUTEX_HANDLES = "mutex_handles";
        public static final String CONFIG_HANDLES = "config_handles";
        public static final String CONFIG_ADDRESSES = "config_addresses";
        public static final String PATCH_ADDRESSES = "patch_addresses";
        public static final String MUTEX_HANDLE_WILDCARDS = "mutex_handle_wildcards";
        public static final String CONFIG_HANDLE_WILDCARDS = "config_handle_wildcards";
        public static final String EXCLUDED_DIRS = "excluded_dirs";
        public static final String COEXIST = "coexist";
        public static final String MULTI = "multirun";
        public static final String REVOKE = "anti-revoke";
        public static final String AUTO_GET = "auto_get";
        public static final String WND_CLASS = "wnd_class";
        public static final String PATH_DETECT = "path_detect";
        public static final String PATH_CHECK = "path_check";

        // 共存频道字段
        public static final String CHANNELS = "channels";
        public static final String EXE_WILDCARD = "exe_wildcard";
        public static final String MUTEX_WILDCARD = "mutex_wildcard";
        public static final String ORDINALS = "ordinals";
        public static final String PATCH_WILDCARD = "patch_wildcard";
        public static final String INTRODUCTION = "introduce";
        public static final String AUTHORS = "authors";

        // 补丁规则字段
        public static final String FEATURES = "features";
        public static final String ADDR = "addr";
        public static final String WILDCARD = "wildcard";
        public static final String PATCH_RULES = "patch_rules";
        public static final String TYPE = "type";
        public static final String VER_ADAPTATIONS = "ver_adaptations";
        public static final String ORIGINAL = "original";
        public static final String MODIFIED = "modified";
        public static final String LEFT_CUT = "left_cut";
        public static final String RIGHT_CUT = "right_cut";
        public static final String TARGETS = "targets";
        public static final String DESCRIPTION = "descript";
        public static final String CUSTOMIZABLE = "customizable";
        public static final String PARENTS = "parents";
        public static final String CHILDREN = "children";
        public static final String FRIENDS = "friends";

        // 多状态/原生多开
        public static final String MULTI_STATE = "multi_state";
        public static final String NATIVE = "native";

        // 缓存字段
        public static final String PRECISES = "precises";

        // 窗口类名字段
        public static final String MATCHING = "matching";
        public static final String ORIGINAL_CLASS = "original";
        public static final String CLASS_NAME = "class_name";
        public static final String CLASS_NAME_WILDCARDS = "ClassNameWildcards";

        // 截图字段
        public static final String AVATAR = "avatar";
        public static final String LOGIN = "login";
        public static final String LOCATE = "locate";
        public static final String CUT = "cut";
        public static final String CAPTURE = "capture";

        // 路径检查子键 — 严格对照 JSON 中的 key
        public static final String LEFT_CONCAT = "left_concat";
        public static final String RIGHT_CONCAT = "right_concat";
        public static final String LEFT_CONTAIN = "left_contain";
        public static final String RIGHT_CONTAIN = "right_contain";
    }

    // ==================== LocalSettingKey — 本地设置 JSON 的键名 ====================

    public static final class LocalSettingKey {
        private LocalSettingKey() {}

        public static final String INST_PATH = "inst_path";
        public static final String DATA_DIR = "data_dir";
        public static final String DLL_DIR = "dll_dir";
        public static final String INST_DIR = "inst_dir";
        public static final String REMARK = "remark";
        public static final String COEXIST_MODE = "coexist_mode";
        public static final String REST_MULTIRUN_MODE = "rest_multirun_mode";
        public static final String GLOBAL_SECTION = "global";
        public static final String ALL_HAS_MUTEX = "all_has_mutex";
        public static final String ENCRYPTED_USERNAME = "encrypted_username";
        public static final String ENCRYPTED_PASSWORD = "encrypted_password";
        public static final String CALL_MODE = "call_mode";
        public static final String MANAGE_SETTINGS_COLLAPSED = "manage_settings_collapsed";
        public static final String THEME = "theme";
    }

    // ==================== AccKeys — 账号数据 JSON 的键名 ====================

    public static final class AccKeys {
        private AccKeys() {}

        public static final String RELAY = "relay";
        public static final String PID = "pid";
        public static final String PID_MUTEX = "pid_mutex";
        public static final String COEXIST_CHANNEL = "coexist_channel";
        public static final String ORDINAL = "ordinal";
    }

    // ==================== 路径类型常量 ====================

    public static final class PathType {
        private PathType() {}

        public static final String INST_PATH = "inst_path";
        public static final String DATA_DIR = "data_dir";
        public static final String DLL_DIR = "dll_dir";
    }

    // ==================== 窗口类型常量 ====================

    public static final class WndType {
        private WndType() {}

        public static final String LOGIN = "login";
        public static final String MAIN = "main";
    }

    // ==================== 多开模式常量 ====================

    public static final class MultirunMode {
        private MultirunMode() {}

        public static final String FREELY_MULTIRUN = "freely_multirun";
        public static final String BUILTIN = "builtin";
    }

    // ==================== 调用模式常量 ====================

    public static final class CallMode {
        private CallMode() {}

        public static final String DEFAULT = "default";
        public static final String LOGON = "logon";
        public static final String HANDLE = "handle";
    }

    // ==================== 路径变量前缀 ====================

    public static final String PATH_VAR_DLL_DIR = "%dll_dir%";
    public static final String PATH_VAR_INST_DIR = "%inst_dir%";
    public static final String PATH_VAR_DATA_DIR = "%data_dir%";
    public static final String PATH_VAR_INST_PATH = "%inst_path%";

    // ==================== 默认值常量 ====================

    public static final int DEFAULT_AVATAR_SIZE = 96;
    public static final String DEFAULT_AVATAR_FILENAME = "default.jpg";
    public static final String AVATAR_CACHE_SUFFIX = "avatar_cache";
}
