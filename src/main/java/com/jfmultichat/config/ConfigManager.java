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
 *   <li>root_config.json — RootConfig POJO（全局设置：代理、数据目录、远程URL列表）</li>
 *   <li>local_global_config.json — JsonConfigStore（软件偏好：主题、窗帘状态等）</li>
 *   <li>local_sw_config.json — JsonConfigStore（各平台设置：路径、尺寸等，一级键=swId）</li>
 *   <li>sw_acc_data.json — JsonConfigStore（账号数据）</li>
 *   <li>sw_cache.json — JsonConfigStore（适配缓存）</li>
 *   <li>remote_global_config.json — JsonConfigStore（远程全局配置缓存，只读）</li>
 *   <li>remote_sw_config.json — JsonConfigStore（远程平台配置缓存，只读）</li>
 * </ul>
 */
public class ConfigManager {

    private static final Logger LOG = LoggerFactory.getLogger(ConfigManager.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static volatile ConfigManager instance;

    // ---- 配置存储 ----
    private RootConfig rootConfig;                    // root_config.json（POJO）
    private JsonConfigStore localGlobalConfigStore;   // local_global_config.json
    private JsonConfigStore localSwConfigStore;       // local_sw_config.json
    private JsonConfigStore swAccDataStore;           // sw_acc_data.json
    private JsonConfigStore swCacheStore;             // sw_cache.json
    private JsonConfigStore remoteGlobalConfigStore;  // remote_global_config.json（缓存）
    private JsonConfigStore remoteSwConfigStore;      // remote_sw_config.json（缓存）

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

        // 1. 加载 root_config.json
        Path rootConfigPath = AppPaths.getRootConfigPath();
        rootConfig = loadRootConfig(rootConfigPath);

        // 2. 确定 user_data_path
        userDataPath = resolveUserDataPath(rootConfig.getUserDataPath());
        AppPaths.ensureDir(userDataPath);
        rootConfig.setUserDataPath(userDataPath.toString());
        saveRootConfig();

        // 3. 设置日志系统属性
        System.setProperty("jfmultichat.logdir", userDataPath.resolve("logs").toString());

        // 4. 确保配置文件存在 + 迁移旧文件
        migrateOldFiles();

        // 5. 加载所有配置存储
        localGlobalConfigStore  = new JsonConfigStore(AppPaths.getLocalGlobalConfigPath(userDataPath));
        localSwConfigStore      = new JsonConfigStore(AppPaths.getLocalSwConfigPath(userDataPath));
        swAccDataStore          = new JsonConfigStore(AppPaths.getSwAccDataPath(userDataPath));
        swCacheStore            = new JsonConfigStore(AppPaths.getSwCachePath(userDataPath));
        remoteGlobalConfigStore = new JsonConfigStore(AppPaths.getRemoteGlobalConfigPath(userDataPath));
        remoteSwConfigStore     = new JsonConfigStore(AppPaths.getRemoteSwConfigPath(userDataPath));

        initialized = true;
    }

