package com.jfmultichat.appcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import com.jfmultichat.config.AppPaths;
import com.jfmultichat.config.ConfigManager;
import com.jfmultichat.config.CryptoUtils;

/**
 * App 操作核心 — 软件级操作（远程配置、版本检查、统计、托盘等）
 * <p>
 * 对应 Python: AppFuncCore (L30-L679)
 * <p>
 * 提供：远程配置获取/下载、版本号检查、用户目录管理、统计数据操作等。
 *
 * 依赖: AppConfigAccessor
 */
public final class AppCore {

    private static final Logger LOG = LoggerFactory.getLogger(AppCore.class);
    private static final AppConfigAccessor ACCESSOR = new AppConfigAccessor();
    static { /* ensure accessibility */ }
    private static final ExecutorService IO_EXECUTOR = Executors.newFixedThreadPool(4);

    private AppCore() {
        throw new UnsupportedOperationException("AppCore is a static utility class");
    }

    // ==================== 用户目录 ====================

    /**
     * 获取用户目录
     * 对应 Python: get_user_dir (L32-L33)
     */
    public static String getUserDir() {
        return ACCESSOR.getUserDir();
    }

    /**
     * 打开用户目录
     * 对应 Python: open_user_file (L266-L276)
     */
    public static String[] openUserFile() {
        try {
            String userDir = getUserDir();
            Path p = Path.of(userDir);
            if (!Files.exists(p)) {
                Files.createDirectories(p);
            }
            java.awt.Desktop.getDesktop().open(p.toFile());
            return new String[]{null, "ok"};
        } catch (Exception e) {
            LOG.error("[应用] 打开用户目录失败: {}", e.getMessage(), e);
            return new String[]{null, e.getMessage()};
        }
    }

    // ==================== 配置读取代理 ====================

    /**
     * 获取平台账号数据
     * 对应 Python: get_sw_acc_data (L36-L37)
     */
    public static JsonNode getSwAccData(String sw, String... addr) {
        return ACCESSOR.getSwAccData(sw, addr);
    }

    /**
     * 获取远程平台配置
     * 对应 Python: get_remote_sw (L40-L41)
     */
    public static JsonNode getRemoteSw(String sw, String... addr) {
        return ACCESSOR.getRemoteSw(sw, addr);
    }

    /**
     * 获取远程全局配置
     * 对应 Python: get_remote_global (L44-L45)
     */
    public static JsonNode getRemoteGlobal(String... addr) {
        return ACCESSOR.getRemoteGlobal(addr);
    }

    /**
     * 获取 RootConfig
     * 对应 Python: get_root_settings (L48-L49)
     */
    public static JsonNode getRootSettings(String... addr) {
        return ACCESSOR.getRootConfig(addr);
    }

    /**
     * 更新 RootConfig
     * 对应 Python: update_root_settings (L52-L53)
     */
    public static void updateRootSettings(Map<String, Object> kwargs) {
        ACCESSOR.updateRootConfig(kwargs);
    }

    /**
     * 获取本地全局设置
     * 对应 Python: get_global_settings (L56-L57)
     */
    public static JsonNode getGlobalSettings(String... addr) {
        return ACCESSOR.getGlobalSetting(addr);
    }

    /**
     * 更新本地全局设置
     * 对应 Python: update_global_settings (L60-L61)
     */
    public static void updateGlobalSettings(Map<String, Object> updates) {
        ACCESSOR.updateGlobalSetting(updates);
    }

    /**
     * 获取或设置默认值
     * 对应 Python: fetch_global_setting_or_set_default (L64-L66)
     */
    public static JsonNode fetchGlobalSettingOrDefault(String key, Object defaultValue) {
        return ACCESSOR.fetchOrSetDefaultGlobal(key, defaultValue);
    }

    /**
     * 保存全局设置并检查变化
     * 对应 Python: save_global_setting_and_check_changed (L69-L74)
     */
    public static boolean saveGlobalSetting(String key, Object value) {
        return ACCESSOR.saveAndCheckChangedGlobal(key, value);
    }

    // ==================== 远程配置获取 ====================

