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
 * 职责：
 * <ul>
 *   <li>初始化目录结构和默认配置文件</li>
 *   <li>加载 root_config.json → 确定 user_data_path</li>
 *   <li>管理 local_config.json / sw_acc_data.json / sw_cache.json</li>
 *   <li>提供细粒度 API：按 Sw ID 获取配置、增删改查账号</li>
 *   <li>读写远程配置缓存（remote_global.json / remote_sw.json）</li>
 * </ul>
 * <p>
 * 本类所有涉及 "Sw" 的术语均表示 "聊天软件"（Software 缩写）.
 */
public class ConfigManager {

    private static final Logger LOG = LoggerFactory.getLogger(ConfigManager.class);

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static volatile ConfigManager instance;

    // ==================== 内存中的配置数据 ====================

    private RootConfig rootConfig;           // root_config.json
    private ObjectNode localConfig;          // local_config.json
    private ObjectNode swAccData;            // sw_acc_data.json
    private ObjectNode swCache;              // sw_cache.json
    private ObjectNode remoteGlobal;         // remote_global.json (只读缓存)
    private ObjectNode remoteSw;             // remote_sw.json (只读缓存)

    private Path userDataPath;               // 实际使用的 user_data_path
    private volatile boolean initialized;

    // ==================== 单例 ====================

    private ConfigManager() {}

    /**
     * 获取单例。首次调用自动触发初始化（devMode=false）.
     */
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

    /**
     * 手动初始化（指定 devMode）。需在首次 getInstance() 前调用.
     *
     * @param devMode true=使用 dev_root_config.json + dev_user_files/
     */
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
        // 1. 创建版本目录
        Path versionDir = AppPaths.getVersionDir();
        AppPaths.ensureDir(versionDir);

        // 2. 加载 root_config.json
        Path rootConfigPath = AppPaths.getRootConfigPath();
        rootConfig = loadRootConfig(rootConfigPath);

        // 3. 确定 user_data_path（不以 user_files 结尾则自动拼接）
        userDataPath = resolveUserDataPath(rootConfig.getUserDataPath());

        // 4. 确保 user_data_path 存在并更新 root config
        AppPaths.ensureDir(userDataPath);
        rootConfig.setUserDataPath(userDataPath.toString());
        saveRootConfig();

        // 5. 设置日志系统属性
        System.setProperty("jfmultichat.logdir", userDataPath.resolve("logs").toString());

        // 6. 创建默认配置文件（不存在则写入空对象）
        AppPaths.ensureJsonFile(userDataPath.resolve("local_config.json"));
        AppPaths.ensureJsonFile(userDataPath.resolve("sw_acc_data.json"));
        AppPaths.ensureJsonFile(userDataPath.resolve("sw_cache.json"));

        // 7. 加载所有配置文件到内存
        localConfig  = loadJson(userDataPath.resolve("local_config.json"));
        swAccData    = loadJson(userDataPath.resolve("sw_acc_data.json"));
        swCache      = loadJson(userDataPath.resolve("sw_cache.json"));

        // 8. remote_global.json / remote_sw.json 暂不创建（留待后续网络下载）
        remoteGlobal = loadJsonOrEmpty(userDataPath.resolve("remote_global.json"));
        remoteSw     = loadJsonOrEmpty(userDataPath.resolve("remote_sw.json"));

