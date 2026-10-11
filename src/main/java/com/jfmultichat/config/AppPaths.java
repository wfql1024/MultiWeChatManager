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

    private AppPaths() {}

    /** @deprecated 使用 {@link AppEnv#isDev()} 替代 */
    @Deprecated
    public static void setDevMode(boolean dev) {
        System.setProperty("run.mode", dev ? "DEV" : "PROD");
    }

    public static boolean isDevMode() {
        return AppEnv.isDev();
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
        String fileName = AppEnv.isDev() ? "DevRootConfig.json" : "RootConfig.json";
        return getVersionDir().resolve(fileName);
    }

    /** 默认用户数据目录 */
    public static Path getDefaultUserDataDir() {
        String dirName = AppEnv.isDev() ? "DevUserFiles" : "UserFiles";
        return getVersionDir().resolve(dirName);
    }

    /** 日志目录（**默认位置**；实际用哪个见 {@link #resolveLogsDirEarly()}） */
    public static Path getLogsDir() {
        return getDefaultUserDataDir().resolve("logs");
    }

    /**
     * **尽早解析出真正要用的日志目录**（用户 2026-10-11）.
     *
     * <p>为什么需要它：用户可以在 {@code RootConfig.user_data_path} 里把数据目录放到**项目里**
     *（这样 IDE 能直接看数据与日志 ✓）；日志应当**跟随**这个目录 ✓。
     * <p>而 `ConfigManager.initInternal()` 里虽然也设置了 `jfmultichat.logdir` ✗，
     * 但那时 logback 早被初始化过了 ✗ —— 因为 **`ConfigManager` 类加载时**它的
     * `private static final Logger LOG` 就会触发 logback 初始化 ✓，属性已经定死 ✓
     *（实测：日志一直落在 APPDATA ✗，怎么改都不动 ✓）。
     *
     * <p>所以这里只做"**读 RootConfig + 取 user_data_path**"这点**不需要日志**的活 ✓，
     * 在入口的第一行调用 ✓：有合法自定义目录 → 用它下面的 `logs/` ✓；否则 → {@link #getLogsDir()} 兜底 ✓。
     *
     * @return 日志目录（绝不返回 null ✓）
     */
    public static Path resolveLogsDirEarly() {
        try {
            Path cfg = getRootConfigPath();
            if (cfg != null && java.nio.file.Files.isRegularFile(cfg)) {
                com.fasterxml.jackson.databind.JsonNode node =
                        new com.fasterxml.jackson.databind.ObjectMapper().readTree(
                                java.nio.file.Files.readString(cfg, java.nio.charset.StandardCharsets.UTF_8));
                String custom = node.path("user_data_path").asText("");
                if (!custom.isBlank()) {
                    return Path.of(custom).resolve("logs");
                }
            }
        } catch (Throwable t) {
            // 读不出来就兜底（绝不能因为日志目录把启动搞挂）
        }
        return getLogsDir();
    }

    // ---- 用户数据目录下的配置文件（双驼峰 PascalCase） ----

    /** LocalGlobalConfig.json */
    public static Path getLocalGlobalConfigPath(Path userDataPath) {
        return userDataPath.resolve("LocalGlobalConfig.json");
    }

    /** LocalSwConfig.json */
    public static Path getLocalSwConfigPath(Path userDataPath) {
        return userDataPath.resolve("LocalSwConfig.json");
    }

    /** RemoteGlobalConfig.json */
    public static Path getRemoteGlobalConfigPath(Path userDataPath) {
        return userDataPath.resolve("RemoteGlobalConfig.json");
    }

    /** RemoteSwConfig.json */
    public static Path getRemoteSwConfigPath(Path userDataPath) {
        return userDataPath.resolve("RemoteSwConfig.json");
    }

    /** SwAccData.json */
    public static Path getSwAccDataPath(Path userDataPath) {
        return userDataPath.resolve("SwAccData.json");
    }

    /** SwCache.json */
    public static Path getSwCachePath(Path userDataPath) {
        return userDataPath.resolve("SwCache.json");
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