    /**
     * 强制从网络获取最新的远程加密配置
     * 对应 Python: force_fetch_remote_encrypted_cfg (L350-L395)
     *
     * @param ns   命名空间："RemoteSw" 或 "RemoteGlobal"
     * @param url  指定 URL（可为 null）
     * @return 解密后的 JSON 字符串；失败返回 null
     */
    public static String forceFetchRemoteEncryptedCfg(String ns, String url) {
        String remoteCfgPath;
        List<String> urlsRaw = new ArrayList<>();

        if (AppCoreConstants.RootCfgKey.REMOTE_SW_NS.equals(ns)) {
            JsonNode userUrlNode = ACCESSOR.getRemoteSw("url");
            String userUrl = userUrlNode != null ? userUrlNode.asText(null) : null;
            remoteCfgPath = AppPaths.getRemoteSwConfigPath(Path.of(getUserDir())).toString();
            if (userUrl != null && !userUrl.isBlank()) urlsRaw.add(userUrl);
            urlsRaw.addAll(List.of(
                    "https://gitee.com/jfmultichat/config/raw/master/remote_sw.json",
                    "https://raw.githubusercontent.com/jfmultichat/config/master/remote_sw.json"
            ));
        } else if (AppCoreConstants.RootCfgKey.REMOTE_GLOBAL_NS.equals(ns)) {
            JsonNode userUrlNode = ACCESSOR.getRemoteGlobal("url");
            String userUrl = userUrlNode != null ? userUrlNode.asText(null) : null;
            remoteCfgPath = AppPaths.getRemoteGlobalConfigPath(Path.of(getUserDir())).toString();
            if (userUrl != null && !userUrl.isBlank()) urlsRaw.add(userUrl);
            urlsRaw.addAll(List.of(
                    "https://gitee.com/jfmultichat/config/raw/master/remote_global.json",
                    "https://raw.githubusercontent.com/jfmultichat/config/master/remote_global.json"
            ));
        } else {
            return null;
        }

        // 去重并保持顺序
        List<String> urls = new ArrayList<>(new LinkedHashSet<>(urlsRaw));
        if (url != null && !url.isBlank()) {
            urls.add(0, url);
        }

        for (String targetUrl : urls) {
            if (targetUrl == null || targetUrl.isBlank()) continue;
            LOG.info("[远程配置] 尝试下载: {}", targetUrl);
            try {
                HttpClient client = HttpClient.newBuilder()
                        .followRedirects(HttpClient.Redirect.NORMAL)
                        .build();
                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create(targetUrl))
                        .timeout(java.time.Duration.ofSeconds(10))
                        .GET()
                        .build();
                HttpResponse<String> response = client.send(request,
                        HttpResponse.BodyHandlers.ofString());
                if (response.statusCode() == 200) {
                    String decrypted = CryptoUtils.decryptResponse(response.body());
                    if (decrypted != null) {
                        Path path = Path.of(remoteCfgPath);
                        Files.createDirectories(path.getParent());
                        Files.writeString(path, decrypted, StandardCharsets.UTF_8);
                        LOG.info("[远程配置] 成功保存到: {}", remoteCfgPath);
                        return decrypted;
                    }
                } else {
                    LOG.warn("[远程配置] HTTP {} from {}", response.statusCode(), targetUrl);
                }
            } catch (Exception e) {
                LOG.warn("[远程配置] 下载失败 {}: {}", targetUrl, e.getMessage());
                if (Thread.currentThread().isInterrupted()) {
                    Thread.currentThread().interrupt();
                }
            }
        }
        return null;
    }

    /**
     * 尝试从本地读取远程配置
     * 对应 Python: _try_read_remote_cfg_locally (L397-L421)
     */
    public static String tryReadRemoteCfgLocally(String ns) {
        String remoteCfgPath;
        if (AppCoreConstants.RootCfgKey.REMOTE_SW_NS.equals(ns)) {
            remoteCfgPath = AppPaths.getRemoteSwConfigPath(Path.of(getUserDir())).toString();
        } else if (AppCoreConstants.RootCfgKey.REMOTE_GLOBAL_NS.equals(ns)) {
            remoteCfgPath = AppPaths.getRemoteGlobalConfigPath(Path.of(getUserDir())).toString();
        } else {
            return null;
        }
        try {
            return Files.readString(Path.of(remoteCfgPath), StandardCharsets.UTF_8);
        } catch (IOException e) {
            LOG.warn("[远程配置] 本地读取失败 {}: {}", remoteCfgPath, e.getMessage());
            return null;
        }
    }

    /**
     * 按策略获取远程配置（定时检查 + 兜底本地）
     * 对应 Python: read_remote_cfg_in_rules (L423-L457)
     */
    public static String readRemoteCfgInRules(String ns) {
        SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd");
        Date today = new Date();

        // 获取下次检查时间
        String nextCheckStr = ACCESSOR.fetchOrSetDefaultGlobal(
                AppCoreConstants.GlobalSettingKey.NEXT_CHECK_TIME, "").asText("");
        Date nextCheckDate;
        try {
            nextCheckDate = sdf.parse(nextCheckStr);
        } catch (Exception e) {
            nextCheckDate = today;
        }

        if (!today.before(nextCheckDate)) {
            // 到期 → 强制更新
            String data = forceFetchRemoteEncryptedCfg(ns, null);
            if (data != null) {
                Calendar cal = Calendar.getInstance();
                cal.add(Calendar.DAY_OF_MONTH, 1);
                String tomorrow = sdf.format(cal.getTime());
                ACCESSOR.fetchOrSetDefaultGlobal(
                        AppCoreConstants.GlobalSettingKey.NEXT_CHECK_TIME, tomorrow);
                return data;
            }
            return tryReadRemoteCfgLocally(ns);
        } else {
            return tryReadRemoteCfgLocally(ns);
        }
    }

    /**
     * 确保远程配置就绪（先读本地，缺失则异步下载）
     * 对应 Python: JFC.ensureRemoteConfigs(onReady) 中的逻辑
     *
     * @param ns        命名空间
     * @param onReady   就绪回调（传入 JSON 字符串）
     * @param onFailed  失败回调（传入错误信息）
     */
    public static void ensureRemoteConfigsAsync(String ns,
                                                 java.util.function.Consumer<String> onReady,
                                                 java.util.function.Consumer<String> onFailed) {
        IO_EXECUTOR.submit(() -> {
            try {
                String local = tryReadRemoteCfgLocally(ns);
                if (local != null && !local.isBlank()) {
                    onReady.accept(local);
                    return;
                }
                // 本地无数据，强制下载
                String data = forceFetchRemoteEncryptedCfg(ns, null);
                if (data != null) {
                    onReady.accept(data);
                } else {
                    onFailed.accept("无法获取远程配置，请检查网络或配置");
                }
            } catch (Exception e) {
                LOG.error("[远程配置] ensureRemoteConfigs 异常: {}", e.getMessage(), e);
                onFailed.accept(e.getMessage());
            }
        });
    }

    // ==================== 版本检查 ====================

    /**
     * 检查是否有新版本
     * 对应 Python: has_newer_version (L213-L225)
     */
    public static boolean hasNewerVersion(String currentVer) {
        try {
            JsonNode updateNode = ACCESSOR.getRemoteGlobal(AppCoreConstants.RemoteGlobalKey.UPDATE);
            if (updateNode == null || !updateNode.isObject()) return false;
            List<String> versions = new ArrayList<>();
            updateNode.fieldNames().forEachRemaining(versions::add);
            if (versions.isEmpty()) return false;
            versions.sort(com.jfmultichat.swcore.SwRuleResolver::compareVersionDesc);
            for (String v : versions) {
                int cmp = com.jfmultichat.swcore.SwRuleResolver.compareVersionDesc(v, currentVer);
                if (cmp > 0) return true;
            }
        } catch (Exception e) {
            LOG.warn("[版本] 版本检查失败: {}", e.getMessage());
        }
        return false;
    }

    /**
     * 根据当前版本分割版本列表
     * 对应 Python: split_vers_by_cur_from_local (L232-L264)
     */
    public static String[] splitVersByCurFromLocal(String currentVer) {
        try {
            JsonNode updateNode = ACCESSOR.getRemoteGlobal(AppCoreConstants.RemoteGlobalKey.UPDATE);
            if (updateNode == null || !updateNode.isObject()) {
                return new String[]{"false", "错误：数据格式错误"};
            }
            List<String> allVersions = new ArrayList<>();
            updateNode.fieldNames().forEachRemaining(allVersions::add);
            allVersions.sort(com.jfmultichat.swcore.SwRuleResolver::compareVersionDesc);
            if (allVersions.isEmpty()) {
                return new String[]{"false", "版本列表为空"};
            }
            List<String> higherVersions = new ArrayList<>();
            List<String> lowerOrEqual = new ArrayList<>();
            boolean foundLower = false;
            for (String v : allVersions) {
                int cmp = com.jfmultichat.swcore.SwRuleResolver.compareVersionDesc(v, currentVer);
                if (cmp > 0) {
                    higherVersions.add(v);
                } else {
                    lowerOrEqual.add(v);
                    foundLower = true;
                }
            }
            if (!foundLower) {
                // 所有版本都比当前高
                higherVersions = new ArrayList<>(allVersions);
                lowerOrEqual = Collections.emptyList();
            }
            return new String[]{
                    "true",
                    "higher=" + higherVersions + ",lower=" + lowerOrEqual
            };
        } catch (Exception e) {
            LOG.warn("[版本] 版本分割失败: {}", e.getMessage());
            return new String[]{"false", "错误：无法获取版本信息"};
        }
    }

    /**
     * 获取当前版本
     */
    public static String getAppCurrentVersion() {
        return com.jfmultichat.config.AppVersion.VERSION;
    }

    // ==================== 平台列表 ====================

    /**
     * 获取所有启用的平台
     * 对应 Python: get_all_enable_sw (L659-L668)
     */
    public static List<String> getAllEnableSw() {
        List<String> result = new ArrayList<>();
        JsonNode swList = ACCESSOR.getRemoteGlobal(AppCoreConstants.RemoteGlobalKey.SP_SW);
        if (swList == null || !swList.isArray()) return result;
        swList.forEach(node -> {
            if (node.isTextual()) {
                String sw = node.asText();
                JsonNode state = ACCESSOR.getSwSetting(sw, AppCoreConstants.SwSettingKey.STATE);
                if (state != null && state.isTextual()) {
                    String s = state.asText();
                    if (AppCoreConstants.SwState.HIDDEN.equals(s)
                            || AppCoreConstants.SwState.VISIBLE.equals(s)) {
                        result.add(sw);
                    }
                }
            }
        });
        return result;
    }

    /**
     * 获取所有可见的平台
     * 对应 Python: get_all_visible_sw (L670-L679)
     */
    public static List<String> getAllVisibleSw() {
        List<String> result = new ArrayList<>();
        JsonNode swList = ACCESSOR.getRemoteGlobal(AppCoreConstants.RemoteGlobalKey.SP_SW);
        if (swList == null || !swList.isArray()) return result;
        swList.forEach(node -> {
            if (node.isTextual()) {
                String sw = node.asText();
                JsonNode state = ACCESSOR.getSwSetting(sw, AppCoreConstants.SwSettingKey.STATE);
                if (state != null && state.isTextual()
                        && AppCoreConstants.SwState.VISIBLE.equals(state.asText())) {
                    result.add(sw);
                }
            }
        });
        return result;
    }

    // ==================== 统计操作 ====================

    /**
     * 清除统计数据
     * 对应 Python: clear_statistic_data (L459-L475)
     */
    public static String[] clearStatisticData() {
        try {
            ObjectNode global = ConfigManager.getInstance().getGlobalConfig();
            if (global.has("statistic")) {
                ((ObjectNode) global).remove("statistic");
                ConfigManager.getInstance().saveAll();
                return new String[]{null, "成功清除统计数据"};
            }
            return new String[]{null, "没有统计数据可清除"};
        } catch (Exception e) {
            LOG.warn("[统计] 清除失败: {}", e.getMessage());
            return new String[]{null, "清除失败: " + e.getMessage()};
        }
    }

    // ==================== 数据处理迁移 ====================

    /**
     * 合并刷新节点（classic/tree 分流）
     * 对应 Python: merge_refresh_nodes (L553-L589)
     */
    public static void mergeRefreshNodes() {
        try {
            ObjectNode global = ConfigManager.getInstance().getGlobalConfig();
            JsonNode refreshNode = global.get("refresh");
            if (refreshNode == null || !refreshNode.isObject()) return;
            ObjectNode refresh = (ObjectNode) refreshNode;
            if (!refresh.has("classic")) refresh.set("classic", com.fasterxml.jackson.databind.node.JsonNodeFactory.instance.objectNode());
            if (!refresh.has("tree")) refresh.set("tree", com.fasterxml.jackson.databind.node.JsonNodeFactory.instance.objectNode());
            Iterator<Map.Entry<String, JsonNode>> it = refresh.fields();
            while (it.hasNext()) {
                Map.Entry<String, JsonNode> entry = it.next();
                String key = entry.getKey();
                if ("classic".equals(key) || "tree".equals(key)) continue;
                JsonNode value = entry.getValue();
                ((ObjectNode) refresh.get("classic")).set(key, value);
                ((ObjectNode) refresh.get("tree")).set(key, value);
                refresh.remove(key);
            }
            ConfigManager.getInstance().saveAll();
            LOG.info("[数据迁移] mergeRefreshNodes 完成");
        } catch (Exception e) {
            LOG.warn("[数据迁移] mergeRefreshNodes 失败: {}", e.getMessage());
        }
    }

    /**
     * 移动数据到 WeChat 节点
     * 对应 Python: move_data_to_wechat (L591-L603)
     */
    public static void moveDataToWechat() {
        try {
            ObjectNode global = ConfigManager.getInstance().getGlobalConfig();
            JsonNode statNode = global.get("statistic");
            if (statNode == null || !statNode.isObject()) return;
            if (!((ObjectNode) statNode).has("WeChat")) {
                ObjectNode wrapped = com.fasterxml.jackson.databind.node.JsonNodeFactory.instance.objectNode();
                wrapped.set("WeChat", statNode);
                ((ObjectNode) global).set("statistic", wrapped);
                ConfigManager.getInstance().saveAll();
                LOG.info("[数据迁移] moveDataToWechat 完成");
            }
        } catch (Exception e) {
            LOG.warn("[数据迁移] moveDataToWechat 失败: {}", e.getMessage());
        }
    }

    // ==================== 代理设置 ====================

    /**
     * 应用代理设置
     * 对应 Python: apply_proxy_setting (L194-L211)
     */
    public static void applyProxySetting() {
        try {
            Boolean useProxy = ACCESSOR.fetchOrSetDefaultGlobal(
                    AppCoreConstants.GlobalSettingKey.USE_PROXY, false).asBoolean();
            if (useProxy) {
                String proxyIp = ACCESSOR.fetchOrSetDefaultGlobal(
                        AppCoreConstants.GlobalSettingKey.PROXY_IP, "").asText("");
                String proxyPort = ACCESSOR.fetchOrSetDefaultGlobal(
                        AppCoreConstants.GlobalSettingKey.PROXY_PORT, "").asText("");
                System.setProperty("http.proxyHost", proxyIp);
                System.setProperty("http.proxyPort", proxyPort);
                System.setProperty("https.proxyHost", proxyIp);
                System.setProperty("https.proxyPort", proxyPort);
                LOG.info("[代理] 已启用代理: {}:{}", proxyIp, proxyPort);
            } else {
                System.clearProperty("http.proxyHost");
                System.clearProperty("http.proxyPort");
                System.clearProperty("https.proxyHost");
                System.clearProperty("https.proxyPort");
                LOG.info("[代理] 已禁用代理");
            }
        } catch (Exception e) {
            LOG.warn("[代理] 应用代理设置失败: {}", e.getMessage());
        }
    }
}
