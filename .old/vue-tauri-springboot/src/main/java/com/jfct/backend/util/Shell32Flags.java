package com.jfct.backend.util;

public class Shell32Flags {
    // 默认值，等于 0
    public static final int KF_FLAG_DEFAULT = 0x00000000;

    // 如果存在快捷方式（junction），返回它指向的目标路径（默认是返回链接本身）
    public static final int KF_FLAG_NO_ALIAS = 0x80000000;

    // 如果 KnownFolder 没有被注册，也返回物理路径
    public static final int KF_FLAG_DONT_UNEXPAND = 0x20000000;

    // 如果用户重定向了文件夹，仍返回默认路径（忽略重定向）
    public static final int KF_FLAG_DEFAULT_PATH = 0x00400000;

    // 如果文件夹不存在，就创建它
    public static final int KF_FLAG_CREATE = 0x00008000;

    // 如果是虚拟文件夹，返回其文件系统路径（如果有的话）
    public static final int KF_FLAG_INIT = 0x00000800;

    // 强制使用用户配置（即使调用进程是系统账号）
    public static final int KF_FLAG_FORCE_APP_DATA_REDIRECTION = 0x00080000;

    // 返回系统路径，而不是当前用户的
    public static final int KF_FLAG_RETURN_SYSTEM_PATH = 0x00001000;

    // 不要检查安全访问权限，直接返回路径（有可能会越权）
    public static final int KF_FLAG_DONT_VERIFY = 0x00004000;
}

