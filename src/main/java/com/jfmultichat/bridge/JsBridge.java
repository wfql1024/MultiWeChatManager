package com.jfmultichat.bridge;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.jfmultichat.config.ConfigManager;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.awt.Desktop;
import java.net.URI;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Consumer;

/**
 * JS ↔ Java 桥接 — 暴露给 JavaScript 的 Java 方法.
 * <p>
 * 通过 {@code JSObject.setMember("javaObject", bridge)} 注入到 WebView，
 * 前端通过 {@code JFC.bridge.call("method")} 或 {@code callWithArgs("method", args...)} 调用.
 * <p>
 * 异步操作使用后台线程池，完成后通过 {@code executeScript} 推送到 JS:
 * {@code JFC.bridge._handleAsync(type, cbId, json)}.
 */
public class JsBridge {

    private static final Logger LOG = LoggerFactory.getLogger(JsBridge.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final ExecutorService THREAD_POOL = Executors.newCachedThreadPool(r -> {
        Thread t = new Thread(r, "JsBridge-worker");
        t.setDaemon(true);
        return t;
    });

    private Consumer<String> scriptExecutor;
    private Consumer<String> themeChangeListener;
    private java.util.function.DoubleConsumer alignListener;

    // ==================== Java→JS 执行 ====================

    public void setScriptExecutor(Consumer<String> executor) {
        this.scriptExecutor = executor;
    }

    /** 注册主题变更监听器（由 MainWindow 调用） */
    public void setThemeChangeListener(Consumer<String> listener) {
        this.themeChangeListener = listener;
    }

    /** 注册 logo 对齐回调（由 MainWindow 调用） */
    public void setAlignListener(java.util.function.DoubleConsumer listener) {
        this.alignListener = listener;
    }

    /** 执行 JS 脚本 */
    public void exec(String script) {
        if (scriptExecutor != null) {
            scriptExecutor.accept(script);
        }
    }

    /** 在 JavaFX 线程上推送结果到 JS 回调 */
    private void pushToJs(String jsCall) {
        if (scriptExecutor != null) {
            javafx.application.Platform.runLater(() -> scriptExecutor.accept(jsCall));
        }
    }

    // ========== 异步操作方法（后台线程 + JS回调） ==========

    /**
     * 异步测试远程 URL.
     * 立即返回，后台线程执行 HTTP+解密+解析，完成后推送结果到 JS.
     *
     * @param url 要测试的 URL
     * @param cbId JS 回调 ID (数字字符串)
     */
    public void testRemoteUrlAsync(String url, String cbId) {
        THREAD_POOL.submit(() -> {
            try {
                java.net.http.HttpClient client = java.net.http.HttpClient.newBuilder()
                        .connectTimeout(java.time.Duration.ofSeconds(5))
                        .followRedirects(java.net.http.HttpClient.Redirect.NORMAL)
                        .build();
                java.net.http.HttpRequest request = java.net.http.HttpRequest.newBuilder()
                        .uri(URI.create(url))
                        .timeout(java.time.Duration.ofSeconds(10))
                        .GET().build();
                java.net.http.HttpResponse<String> resp = client.send(request,
                        java.net.http.HttpResponse.BodyHandlers.ofString());
                if (resp.statusCode() != 200) {
                    pushToJs("JFC.bridge._handleAsync('test'," + cbId + ",'{\"success\":false,\"error\":\"HTTP " + resp.statusCode() + "\"}')");
                    return;
                }
                String body = resp.body();
                if (body == null || body.isBlank()) {
                    pushToJs("JFC.bridge._handleAsync('test'," + cbId + ",'{\"success\":false,\"error\":\"响应为空\"}')");
                    return;
                }
                String decrypted = com.jfmultichat.config.CryptoUtils.decryptResponse(body);
                if (decrypted == null || decrypted.isBlank()) {
                    pushToJs("JFC.bridge._handleAsync('test'," + cbId + ",'{\"success\":false,\"error\":\"解密后内容为空\"}')");
                    return;
                }
                MAPPER.readTree(decrypted);
                pushToJs("JFC.bridge._handleAsync('test'," + cbId + ",'{\"success\":true}')");
            } catch (Exception e) {
                LOG.warn("testRemoteUrlAsync failed: {}", url, e);
                String err = e.getMessage() != null ? e.getMessage().replace("'", "\\'") : "未知错误";
                pushToJs("JFC.bridge._handleAsync('test'," + cbId + ",'{\"success\":false,\"error\":\"" + err + "\"}')");
            }
        });
    }

    /** 异步获取更新页数据 */
    public void fetchUpdateDataAsync(String cbId) {
        THREAD_POOL.submit(() -> {
            try {
                JsonNode remoteGlobal = com.jfmultichat.config.RemoteConfigFetcher
                        .tryReadRemoteConfig(com.jfmultichat.config.RemoteConfigFetcher.NS_REMOTE_GLOBAL);
                ObjectNode result = MAPPER.createObjectNode();
                String curVer = com.jfmultichat.config.AppVersion.VERSION;
                result.put("currentVersion", curVer);

                if (remoteGlobal != null && remoteGlobal.has("update")) {
                    JsonNode updateNode = remoteGlobal.get("update");

                    // 收集所有版本号，用版本比较找出最新版
                    java.util.List<String> allVers = new java.util.ArrayList<>();
                    updateNode.fieldNames().forEachRemaining(allVers::add);

                    if (!allVers.isEmpty()) {
                        String[][] split = com.jfmultichat.config.AppVersion.splitVersions(curVer, allVers);
                        if (split != null) {
                            String[] newer = split[0];
                            String[] older = split[1];

                            if (newer.length > 0) {
                                // 取最新的
                                String latest = newer[0];
                                result.put("latestVersion", latest);
                                result.put("hasUpdate", true);
                                if (updateNode.has(latest) && updateNode.get(latest).has("logs"))
                                    result.set("updateLogs", updateNode.get(latest).get("logs"));
                            } else {
                                // 没有更新的版本 — 当前是最新的
                                result.put("latestVersion", older.length > 0 ? older[0] : curVer);
                                result.put("hasUpdate", false);
                            }
                        }
                    }
                } else {
                    result.put("latestVersion", "");
                    result.put("hasUpdate", false);
                }

                String json = MAPPER.writeValueAsString(result);
                pushToJs("JFC.bridge._handleAsync('update'," + cbId + ",'" + json.replace("'", "\\'") + "')");
            } catch (Exception e) {
                LOG.error("fetchUpdateDataAsync failed", e);
                pushToJs("JFC.bridge._handleAsync('update'," + cbId + ",'{}')");
            }
        });
    }

    /** 异步获取鸣谢页数据 */
    public void fetchThanksDataAsync(String cbId) {
        THREAD_POOL.submit(() -> {
            try {
                JsonNode remoteGlobal = com.jfmultichat.config.RemoteConfigFetcher
                        .tryReadRemoteConfig(com.jfmultichat.config.RemoteConfigFetcher.NS_REMOTE_GLOBAL);
                ObjectNode result = MAPPER.createObjectNode();
                if (remoteGlobal != null && remoteGlobal.has("about")) {
                    JsonNode about = remoteGlobal.get("about");
                    result.set("thanks", about.has("thanks") ? about.get("thanks") : MAPPER.createObjectNode());
                    result.set("sponsors", about.has("sponsor") ? about.get("sponsor") : MAPPER.createArrayNode());
                    result.set("reference", about.has("reference") ? about.get("reference") : MAPPER.createArrayNode());
                } else {
                    result.putObject("thanks");
                    result.putArray("sponsors");
                    result.putArray("reference");
                }
                String json = MAPPER.writeValueAsString(result);
                pushToJs("JFC.bridge._handleAsync('thanks'," + cbId + ",'" + json.replace("'", "\\'") + "')");
            } catch (Exception e) {
                LOG.error("fetchThanksDataAsync failed", e);
                pushToJs("JFC.bridge._handleAsync('thanks'," + cbId + ",'{}')");
            }
        });
    }

    /** 异步获取关于页数据 */
    public void fetchAboutDataAsync(String cbId) {
        THREAD_POOL.submit(() -> {
            try {
                JsonNode remoteGlobal = com.jfmultichat.config.RemoteConfigFetcher
                        .tryReadRemoteConfig(com.jfmultichat.config.RemoteConfigFetcher.NS_REMOTE_GLOBAL);
                ObjectNode result = MAPPER.createObjectNode();
                if (remoteGlobal != null) {
                    result.put("appName", remoteGlobal.has("app_name") ? remoteGlobal.get("app_name").asText() : "极峰多聊");
                    result.put("appAuthor", remoteGlobal.has("app_author") ? remoteGlobal.get("app_author").asText() : "吾峰起浪");
                    if (remoteGlobal.has("about")) {
                        JsonNode about = remoteGlobal.get("about");
                        result.set("home", about.has("home") ? about.get("home") : MAPPER.createObjectNode());
                        result.set("project", about.has("project") ? about.get("project") : MAPPER.createObjectNode());
                        result.set("reference", about.has("reference") ? about.get("reference") : MAPPER.createArrayNode());
                    }
                }
                String json = MAPPER.writeValueAsString(result);
                pushToJs("JFC.bridge._handleAsync('about'," + cbId + ",'" + json.replace("'", "\\'") + "')");
            } catch (Exception e) {
                LOG.error("fetchAboutDataAsync failed", e);
                pushToJs("JFC.bridge._handleAsync('about'," + cbId + ",'{}')");
            }
        });
    }

    // ========== 暴露给 JS 的方法 ==========

    /** JS 调用：切换主题 */
    public void setTheme(String theme) {
        LOG.info("Theme changed to: {}", theme);
        if (themeChangeListener != null) {
            themeChangeListener.accept(theme);
        }
    }

    /** JS 调用：报告侧栏图标中心 X 坐标，Java 据此对齐标题栏 logo */
    public void reportSidebarIconCenter(double x) {
        LOG.debug("Sidebar icon center reported: {}", x);
        if (alignListener != null) {
            alignListener.accept(x);
        }
    }

    /** JS 调用：用默认浏览器打开 URL */
    public void openExternal(String url) {
        try {
            Desktop.getDesktop().browse(new URI(url));
        } catch (Exception e) {
            LOG.warn("Failed to open URL: {}", url, e);
        }
    }

    /** ping — 检查桥接是否正常 */
    public String ping() {
        return "pong";
    }

    // ========== 数据访问方法（供前端展示） ==========

    /**
     * 获取所有 Sw 列表.
     * 从 local_config.json 的顶层键（排除 "global"）中读取.
     *
     * @return Sw ID 列表的 JSON 数组字符串，如 {@code ["WeChat","Weixin","QQNT"]}
     */
    public String getSwList() {
        try {
            List<String> swList = ConfigManager.getInstance().getSwList();
            return MAPPER.writeValueAsString(swList);
        } catch (Exception e) {
            LOG.error("Failed to get Sw list", e);
            return "[]";
        }
    }

    /**
     * 获取指定 Sw 下的所有账号列表.
     * 从 sw_acc_data.json 中读取.
     *
     * @param swId Sw ID，如 "WeChat"、"Weixin"
     * @return 账号映射的 JSON 字符串，如 {@code {"wxid_xxx":{...},"wxid_yyy":{...}}}
     */
    public String getAccountList(String swId) {
        try {
            Map<String, ObjectNode> accounts = ConfigManager.getInstance().getAccountMap(swId);
            // 构建精简的账号列表 — 每个账号仅返回 id + nickname + avatar_url
            List<ObjectNode> list = new java.util.ArrayList<>();
            accounts.forEach((id, fields) -> {
                ObjectNode item = MAPPER.createObjectNode();
                item.put("id", id);
                item.put("nickname", fields.has("nickname") ? fields.get("nickname").asText() : "");
                item.put("avatar_url", fields.has("avatar_url") ? fields.get("avatar_url").asText() : "");
                list.add(item);
            });
            return MAPPER.writeValueAsString(list);
        } catch (Exception e) {
            LOG.error("Failed to get account list for swId={}", swId, e);
            return "[]";
        }
    }

    /**
     * 获取当前主题设置（从 local_config.json → global → theme）.
     * 供前端初始化时读取.
     *
     * @return 主题字符串: "dark" | "light" | "auto"
     */
    public String getTheme() {
        try {
            ObjectNode globalConfig = ConfigManager.getInstance().getGlobalConfig();
            if (globalConfig.has("theme")) {
                return globalConfig.get("theme").asText();
            }
        } catch (Exception e) {
            LOG.warn("Failed to get theme from config", e);
        }
        return "auto";
    }

    /**
     * 保存当前主题设置到 local_config.json.
     */
    public void saveTheme(String theme) {
        try {
            ConfigManager.getInstance().updateGlobalConfig(Map.of("theme", theme));
            LOG.info("Theme saved: {}", theme);
        } catch (Exception e) {
            LOG.warn("Failed to save theme", e);
        }
    }

    // ========== 配置页数据（供设置 → 配置 使用） ==========

    /**
     * 获取默认用户数据目录路径.
     * 供前端"配置"页的"默认"按钮使用.
     */
    public String getDefaultUserDir() {
        return com.jfmultichat.config.AppPaths.getDefaultUserDataDir().toString();
    }

    /**
     * 获取配置页所需的所有数据.
     * 包括：代理设置(local_config.json)、用户目录(root_config.json)、远程 URL(root_config.json).
     *
     * @return JSON 字符串，包含 useProxy, proxyIp, proxyPort, userDataPath, remoteSwUrl, remoteGlobalUrl
     */
    public String getConfigData() {
        try {
            ConfigManager cm = ConfigManager.getInstance();
            ObjectNode result = MAPPER.createObjectNode();

            // 代理设置 → local_config.json → global
            ObjectNode global = cm.getGlobalConfig();
            result.put("useProxy", global.has("use_proxy") && global.get("use_proxy").asBoolean());
            result.put("proxyIp", global.has("proxy_ip") ? global.get("proxy_ip").asText() : "");
            result.put("proxyPort", global.has("proxy_port") ? global.get("proxy_port").asText() : "");

            // 用户目录 → root_config.json
            result.put("userDataPath", cm.getRootConfig().getUserDataPath());

            // 远程 URL 列表 → local_config.json → global (优先从数组读，回退到 root_config 单值)
            var remoteGlobalUrls = global.has("remote_global_urls")
                    ? global.get("remote_global_urls")
                    : MAPPER.createArrayNode().add(cm.getRootConfig().getRemoteGlobalUrl());
            var remoteSwUrls = global.has("remote_sw_urls")
                    ? global.get("remote_sw_urls")
                    : MAPPER.createArrayNode().add(cm.getRootConfig().getRemoteSwUrl());
            result.set("remoteGlobalUrls", remoteGlobalUrls);
            result.set("remoteSwUrls", remoteSwUrls);

            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to get config data", e);
            return "{}";
        }
    }

    /**
     * 获取代理预设值（从远程全局配置的 proxy 节点）.
     *
     * @return JSON 字符串，包含 ipPresets 和 portPresets 数组
     */
    public String getProxyPresets() {
        try {
            ObjectNode result = MAPPER.createObjectNode();
            com.jfmultichat.setting.RemoteGlobalSetting rgs =
                    com.jfmultichat.setting.RemoteGlobalSetting.getInstance();

            var proxyNode = rgs.get("proxy");
            if (proxyNode.isPresent()) {
                var proxy = proxyNode.get();
                if (proxy.has("ip_presets")) {
                    result.set("ipPresets", proxy.get("ip_presets"));
                } else {
                    result.putArray("ipPresets");
                }
                if (proxy.has("port_presets")) {
                    result.set("portPresets", proxy.get("port_presets"));
                } else {
                    result.putArray("portPresets");
                }
            } else {
                result.putArray("ipPresets");
                result.putArray("portPresets");
            }

            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to get proxy presets", e);
            return "{\"ipPresets\":[],\"portPresets\":[]}";
        }
    }

    /**
     * 保存配置页数据.
     * 接收前端 JSON → 分别写入 local_config.json（代理）和 root_config.json（用户目录、远程URL）.
     *
     * @param json 包含 useProxy, proxyIp, proxyPort, userDataPath, remoteSwUrl, remoteGlobalUrl
     * @return JSON 字符串，包含 success(bool) 和可选的 error(string) / pathChanged(bool) / newPath(string)
     */
    public String saveConfigData(String json) {
        try {
            JsonNode data = MAPPER.readTree(json);
            ConfigManager cm = ConfigManager.getInstance();
            ObjectNode result = MAPPER.createObjectNode();

            // 代理设置 → local_config.json → global
            Map<String, Object> proxyUpdates = new java.util.LinkedHashMap<>();
            if (data.has("useProxy")) {
                proxyUpdates.put("use_proxy", data.get("useProxy").asBoolean());
            }
            if (data.has("proxyIp")) {
                proxyUpdates.put("proxy_ip", data.get("proxyIp").asText().trim());
            }
            if (data.has("proxyPort")) {
                proxyUpdates.put("proxy_port", data.get("proxyPort").asText().trim());
            }
            if (!proxyUpdates.isEmpty()) {
                cm.updateGlobalConfig(proxyUpdates);
            }

            // 远程 URL 列表 → local_config.json → global
            if (data.has("remoteGlobalUrls") && data.get("remoteGlobalUrls").isArray()) {
                proxyUpdates.put("remote_global_urls", data.get("remoteGlobalUrls"));
                // 同时更新 root_config 的首个 URL（兼容）:
                var arr = data.get("remoteGlobalUrls");
                cm.getRootConfig().setRemoteGlobalUrl(arr.size() > 0 ? arr.get(0).asText().trim() : "");
            }
            if (data.has("remoteSwUrls") && data.get("remoteSwUrls").isArray()) {
                proxyUpdates.put("remote_sw_urls", data.get("remoteSwUrls"));
                var arr = data.get("remoteSwUrls");
                cm.getRootConfig().setRemoteSwUrl(arr.size() > 0 ? arr.get(0).asText().trim() : "");
            }

            // 用户目录 → root_config.json（可能触发迁移）
            boolean pathChanged = false;
            if (data.has("userDataPath")) {
                String newPath = data.get("userDataPath").asText().trim();
                String oldPath = cm.getRootConfig().getUserDataPath();
                if (!newPath.isEmpty() && !newPath.equals(oldPath)) {
                    cm.setUserDataPath(newPath);
                    pathChanged = true;
                    result.put("newPath", cm.getUserDataPath().toString());
                }
            }

            cm.saveAll();
            result.put("success", true);
            result.put("pathChanged", pathChanged);
            LOG.info("Config saved. proxy={}, userDataPath changed={}",
                    data.has("useProxy") ? data.get("useProxy").asBoolean() : false, pathChanged);

            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to save config data", e);
            return "{\"success\":false,\"error\":\"" + e.getMessage() + "\"}";
        }
    }

    // ========== 更新 / 鸣谢 / 关于 页面数据 ==========

    /**
     * 获取更新页数据.
     * 从远程全局配置的 update 节点提取已发布的版本信息，
     * 结合当前应用版本做比较.
     *
     * @return JSON: {currentVersion, latestVersion, hasUpdate, updateLogs, ...}
     */
    public String getUpdateData() {
        try {
            JsonNode remoteGlobal = com.jfmultichat.config.RemoteConfigFetcher
                    .tryReadRemoteConfig(com.jfmultichat.config.RemoteConfigFetcher.NS_REMOTE_GLOBAL);

            ObjectNode result = MAPPER.createObjectNode();
            result.put("currentVersion", com.jfmultichat.config.AppPaths.VERSION);

            if (remoteGlobal != null && remoteGlobal.has("update")) {
                JsonNode updateNode = remoteGlobal.get("update");

                // 取第一个版本作为最新版本
                var fields = updateNode.fields();
                if (fields.hasNext()) {
                    var latest = fields.next();
                    String latestVer = latest.getKey();
                    result.put("latestVersion", latestVer);
                    result.put("hasUpdate", !latestVer.contains(com.jfmultichat.config.AppPaths.VERSION));

                    // 更新日志
                    JsonNode logNode = latest.getValue();
                    if (logNode.has("logs")) {
                        result.set("updateLogs", logNode.get("logs"));
                    }
                } else {
                    result.put("latestVersion", "");
                    result.put("hasUpdate", false);
                }
            } else {
                result.put("latestVersion", "");
                result.put("hasUpdate", false);
            }

            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to get update data", e);
            return "{\"currentVersion\":\"\",\"latestVersion\":\"\",\"hasUpdate\":false}";
        }
    }

    /**
     * 获取鸣谢页数据.
     * 从远程全局配置的 about 节点提取 thanks 和 sponsor.
     *
     * @return JSON: {thanks: {...}, sponsors: [...]}
     */
    public String getThanksData() {
        try {
            JsonNode remoteGlobal = com.jfmultichat.config.RemoteConfigFetcher
                    .tryReadRemoteConfig(com.jfmultichat.config.RemoteConfigFetcher.NS_REMOTE_GLOBAL);

            ObjectNode result = MAPPER.createObjectNode();

            if (remoteGlobal != null && remoteGlobal.has("about")) {
                JsonNode about = remoteGlobal.get("about");

                // 鸣谢
                if (about.has("thanks")) {
                    result.set("thanks", about.get("thanks"));
                } else {
                    result.putObject("thanks");
                }

                // 赞助
                if (about.has("sponsor")) {
                    result.set("sponsors", about.get("sponsor"));
                } else {
                    result.putArray("sponsors");
                }
            } else {
                result.putObject("thanks");
                result.putArray("sponsors");
            }

            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to get thanks data", e);
            return "{\"thanks\":{},\"sponsors\":[]}";
        }
    }

    /**
     * 获取关于页数据.
     * 从远程全局配置提取 home, project, reference, app_name, app_author.
     *
     * @return JSON: {appName, appAuthor, home, project, reference}
     */
    public String getAboutData() {
        try {
            JsonNode remoteGlobal = com.jfmultichat.config.RemoteConfigFetcher
                    .tryReadRemoteConfig(com.jfmultichat.config.RemoteConfigFetcher.NS_REMOTE_GLOBAL);

            ObjectNode result = MAPPER.createObjectNode();

            if (remoteGlobal != null) {
                result.put("appName", remoteGlobal.has("app_name")
                        ? remoteGlobal.get("app_name").asText() : "极峰多聊");
                result.put("appAuthor", remoteGlobal.has("app_author")
                        ? remoteGlobal.get("app_author").asText() : "吾峰起浪");

                if (remoteGlobal.has("about")) {
                    JsonNode about = remoteGlobal.get("about");
                    if (about.has("home")) result.set("home", about.get("home"));
                    else result.putObject("home");
                    if (about.has("project")) result.set("project", about.get("project"));
                    else result.putObject("project");
                    if (about.has("reference")) result.set("reference", about.get("reference"));
                    else result.putArray("reference");
                } else {
                    result.putObject("home");
                    result.putObject("project");
                    result.putArray("reference");
                }
            } else {
                result.put("appName", "极峰多聊");
                result.put("appAuthor", "吾峰起浪");
                result.putObject("home");
                result.putObject("project");
                result.putArray("reference");
            }

            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to get about data", e);
            return "{\"appName\":\"\",\"appAuthor\":\"\",\"home\":{},\"project\":{},\"reference\":[]}";
        }
    }

    /**
     * 获取当前构建的 Git 提交信息（供更新页显示）.
     */
    public String getCommitInfo() {
        try {
            ObjectNode result = MAPPER.createObjectNode();
            try (java.io.InputStream is = getClass().getResourceAsStream("/git.properties")) {
                if (is != null) {
                    java.util.Properties props = new java.util.Properties();
                    props.load(is);
                    result.put("commitId", props.getProperty("git.commit.id.abbrev",
                            props.getProperty("git.commit.id", "")));
                    result.put("commitDate", props.getProperty("git.commit.time", ""));
                    return MAPPER.writeValueAsString(result);
                }
            } catch (Exception ignored) {}
            result.put("commitId", "");
            result.put("commitDate", "");
            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.warn("Failed to get commit info", e);
            return "{\"commitId\":\"\",\"commitDate\":\"\"}";
        }
    }

    // ========== 配置页辅助方法 ==========

    /**
     * 获取默认远程配置 URL 列表.
     * 返回内置的所有地址（带标签）供前端列表展示.
     */
    public String getDefaultUrls() {
        try {
            ObjectNode result = MAPPER.createObjectNode();

            // 远程全局默认 URL
            var globalArr = result.putArray("remoteGlobalDefaults");
            for (String url : com.jfmultichat.config.RemoteConfigFetcher.getBuiltinRemoteGlobalUrls()) {
                ObjectNode item = MAPPER.createObjectNode();
                item.put("url", url);
                item.put("label", url.contains("gitee") ? "Gitee" : "GitHub");
                globalArr.add(item);
            }

            // 远程平台默认 URL
            var swArr = result.putArray("remoteSwDefaults");
            for (String url : com.jfmultichat.config.RemoteConfigFetcher.getBuiltinRemoteSwUrls()) {
                ObjectNode item = MAPPER.createObjectNode();
                item.put("url", url);
                item.put("label", url.contains("gitee") ? "Gitee" : "GitHub");
                swArr.add(item);
            }

            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.warn("Failed to get default URLs", e);
            return "{}";
        }
    }

    /**
     * 测试远程配置 URL 是否可用.
     * 下载 → 解密 → 尝试解析 JSON → 返回结果.
     *
     * @param url 要测试的 URL
     * @return JSON: {success: true/false, error: "..."}
     */
    public String testRemoteUrl(String url) {
        try {
            if (url == null || url.isBlank()) {
                return "{\"success\":false,\"error\":\"URL 为空\"}";
            }
            java.net.http.HttpClient client = java.net.http.HttpClient.newBuilder()
                    .connectTimeout(java.time.Duration.ofSeconds(5))
                    .build();
            java.net.http.HttpRequest request = java.net.http.HttpRequest.newBuilder()
                    .uri(java.net.URI.create(url))
                    .timeout(java.time.Duration.ofSeconds(10))
                    .GET().build();
            java.net.http.HttpResponse<String> resp = client.send(request,
                    java.net.http.HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() != 200) {
                return "{\"success\":false,\"error\":\"HTTP " + resp.statusCode() + "\"}";
            }
            String body = resp.body();
            if (body == null || body.isBlank()) {
                return "{\"success\":false,\"error\":\"响应为空\"}";
            }
            // 尝试解密
            String decrypted = com.jfmultichat.config.CryptoUtils.decryptResponse(body);
            if (decrypted == null || decrypted.isBlank()) {
                return "{\"success\":false,\"error\":\"解密后内容为空\"}";
            }
            // 尝试解析 JSON
            MAPPER.readTree(decrypted);
            return "{\"success\":true}";
        } catch (Exception e) {
            LOG.warn("testRemoteUrl failed: {}", url, e);
            return "{\"success\":false,\"error\":\"" + e.getMessage().replace("\"", "'") + "\"}";
        }
    }

    /**
     * 打开文件夹选择对话框，返回所选目录的绝对路径.
     */
    public String browseFolder(String initialPath) {
        try {
            javafx.stage.DirectoryChooser chooser = new javafx.stage.DirectoryChooser();
            chooser.setTitle("选择用户数据目录");
            if (initialPath != null && !initialPath.isBlank()) {
                java.io.File initDir = new java.io.File(initialPath);
                if (initDir.exists() && initDir.isDirectory()) {
                    chooser.setInitialDirectory(initDir);
                }
            }
            java.io.File selected = chooser.showDialog(null);
            return selected != null ? selected.getAbsolutePath() : "";
        } catch (Exception e) {
            LOG.warn("browseFolder failed", e);
            return "";
        }
    }

    /**
     * 当前是否为开发模式.
     */
    public boolean isDevMode() {
        return com.jfmultichat.config.AppPaths.isDevMode();
    }

    /**
     * 校验 Windows 路径合法性.
     * 检查：盘符格式（必须有冒号）、非法字符、盘符是否存在.
     *
     * @param path 待校验的绝对路径
     * @return JSON: {valid: true/false, error: "..."}
     */
    public String validatePath(String path) {
        try {
            ObjectNode result = MAPPER.createObjectNode();
            if (path == null || path.isBlank()) {
                result.put("valid", false);
                result.put("error", "路径为空");
                return MAPPER.writeValueAsString(result);
            }

            String trimmed = path.trim();
            if (!trimmed.equals(path)) {
                result.put("valid", false);
                result.put("error", "路径首尾不能有空格");
                return MAPPER.writeValueAsString(result);
            }

            // 非法字符检查
            if (trimmed.matches(".*[\\*\\?\"<>\\|].*")) {
                result.put("valid", false);
                result.put("error", "路径包含非法字符 (* ? \" < > |)");
                return MAPPER.writeValueAsString(result);
            }

            // 盘符格式检查: 必须以 [A-Z]: 开头
            if (!trimmed.matches("^[A-Za-z]:.*")) {
                if (trimmed.matches("^[A-Za-z]/.*") || trimmed.matches("^[A-Za-z]\\\\.*")) {
                    result.put("valid", false);
                    result.put("error", "盘符缺少冒号，应为 " + trimmed.charAt(0) + ":\\");
                } else {
                    result.put("valid", false);
                    result.put("error", "路径必须以盘符开头 (如 C:\\)");
                }
                return MAPPER.writeValueAsString(result);
            }

            // 盘符存在性检查
            String driveLetter = trimmed.substring(0, 1).toUpperCase() + ":\\";
            java.io.File drive = new java.io.File(driveLetter);
            if (!drive.exists()) {
                result.put("valid", false);
                result.put("error", "盘符 " + driveLetter + " 在当前系统中不存在");
                return MAPPER.writeValueAsString(result);
            }

            result.put("valid", true);
            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.warn("validatePath failed", e);
            return "{\"valid\":false,\"error\":\"" + e.getMessage().replace("\"", "'") + "\"}";
        }
    }
}
