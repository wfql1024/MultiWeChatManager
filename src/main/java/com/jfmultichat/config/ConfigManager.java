package com.jfmultichat.config;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * 统一配置管理器 — 单例，管理所有配置文件的加载、保存、获取、更新.
 * <p>
 * 配置文件一览:
 * <ul>
 *   <li>RootConfig.json — RootConfig POJO（全局设置：代理、数据目录、远程URL列表）</li>
 *   <li>LocalGlobalConfig.json — JsonConfigStore（软件偏好：主题、窗帘状态等）</li>
 *   <li>LocalSwConfig.json — JsonConfigStore（各平台设置：路径、尺寸等，一级键=swId）</li>
 *   <li>SwAccData.json — JsonConfigStore（账号数据）</li>
 *   <li>SwCache.json — JsonConfigStore（适配缓存）</li>
 *   <li>RemoteGlobalConfig.json — JsonConfigStore（远程全局配置缓存，只读）</li>
 *   <li>RemoteSwConfig.json — JsonConfigStore（远程平台配置缓存，只读）</li>
 * </ul>
 */
public class ConfigManager {

    private static final Logger LOG = LoggerFactory.getLogger(ConfigManager.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static volatile ConfigManager instance;

    // ---- 配置存储 ----
    private RootConfig rootConfig;                    // RootConfig.json（POJO）
    private JsonConfigStore localGlobalConfigStore;   // LocalGlobalConfig.json
    private JsonConfigStore localSwConfigStore;       // LocalSwConfig.json
    private JsonConfigStore swAccDataStore;           // SwAccData.json
    private JsonConfigStore swCacheStore;             // SwCache.json
    private JsonConfigStore remoteGlobalConfigStore;  // RemoteGlobalConfig.json（缓存）
    private JsonConfigStore remoteSwConfigStore;      // RemoteSwConfig.json（缓存）

    private Path userDataPath;
    private volatile boolean initialized;

    // ==================== 单例 ====================

    private ConfigManager() {}

    public static ConfigManager getInstance() {
        if (instance == null) {
            synchronized (ConfigManager.class) {
                if (instance == null) {
                    ConfigManager mgr = new ConfigManager();
                    mgr.init(false);
                    instance = mgr;
                }
            }
        }
        return instance;
    }

    public static synchronized ConfigManager init(boolean devMode) {
        if (instance != null) {
            LOG.warn("ConfigManager already initialized, ignoring init({})", devMode);
            return instance;
        }
        AppPaths.setDevMode(devMode);
        ConfigManager mgr = new ConfigManager();
        mgr.initInternal();
        instance = mgr;
        LOG.info("ConfigManager initialized. devMode={}, userDataPath={}", devMode, mgr.userDataPath);
        return instance;
    }

    // ==================== 初始化 ====================

    private void initInternal() {
        Path versionDir = AppPaths.getVersionDir();
        AppPaths.ensureDir(versionDir);

        // 1. 加载 RootConfig.json
        Path rootConfigPath = AppPaths.getRootConfigPath();
        rootConfig = loadRootConfig(rootConfigPath);

        // 2. 确定 user_data_path
        userDataPath = resolveUserDataPath(rootConfig.getUserDataPath());
        AppPaths.ensureDir(userDataPath);
        rootConfig.setUserDataPath(userDataPath.toString());
        saveRootConfig();

        // 3. 设置日志系统属性
        System.setProperty("jfmultichat.logdir", userDataPath.resolve("logs").toString());

        // 4. 确保配置文件存在
        ensureConfigFiles();

        // 5. 加载所有配置存储
        localGlobalConfigStore  = new JsonConfigStore(AppPaths.getLocalGlobalConfigPath(userDataPath));
        localSwConfigStore      = new JsonConfigStore(AppPaths.getLocalSwConfigPath(userDataPath));
        swAccDataStore          = new JsonConfigStore(AppPaths.getSwAccDataPath(userDataPath));
        swCacheStore            = new JsonConfigStore(AppPaths.getSwCachePath(userDataPath));
        remoteGlobalConfigStore = new JsonConfigStore(AppPaths.getRemoteGlobalConfigPath(userDataPath));
        remoteSwConfigStore     = new JsonConfigStore(AppPaths.getRemoteSwConfigPath(userDataPath));

        initialized = true;
    }

    /** 确保所有配置文件存在 */
    private void ensureConfigFiles() {
        AppPaths.ensureJsonFile(AppPaths.getLocalGlobalConfigPath(userDataPath));
        AppPaths.ensureJsonFile(AppPaths.getLocalSwConfigPath(userDataPath));
        AppPaths.ensureJsonFile(AppPaths.getSwAccDataPath(userDataPath));
        AppPaths.ensureJsonFile(AppPaths.getSwCachePath(userDataPath));
    }

    private Path resolveUserDataPath(String configured) {
        if (configured == null || configured.isBlank()) {
            return AppPaths.getDefaultUserDataDir();
        }
        Path p = Path.of(configured);
        String dirName = p.getFileName().toString();
        String expected = AppPaths.isDevMode() ? "DevUserFiles" : "UserFiles";
        if (!dirName.equals(expected)) {
            p = p.resolve(expected);
        }
        return p;
    }

    // ==================== JSON 读写工具 ====================

    private RootConfig loadRootConfig(Path path) {
        if (Files.exists(path)) {
            try {
                String json = Files.readString(path);
                if (!json.isBlank()) {
                    return MAPPER.readValue(json, RootConfig.class);
                }
            } catch (IOException e) {
                LOG.error("Failed to load RootConfig.json, recreating", e);
            }
        }
        RootConfig rc = new RootConfig();
        rc.setUserDataPath(AppPaths.getDefaultUserDataDir().toString());
        try {
            MAPPER.writeValue(path.toFile(), rc);
            LOG.info("Created default RootConfig.json at {}", path);
        } catch (IOException e) {
            LOG.error("Failed to write default RootConfig.json", e);
        }
        return rc;
    }

    private ObjectNode loadJsonNode(Path path) {
        try {
            if (Files.exists(path)) {
                String json = Files.readString(path);
                if (!json.isBlank()) {
                    JsonNode node = MAPPER.readTree(json);
                    if (node.isObject()) return (ObjectNode) node;
                }
            }
        } catch (IOException e) {
            LOG.error("Failed to load {}", path, e);
        }
        return MAPPER.createObjectNode();
    }

    private void saveJsonNode(Path path, ObjectNode data) {
        try {
            AppPaths.ensureDir(path.getParent());
            MAPPER.writerWithDefaultPrettyPrinter().writeValue(path.toFile(), data);
        } catch (IOException e) {
            LOG.error("Failed to save {}", path, e);
        }
    }

    // ==================== 路径访问 ====================

    public Path getUserDataPath() { return userDataPath; }
    public Path getLogsDir() { return userDataPath.resolve("logs"); }

    // ==================== RootConfig ====================

    public RootConfig getRootConfig() { return rootConfig; }

    /**
     * 迁移数据目录，支持冲突处理与备份.
     *
     * @param newPath   目标路径
     * @param useTarget true=使用目标已有数据（来源备份到桌面），false=覆盖目标（目标备份到桌面）
     */
    public void migrateAndBackup(String newPath, boolean useTarget) {
        Path resolved = resolveUserDataPath(newPath);
        if (resolved.equals(userDataPath)) return;

        Path oldPath = userDataPath;
        Path newResolved = resolved;
        AppPaths.ensureDir(newResolved);

        // 备份目标或来源到桌面
        Path desktop = java.nio.file.Path.of(System.getProperty("user.home"), "Desktop");
        String dateStr = java.time.LocalDate.now().toString();
        if (useTarget) {
            // 使用目标数据 → 备份来源到桌面，保留目标
            if (java.nio.file.Files.exists(oldPath) && hasFiles(oldPath)) {
                Path bak = desktop.resolve(oldPath.getFileName() + "_备份_" + dateStr);
                try {
                    copyDir(oldPath, bak);
                    LOG.info("来源数据已备份到 {}", bak);
                } catch (java.io.IOException e) {
                    LOG.warn("备份来源失败: {}", e.getMessage());
                }
            }
        } else {
            // 使用当前数据 → 备份目标到桌面，再迁移
            if (java.nio.file.Files.exists(newResolved) && hasFiles(newResolved)) {
                Path bak = desktop.resolve(newResolved.getFileName() + "_备份_" + dateStr);
                try {
                    copyDir(newResolved, bak);
                    LOG.info("目标数据已备份到 {}", bak);
                } catch (java.io.IOException e) {
                    LOG.warn("备份目标失败: {}", e.getMessage());
                }
            }
        }

        // 迁移（useTarget=false 时复制来源→目标）
        if (!useTarget) {
            try {
                copyDir(oldPath, newResolved);
                LOG.info("数据已从 {} 迁移到 {}", oldPath, newResolved);
            } catch (java.io.IOException e) {
                LOG.error("迁移失败: {}", e.getMessage());
                return;
            }
        }

        // 更新路径 + 重新加载
        userDataPath = newResolved;
        rootConfig.setUserDataPath(newResolved.toString());
        saveRootConfig();
        reloadStores(newResolved);
        System.setProperty("jfmultichat.logdir", newResolved.resolve("logs").toString());
    }

    private boolean hasFiles(Path dir) {
        if (!java.nio.file.Files.exists(dir)) return false;
        try (var s = java.nio.file.Files.list(dir)) {
            return s.findFirst().isPresent();
        } catch (java.io.IOException e) {
            return false;
        }
    }

    private void reloadStores(Path dataPath) {
        localGlobalConfigStore  = new JsonConfigStore(AppPaths.getLocalGlobalConfigPath(dataPath));
        localSwConfigStore      = new JsonConfigStore(AppPaths.getLocalSwConfigPath(dataPath));
        swAccDataStore          = new JsonConfigStore(AppPaths.getSwAccDataPath(dataPath));
        swCacheStore            = new JsonConfigStore(AppPaths.getSwCachePath(dataPath));
        remoteGlobalConfigStore = new JsonConfigStore(AppPaths.getRemoteGlobalConfigPath(dataPath));
        remoteSwConfigStore     = new JsonConfigStore(AppPaths.getRemoteSwConfigPath(dataPath));
    }

    public void setUserDataPath(String newPath) {
        migrateAndBackup(newPath, false);
    }

    private void copyDir(Path src, Path dst) throws IOException {
        if (!Files.exists(src)) return;
        Files.walk(src).forEach(s -> {
            try {
                Path d = dst.resolve(src.relativize(s));
                if (Files.isDirectory(s)) {
                    Files.createDirectories(d);
                } else {
                    Files.copy(s, d, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                }
            } catch (IOException ignored) {}
        });
    }

    // ==================== Sw 列表 ====================

    /** 从 LocalSwConfig.json 读取所有平台 ID */
    public List<String> getSwList() {
        List<String> list = new ArrayList<>();
        localSwConfigStore.fieldNames().forEachRemaining(list::add);
        return list;
    }

    // ==================== LocalGlobalConfig ====================

    public ObjectNode getGlobalConfig() {
        return localGlobalConfigStore.getData();
    }

    public void updateGlobalConfig(Map<String, Object> updates) {
        updates.forEach((k, v) -> {
            if (v == null) localGlobalConfigStore.remove(k);
            else localGlobalConfigStore.put(k, v);
        });
        try { localGlobalConfigStore.save(); } catch (IOException e) { LOG.error("save failed", e); }
    }

    // ==================== LocalSwConfig ====================

    public ObjectNode getSwConfig(String swId) {
        JsonNode node = localSwConfigStore.getData().get(swId);
        if (node != null && node.isObject()) return (ObjectNode) node;
        ObjectNode defaults = MAPPER.createObjectNode();
        defaults.put("state", "visible");
        return defaults;
    }

    public void updateSwConfig(String swId, Map<String, Object> updates) {
        ObjectNode swNode = localSwConfigStore.getSubNode(swId);
        updates.forEach((k, v) -> {
            if (v == null) swNode.remove(k);
            else swNode.putPOJO(k, v);
        });
        try { localSwConfigStore.save(); } catch (IOException e) { LOG.error("save failed", e); }
    }

    // ==================== 账号管理 (SwAccData.json) ====================

    public Map<String, ObjectNode> getAccountMap(String swId) {
        Map<String, ObjectNode> map = new LinkedHashMap<>();
        JsonNode swNode = swAccDataStore.getData().get(swId);
        if (swNode != null && swNode.isObject()) {
            swNode.fields().forEachRemaining(e -> map.put(e.getKey(), (ObjectNode) e.getValue()));
        }
        return map;
    }

    public void addAccount(String swId, String accountId, ObjectNode fields) {
        swAccDataStore.getSubNode(swId).set(accountId, fields.deepCopy());
        try { swAccDataStore.save(); } catch (IOException e) { LOG.error("save failed", e); }
    }

    public void updateAccount(String swId, String accountId, Map<String, Object> updates) {
        ObjectNode swNode = swAccDataStore.getSubNode(swId);
        ObjectNode accNode;
        JsonNode existing = swNode.get(accountId);
        if (existing != null && existing.isObject()) {
            accNode = (ObjectNode) existing;
        } else {
            accNode = MAPPER.createObjectNode();
            swNode.set(accountId, accNode);
        }
        updates.forEach((k, v) -> {
            if (v == null) accNode.remove(k);
            else accNode.putPOJO(k, v);
        });
        try { swAccDataStore.save(); } catch (IOException e) { LOG.error("save failed", e); }
    }

    public boolean deleteAccount(String swId, String accountId) {
        JsonNode swNode = swAccDataStore.getData().get(swId);
        if (swNode == null || !swNode.isObject()) return false;
        boolean removed = ((ObjectNode) swNode).remove(accountId) != null;
        if (removed) {
            try { swAccDataStore.save(); } catch (IOException e) { LOG.error("save failed", e); }
        }
        return removed;
    }

    // ==================== Sw 缓存 ====================

    public ObjectNode getSwCache() { return swCacheStore.getData(); }

    public void setSwCache(ObjectNode cache) {
        swCacheStore.setData(cache != null ? cache : MAPPER.createObjectNode());
        try { swCacheStore.save(); } catch (IOException e) { LOG.error("save failed", e); }
    }

    // ==================== 远程配置缓存 ====================

    public ObjectNode getRemoteGlobal() { return remoteGlobalConfigStore.getData(); }

    public ObjectNode getRemoteSw() { return remoteSwConfigStore.getData(); }

    public void setRemoteGlobal(ObjectNode data) {
        remoteGlobalConfigStore.setData(data != null ? data : MAPPER.createObjectNode());
        try { remoteGlobalConfigStore.save(); } catch (IOException e) { LOG.error("save failed", e); }
    }

    public void setRemoteSw(ObjectNode data) {
        remoteSwConfigStore.setData(data != null ? data : MAPPER.createObjectNode());
        try { remoteSwConfigStore.save(); } catch (IOException e) { LOG.error("save failed", e); }
    }

    // ==================== 持久化 ====================

    private void saveRootConfig() {
        try {
            Path path = AppPaths.getRootConfigPath();
            AppPaths.ensureDir(path.getParent());
            MAPPER.writerWithDefaultPrettyPrinter().writeValue(path.toFile(), rootConfig);
        } catch (IOException e) {
            LOG.error("Failed to save RootConfig.json", e);
        }
    }

    public void saveAll() {
        saveRootConfig();
        try { localGlobalConfigStore.save(); } catch (IOException e) { LOG.error("save failed", e); }
        try { localSwConfigStore.save(); } catch (IOException e) { LOG.error("save failed", e); }
        try { swAccDataStore.save(); } catch (IOException e) { LOG.error("save failed", e); }
        try { swCacheStore.save(); } catch (IOException e) { LOG.error("save failed", e); }
    }

    public boolean isInitialized() { return initialized; }
}