        initialized = true;
    }

    /**
     * 解析 user_data_path：如果用户指定的路径不以 user_files 结尾，自动拼接.
     */
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

    // ==================== JSON 读写 ====================

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
        // 默认值
        RootConfig rc = new RootConfig();
        rc.setUserDataPath(AppPaths.getDefaultUserDataDir().toString());
        rc.setRemoteGlobalUrl("");
        rc.setRemoteSwUrl("");
        // 写入默认配置
        try {
            MAPPER.writeValue(path.toFile(), rc);
            LOG.info("Created default root_config.json at {}", path);
        } catch (IOException e) {
            LOG.error("Failed to write default root_config.json", e);
        }
        return rc;
    }

    private void saveRootConfig() {
        try {
            Path path = AppPaths.getRootConfigPath();
            AppPaths.ensureDir(path.getParent());
            MAPPER.writerWithDefaultPrettyPrinter().writeValue(path.toFile(), rootConfig);
        } catch (IOException e) {
            LOG.error("Failed to save root_config.json", e);
        }
    }

    private ObjectNode loadJson(Path path) {
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

    private ObjectNode loadJsonOrEmpty(Path path) {
        return Files.exists(path) ? loadJson(path) : MAPPER.createObjectNode();
    }

    private void saveJson(Path path, ObjectNode data) {
        try {
            AppPaths.ensureDir(path.getParent());
            MAPPER.writerWithDefaultPrettyPrinter().writeValue(path.toFile(), data);
        } catch (IOException e) {
            LOG.error("Failed to save {}", path, e);
        }
    }

    // ==================== 路径访问 ====================

    /** 当前用户数据目录的绝对路径 */
    public Path getUserDataPath() {
        return userDataPath;
    }

    /** 日志目录 */
    public Path getLogsDir() {
        return userDataPath.resolve("logs");
    }

    // ==================== RootConfig ====================

    public RootConfig getRootConfig() {
        return rootConfig;
    }

    /**
     * 修改 user_data_path — 触发数据迁移.
     * 新路径不以 user_files 结尾时自动拼接.
     */
    public void setUserDataPath(String newPath) {
        Path resolved = resolveUserDataPath(newPath);
        if (resolved.equals(userDataPath)) return;

        // 复制现有文件到新目录
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

        // 重新加载在新位置的配置
        localConfig  = loadJson(resolved.resolve("local_config.json"));
        swAccData    = loadJson(resolved.resolve("sw_acc_data.json"));
        swCache      = loadJson(resolved.resolve("sw_cache.json"));
        remoteGlobal = loadJsonOrEmpty(resolved.resolve("remote_global.json"));
        remoteSw     = loadJsonOrEmpty(resolved.resolve("remote_sw.json"));

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

    /**
     * 获取所有 Sw 配置的 ID 列表（从 local_config.json 的顶层键中排除 "global"）.
     * 用于前端展示 Sw 列表.
     */
    public List<String> getSwList() {
        List<String> list = new ArrayList<>();
        localConfig.fieldNames().forEachRemaining(key -> {
            if (!"global".equals(key)) list.add(key);
        });
        return list;
    }

    // ==================== 全局配置 (local_config.json → global) ====================

    public ObjectNode getGlobalConfig() {
        JsonNode global = localConfig.get("global");
        if (global == null || !global.isObject()) {
            ObjectNode gn = MAPPER.createObjectNode();
            localConfig.set("global", gn);
            return gn;
        }
        return (ObjectNode) global;
    }

    public void updateGlobalConfig(Map<String, Object> updates) {
        ObjectNode global = getGlobalConfig();
        updates.forEach((k, v) -> {
            if (v == null) global.remove(k);
            else global.putPOJO(k, v);
        });
        saveLocalConfig();
    }

    // ==================== Sw 配置 (local_config.json → {swId}) ====================

    /**
     * 获取指定 Sw 的配置（如 "WeChat"、"Weixin"）.
     * 如果不存在，返回默认配置（state="visible"）.
     */
    public ObjectNode getSwConfig(String swId) {
        JsonNode swNode = localConfig.get(swId);
        if (swNode != null && swNode.isObject()) return (ObjectNode) swNode;

        // 返回默认配置
        ObjectNode defaults = MAPPER.createObjectNode();
        defaults.put("state", "visible");
        return defaults;
    }

    /**
     * 获取或创建指定 Sw 的配置（不存在时写入 local_config.json）.
     */
    public ObjectNode getOrCreateSwConfig(String swId) {
        JsonNode swNode = localConfig.get(swId);
        if (swNode != null && swNode.isObject()) return (ObjectNode) swNode;

        ObjectNode defaults = MAPPER.createObjectNode();
        defaults.put("state", "visible");
        localConfig.set(swId, defaults);
        saveLocalConfig();
        return defaults;
    }

    /**
     * 更新指定 Sw 的配置（合并更新）.
     */
    public void updateSwConfig(String swId, Map<String, Object> updates) {
        ObjectNode swConfig = getOrCreateSwConfig(swId);
        updates.forEach((k, v) -> {
            if (v == null) swConfig.remove(k);
            else swConfig.putPOJO(k, v);
        });
        saveLocalConfig();
    }

    // ==================== 账号管理 (sw_acc_data.json) ====================

    /**
     * 获取指定 Sw 下的所有账号（Map<accountId, JsonNode>）.
     */
    public Map<String, ObjectNode> getAccountMap(String swId) {
        Map<String, ObjectNode> map = new LinkedHashMap<>();
        JsonNode swNode = swAccData.get(swId);
        if (swNode != null && swNode.isObject()) {
            swNode.fields().forEachRemaining(e -> map.put(e.getKey(), (ObjectNode) e.getValue()));
        }
        return map;
    }

    /**
     * 获取指定 Sw 下的单个账号.
     */
    public Optional<ObjectNode> getAccount(String swId, String accountId) {
        JsonNode swNode = swAccData.get(swId);
        if (swNode == null || !swNode.isObject()) return Optional.empty();
        JsonNode accNode = swNode.get(accountId);
        if (accNode != null && accNode.isObject()) return Optional.of((ObjectNode) accNode);
        return Optional.empty();
    }

    /**
     * 添加或更新一个账号.
     *
     * @param swId      Sw ID
     * @param accountId 账号 ID（在同一 Sw 内唯一）
     * @param fields    账号字段
     */
    public void addAccount(String swId, String accountId, ObjectNode fields) {
        ObjectNode swNode = getOrCreateSwNode(swId);
        swNode.set(accountId, fields.deepCopy());
        saveSwAccData();
    }

    /**
     * 更新账号的部分字段（合并）.
     */
    public void updateAccount(String swId, String accountId, Map<String, Object> updates) {
        ObjectNode swNode = getOrCreateSwNode(swId);
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
        saveSwAccData();
    }

    /**
     * 删除一个账号.
     */
    public boolean deleteAccount(String swId, String accountId) {
        JsonNode swNode = swAccData.get(swId);
        if (swNode == null || !swNode.isObject()) return false;
        boolean removed = ((ObjectNode) swNode).remove(accountId) != null;
        if (removed) saveSwAccData();
        return removed;
    }

    private ObjectNode getOrCreateSwNode(String swId) {
        JsonNode swNode = swAccData.get(swId);
        if (swNode != null && swNode.isObject()) return (ObjectNode) swNode;
        ObjectNode newNode = MAPPER.createObjectNode();
        swAccData.set(swId, newNode);
        return newNode;
    }

    // ==================== Sw 适配缓存 (sw_cache.json) ====================

    /** 获取整个适配缓存（暂作为整体 JSON 对象，不解析内部结构） */
    public ObjectNode getSwCache() {
        return swCache;
    }

    /** 覆写整个适配缓存 */
    public void setSwCache(ObjectNode cache) {
        this.swCache = cache != null ? cache : MAPPER.createObjectNode();
        saveSwCache();
    }

    // ==================== 远程配置缓存（只读） ====================

    /** 获取远程全局配置缓存（只读） */
    public ObjectNode getRemoteGlobal() {
        return remoteGlobal;
    }

    /** 获取远程平台配置缓存（只读） */
    public ObjectNode getRemoteSw() {
        return remoteSw;
    }

    /**
     * 写入远程全局配置缓存（由下载逻辑调用，暂留）.
     */
    public void setRemoteGlobal(ObjectNode data) {
        this.remoteGlobal = data != null ? data : MAPPER.createObjectNode();
        saveJson(userDataPath.resolve("remote_global.json"), remoteGlobal);
    }

    /**
     * 写入远程平台配置缓存（由下载逻辑调用，暂留）.
     */
    public void setRemoteSw(ObjectNode data) {
        this.remoteSw = data != null ? data : MAPPER.createObjectNode();
        saveJson(userDataPath.resolve("remote_sw.json"), remoteSw);
    }

    // ==================== 持久化 ====================

    public void saveLocalConfig() {
        saveJson(userDataPath.resolve("local_config.json"), localConfig);
    }

    public void saveSwAccData() {
        saveJson(userDataPath.resolve("sw_acc_data.json"), swAccData);
    }

    public void saveSwCache() {
        saveJson(userDataPath.resolve("sw_cache.json"), swCache);
    }

    /** 保存所有可写配置 */
    public void saveAll() {
        saveRootConfig();
        saveLocalConfig();
        saveSwAccData();
        saveSwCache();
    }

    /** 是否已初始化 */
    public boolean isInitialized() {
        return initialized;
    }
}