    /** 迁移旧版配置文件到新命名 */
    private void migrateOldFiles() {
        // local_config.json → local_global_config.json + local_sw_config.json
        Path oldConfig = userDataPath.resolve("local_config.json");
        if (Files.exists(oldConfig)) {
            try {
                ObjectNode old = loadJsonNode(oldConfig);
                // global 节点 → local_global_config.json
                if (old.has("global") && old.get("global").isObject()) {
                    saveJsonNode(AppPaths.getLocalGlobalConfigPath(userDataPath),
                            (ObjectNode) old.get("global"));
                    // 同时把旧 global 中的代理/URL迁移到 root_config
                    JsonNode g = old.get("global");
                    if (g.has("use_proxy") && rootConfig.getProxyIp().isEmpty())
                        rootConfig.setUseProxy(g.get("use_proxy").asBoolean());
                    if (g.has("proxy_ip") && rootConfig.getProxyIp().isEmpty())
                        rootConfig.setProxyIp(g.get("proxy_ip").asText());
                    if (g.has("proxy_port") && rootConfig.getProxyPort().isEmpty())
                        rootConfig.setProxyPort(g.get("proxy_port").asText());
                    if (g.has("remote_global_urls") && g.get("remote_global_urls").isArray()) {
                        for (JsonNode u : g.get("remote_global_urls"))
                            if (u.isTextual() && !rootConfig.getRemoteGlobalUrls().contains(u.asText()))
                                rootConfig.getRemoteGlobalUrls().add(u.asText());
                    }
                    if (g.has("remote_sw_urls") && g.get("remote_sw_urls").isArray()) {
                        for (JsonNode u : g.get("remote_sw_urls"))
                            if (u.isTextual() && !rootConfig.getRemoteSwUrls().contains(u.asText()))
                                rootConfig.getRemoteSwUrls().add(u.asText());
                    }
                    saveRootConfig();
                }
                // 平台节点 → local_sw_config.json
                ObjectNode swNode = MAPPER.createObjectNode();
                var it = old.fieldNames();
                while (it.hasNext()) {
                    String key = it.next();
                    if (!"global".equals(key) && old.get(key).isObject()) {
                        swNode.set(key, old.get(key).deepCopy());
                    }
                }
                if (!swNode.isEmpty()) {
                    saveJsonNode(AppPaths.getLocalSwConfigPath(userDataPath), swNode);
                }
                Files.deleteIfExists(oldConfig);
                LOG.info("Migrated local_config.json → local_global_config.json + local_sw_config.json");
            } catch (Exception e) {
                LOG.error("Failed to migrate local_config.json", e);
            }
        }

        // local_global.json → local_global_config.json
        Path oldGlobal = userDataPath.resolve("local_global.json");
        if (Files.exists(oldGlobal)) {
            try {
                Files.move(oldGlobal, AppPaths.getLocalGlobalConfigPath(userDataPath));
                LOG.info("Renamed local_global.json → local_global_config.json");
            } catch (Exception e) {
                LOG.warn("Failed to rename local_global.json", e);
            }
        }

        // local_sw.json → local_sw_config.json
        Path oldSw = userDataPath.resolve("local_sw.json");
        if (Files.exists(oldSw)) {
            try {
                Files.move(oldSw, AppPaths.getLocalSwConfigPath(userDataPath));
                LOG.info("Renamed local_sw.json → local_sw_config.json");
            } catch (Exception e) {
                LOG.warn("Failed to rename local_sw.json", e);
            }
        }

        // remote_global.json → remote_global_config.json
        Path oldRg = userDataPath.resolve("remote_global.json");
        if (Files.exists(oldRg)) {
            try {
                Files.move(oldRg, AppPaths.getRemoteGlobalConfigPath(userDataPath));
                LOG.info("Renamed remote_global.json → remote_global_config.json");
            } catch (Exception e) {
                LOG.warn("Failed to rename remote_global.json", e);
            }
        }

        // remote_sw.json → remote_sw_config.json
        Path oldRs = userDataPath.resolve("remote_sw.json");
        if (Files.exists(oldRs)) {
            try {
                Files.move(oldRs, AppPaths.getRemoteSwConfigPath(userDataPath));
                LOG.info("Renamed remote_sw.json → remote_sw_config.json");
            } catch (Exception e) {
                LOG.warn("Failed to rename remote_sw.json", e);
            }
        }

        // 确保所有文件存在
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
        String expected = AppPaths.isDevMode() ? "dev_user_files" : "user_files";
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
                LOG.error("Failed to load root_config.json, recreating", e);
            }
        }
        RootConfig rc = new RootConfig();
        rc.setUserDataPath(AppPaths.getDefaultUserDataDir().toString());
        try {
            MAPPER.writeValue(path.toFile(), rc);
            LOG.info("Created default root_config.json at {}", path);
        } catch (IOException e) {
            LOG.error("Failed to write default root_config.json", e);
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

    public void setUserDataPath(String newPath) {
        Path resolved = resolveUserDataPath(newPath);
        if (resolved.equals(userDataPath)) return;

        Path oldPath = userDataPath;
        AppPaths.ensureDir(resolved);
        try {
            copyDir(oldPath, resolved);
            LOG.info("Migrated user data from {} to {}", oldPath, resolved);
        } catch (IOException e) {
            LOG.error("Failed to migrate user data to {}", resolved, e);
            return;
        }

        userDataPath = resolved;
        rootConfig.setUserDataPath(resolved.toString());
        saveRootConfig();

        // 重新加载
        localGlobalConfigStore  = new JsonConfigStore(AppPaths.getLocalGlobalConfigPath(resolved));
        localSwConfigStore      = new JsonConfigStore(AppPaths.getLocalSwConfigPath(resolved));
        swAccDataStore          = new JsonConfigStore(AppPaths.getSwAccDataPath(resolved));
        swCacheStore            = new JsonConfigStore(AppPaths.getSwCachePath(resolved));
        remoteGlobalConfigStore = new JsonConfigStore(AppPaths.getRemoteGlobalConfigPath(resolved));
        remoteSwConfigStore     = new JsonConfigStore(AppPaths.getRemoteSwConfigPath(resolved));

        System.setProperty("jfmultichat.logdir", resolved.resolve("logs").toString());
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

    /** 从 local_sw_config.json 读取所有平台 ID */
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

    // ==================== 账号管理 (sw_acc_data.json) ====================

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
            LOG.error("Failed to save root_config.json", e);
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
