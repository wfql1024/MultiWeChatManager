package com.jfmultichat.config;

import java.io.File;
import java.nio.file.Path;

/**
 * 应用数据路径规范 — 版本隔离 + 开发版隔离.
 * <p>
 * 所有数据存放在 {@code %APPDATA%/JhiFengMultiChat/{version}/} 下.
 * 正式版和开发版使用不同的配置文件和用户数据目录，互不干扰.
 */
public final class AppPaths {

    /** 当前版本号（来自 AppVersion.VERSION） */
    public static final String VERSION = AppVersion.VERSION;

    private static volatile boolean devMode = false;

    private AppPaths() {}

    public static void setDevMode(boolean dev) {
        devMode = dev;
    }

    public static boolean isDevMode() {
        return devMode;
    }

    // ==================== 目录路径 ====================

    /** %APPDATA%/JhiFengMultiChat/ */
    public static Path getAppDataDir() {
        String appData = System.getenv("APPDATA");
        if (appData == null || appData.isBlank()) {
            appData = System.getProperty("user.home") + "\\AppData\\Roaming";
        }
        return Path.of(appData, "JhiFengMultiChat");
    }

    /** %APPDATA%/JhiFengMultiChat/{version}/ */
    public static Path getVersionDir() {
        return getAppDataDir().resolve(VERSION);
    }

    // ==================== 文件路径 ====================

    /** 根配置文件路径 */
    public static Path getRootConfigPath() {
        String fileName = devMode ? "dev_root_config.json" : "root_config.json";
        return getVersionDir().resolve(fileName);
    }

    /** 默认用户数据目录 */
    public static Path getDefaultUserDataDir() {
        String dirName = devMode ? "dev_user_files" : "user_files";
        return getVersionDir().resolve(dirName);
    }

    /** 日志目录 */
    public static Path getLogsDir() {
        return getDefaultUserDataDir().resolve("logs");
    }

    /** 确保目录存在（递归创建） */
    public static void ensureDir(Path dir) {
        File f = dir.toFile();
        if (!f.exists()) {
            f.mkdirs();
        }
    }

    /** 确保文件存在，不存在则写入空 JSON 对象 */
    public static void ensureJsonFile(Path file) {
        File f = file.toFile();
        if (!f.exists()) {
            try {
                f.getParentFile().mkdirs();
                java.nio.file.Files.writeString(file, "{}");
            } catch (Exception ignored) {
                // 忽略写入失败
            }
        }
    }
}
