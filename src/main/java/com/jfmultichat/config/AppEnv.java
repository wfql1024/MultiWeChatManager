package com.jfmultichat.config;

/**
 * 运行环境判断 — 自动识别 DEV / TEST / PROD 模式.
 * <p>
 * 判断逻辑（优先级从高到低）:
 * <ol>
 *   <li>手动指定 — JVM 系统属性 {@code run.mode}，支持 DEV / TEST / PROD（不区分大小写）</li>
 *   <li>自动判断 — {@code getCodeSource().getLocation().getPath()} 以 .jar 结尾 → PROD，否则 → DEV</li>
 * </ol>
 * TEST 仅通过手动指定 {@code run.mode=TEST} 进入，不做自动判断.
 * <p>
 * 使用方式:
 * <pre>
 *   if (AppEnv.isDev())  { ... }
 *   if (AppEnv.isProd()) { ... }
 *   AppEnv.RunMode mode = AppEnv.getRunMode();
 * </pre>
 */
public final class AppEnv {

    /** 运行模式枚举 */
    public enum RunMode { DEV, TEST, PROD }

    private static final RunMode RUN_MODE = initRunMode();

    private AppEnv() {}

    private static RunMode initRunMode() {
        // 1. 系统属性优先
        String mode = System.getProperty("run.mode");
        if (mode != null && !mode.isBlank()) {
            try {
                return RunMode.valueOf(mode.trim().toUpperCase());
            } catch (IllegalArgumentException ignored) {
                // 非法值 → 回退到自动判断
            }
        }

        // 2. 自动检测: 从当前类的 code source 路径判断
        String path = AppEnv.class
                .getProtectionDomain()
                .getCodeSource()
                .getLocation()
                .getPath();

        return path.endsWith(".jar") ? RunMode.PROD : RunMode.DEV;
    }

    // ==================== 公开 API ====================

    /** 获取当前运行模式 */
    public static RunMode getRunMode() {
        return RUN_MODE;
    }

    /** 是否为开发环境 */
    public static boolean isDev() {
        return RUN_MODE == RunMode.DEV;
    }

    /** 是否为测试环境 */
    public static boolean isTest() {
        return RUN_MODE == RunMode.TEST;
    }

    /** 是否为生产环境 */
    public static boolean isProd() {
        return RUN_MODE == RunMode.PROD;
    }
}
